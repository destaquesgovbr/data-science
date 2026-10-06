#!/usr/bin/env python3
"""
Re-enriquecimento da chamada COMBINADA (tema + resumo + sentimento) numa janela
de datas, SEM NER e SEM publicar evento. Fase 2.5 (DS-1).

Backfills:
  - B2: `--select null-theme --date-from 2026-09-25 --date-to 2026-10-06`:
    artigos que ficaram sem tema quando o Claude 3 Haiku teve EOL no Bedrock
    (25/09 até o INF-1/infra#215, aplicado em 06/10 00:19Z = 05/10 21:19 BRT).
  - B5 (decisão D3): `--select mock`: os ~4.600 artigos com summary '[MOCK]…'
    (tema também falso; ver issue #3).
  - DS-2: `--select null-summary --date-from 2026-06-01 --date-to <hoje BRT>`:
    os ~6.935 artigos com tema e summary NULL. O re-scrape do scraper
    (`_update_existing_articles`, desde o d406fee de 01/06) grava summary = NULL
    e content_embedding = NULL. Só depois do deploy do SC-1 (senão o re-scrape
    apaga de novo). Ver "Modo null-summary" abaixo.

Fluxo por artigo (espelha o caminho de sucesso de handler.enrich_article, menos
o NER e o evento):
    result = classifier.classify_single(article)       # modelo = ENRICHMENT_MODEL_ID
    update_news_enrichment(db, [result], code_to_id)   # tema + resumo
    _upsert_ai_features(uid, {"sentiment": ...})       # NUNCA entities
    quota_governor.record_usage(...)                   # ledger por modelo

Garantias:
  - NUNCA chama extract_entities: não toca o pool do Sonnet e não sobrescreve
    entidades canonicalizadas (o merge `features || {...}` só leva `sentiment`).
  - NUNCA publica dgb.news.enriched: reenviar o evento para artigos antigos
    geraria push e federation de notícias velhas.
  - Governador de cota: para gracioso quando o consumo do dia do modelo
    (account-wide, ledger llm_daily_usage) bate `fração × cota`. Resumível: a
    seleção exclui o que já foi feito (tema gravado / summary sem [MOCK]).
    Use a cota REAL da AWS em BEDROCK_DAILY_TOKEN_QUOTA; a fração
    (BACKFILL_QUOTA_FRACTION, default 0.8) é aplicada aqui, uma única vez.
  - Modelo indisponível (EOL / id inexistente) aborta o run (código de saída 1).
  - Janela por dia BRT (America/Sao_Paulo); --date-to é EXCLUSIVO.
  - `null-theme` EXIGE --date-to, e ele não pode passar de hoje (BRT): sem teto,
    o ORDER BY published_at DESC pegaria primeiro artigos novos que o worker ao
    vivo ainda vai processar. Gravar o tema deles aqui (sem NER e sem publicar)
    faria o worker devolver `skipped` e o artigo ficaria sem dgb.news.enriched.
  - --dry-run só seleciona e lista: não chama o Bedrock nem escreve nada.

Modo null-summary (DS-2): só o resumo, com o prompt ENXUTO do
BedrockLLMClient.summarize_single (as regras de resumo da combinada, sem a
taxonomia: prompt de no máximo ~3 mil caracteres; a combinada manda ~18,9k
tokens de entrada). Por artigo:
    result = llm_client.summarize_single(article)       # modelo = ENRICHMENT_MODEL_ID
    UPDATE news SET summary = %s, updated_at = NOW()
     WHERE unique_id = %s AND summary IS NULL           # UPDATE_SUMMARY_SQL
    quota_governor.record_usage(...)                    # ledger por modelo
  - NUNCA regrava tema, NUNCA chama o NER, NUNCA publica, NUNCA grava
    news_features e NÃO toca content_embedding (o B3 gera depois, a partir do
    resumo).
  - Sentimento ausente em news_features NÃO é gerado aqui (fora do escopo): só
    é contado e reportado (sem_sentimento=N) na seleção e no resumo final.
  - Selecionados que JÁ têm content_embedding (feito sem o resumo, a partir do
    content) são contados e reportados (com_embedding=N) na seleção e no resumo
    final. O embedding deles não é tocado aqui, e o B3 (só content_embedding IS
    NULL) não o refaz: exigem um passo separado, aprovado, depois do DS-2 (ver o
    README do worker).
  - Resumo vazio/inválido não grava e conta `summary_failed`: o artigo segue
    selecionável no próximo run. Resumo gravado por outro processo no meio do
    run não é sobrescrito (guarda IS NULL → `summary_present`).
  - Mesma regra do null-theme para a janela: --date-to obrigatório, ≤ hoje BRT.

Env obrigatórias: DATABASE_URL, ENRICHMENT_MODEL_ID (sem fallback para o default
legado nem para BEDROCK_MODEL_ID), creds AWS (AWS_BEDROCK_CONNECTION_URI ou
AWS_ACCESS_KEY_ID/SECRET). Opcionais: BEDROCK_DAILY_TOKEN_QUOTA (JSON
{model_id: tokens/dia}), BACKFILL_QUOTA_FRACTION.

Uso (sempre --dry-run → --limit 10 → completo, cada etapa com OK):
    ENRICHMENT_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \\
    PYTHONPATH=src .venv/bin/python scripts/reenrich_combined_window.py \\
        --select null-theme --date-from 2026-09-25 --date-to 2026-10-06 \\
        [--limit 500] [--workers 1] [--dry-run]
    # DS-2 (depois do deploy do SC-1):
    ... --select null-summary --date-from 2026-06-01 --date-to <hoje BRT> [...]
"""
import argparse
import datetime
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from news_enrichment.enrichment_job import update_news_enrichment  # noqa: E402
from news_enrichment.llm_client import is_model_unavailable_error  # noqa: E402
from news_enrichment.quota_governor import (  # noqa: E402
    budget_exhausted,
    parse_daily_quota_env,
    record_usage,
)
from news_enrichment.worker import handler  # noqa: E402

SELECT_CHOICES = ("null-theme", "mock", "null-summary")
# Seleções que disputam artigos com o worker ao vivo: exigem --date-to <= hoje BRT.
SELECTS_REQUIRING_DATE_TO = frozenset({"null-theme", "null-summary"})
# Janela de exemplo por seleção (mensagem de erro sem --date-to).
_EXAMPLE_WINDOW = {
    "null-theme": "no B2: --date-from 2026-09-25 --date-to 2026-10-06",
    "null-summary": "no DS-2: --date-from 2026-06-01 --date-to <hoje BRT>",
}
BRT = ZoneInfo("America/Sao_Paulo")
MOCK_SUMMARY_PATTERN = "[MOCK]%"
# Checa o budget a cada N artigos (tolera pequena ultrapassagem; margem ~fração).
BUDGET_CHECK_EVERY = 5
DRY_RUN_SAMPLE = 20
_ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0}

# Limites da janela: meia-noite do dia em BRT, convertida para timestamptz.
_BRT_DAY_START = "(%({param})s::date::timestamp AT TIME ZONE 'America/Sao_Paulo')"

# null-summary: grava SÓ o resumo, e só se ainda estiver NULL (não sobrescreve um
# resumo gravado no meio do run). Tema e content_embedding ficam intactos.
UPDATE_SUMMARY_SQL = """
    UPDATE news
    SET summary = %s, updated_at = NOW()
    WHERE unique_id = %s AND summary IS NULL
"""

# null-summary: quantos dos uids não têm sentimento em news_features (só reportado;
# este modo não gera sentimento).
MISSING_SENTIMENT_SQL = """
    SELECT COUNT(*)
    FROM news n
    LEFT JOIN news_features nf ON nf.unique_id = n.unique_id
    WHERE n.unique_id = ANY(%s)
      AND (nf.features -> 'sentiment' ->> 'label') IS NULL
"""

# null-summary: quantos dos uids JÁ têm content_embedding (feito sem o resumo, a
# partir do content). Só reportado: o embedding não é tocado aqui e o B3 só pega
# content_embedding IS NULL, então esses artigos exigem um passo separado.
WITH_EMBEDDING_SQL = """
    SELECT COUNT(*)
    FROM news n
    WHERE n.unique_id = ANY(%s)
      AND n.content_embedding IS NOT NULL
"""


def build_select_sql(select: str, with_date_to: bool) -> str:
    """SELECT da janela: `null-theme` (tema NULL), `mock` (summary '[MOCK]%') ou
    `null-summary` (tema gravado e summary NULL).

    Parâmetros nomeados (ver build_select_params). Ordem: mais recentes primeiro.
    `null-theme`/`null-summary` sem teto (with_date_to=False) são recusados: ver o
    docstring do módulo.
    """
    if select in SELECTS_REQUIRING_DATE_TO and not with_date_to:
        raise ValueError(f"--select {select} exige --date-to (teto da janela)")
    if select == "null-theme":
        predicate = "n.most_specific_theme_id IS NULL"
    elif select == "mock":
        predicate = "n.summary LIKE %(mock_pattern)s"
    elif select == "null-summary":
        predicate = "n.most_specific_theme_id IS NOT NULL AND n.summary IS NULL"
    else:
        raise ValueError(f"seleção inválida: {select!r} (use {', '.join(SELECT_CHOICES)})")

    upper = ""
    if with_date_to:
        upper = f"AND n.published_at < {_BRT_DAY_START.format(param='date_to')}"
    return f"""
        SELECT n.unique_id
        FROM news n
        WHERE {predicate}
          AND n.published_at >= {_BRT_DAY_START.format(param='date_from')}
          {upper}
        ORDER BY n.published_at DESC
        LIMIT %(limit)s
    """


def build_select_params(select: str, date_from: str, date_to, limit: int) -> dict:
    params = {"date_from": date_from, "limit": limit}
    if date_to:
        params["date_to"] = date_to
    if select == "mock":
        params["mock_pattern"] = MOCK_SUMMARY_PATTERN
    return params


def _get_conn():
    """Conexão psycopg2 (separada para selecionar uids / ler e gravar o ledger)."""
    return psycopg2.connect(handler._get_database_url())


def get_window_uids(select: str, date_from: str, date_to, limit: int) -> list:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            build_select_sql(select, with_date_to=bool(date_to)),
            build_select_params(select, date_from, date_to, limit),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def process_one(uid: str):
    """Re-enriquece um artigo. Retorna (uid, status, usage).

    status: ok | missing | classification_failed | model_unavailable |
    update_failed | error:<Exceção>. usage = tokens da chamada combinada.
    NUNCA chama extract_entities e NUNCA publica evento.
    """
    article = handler.fetch_article(uid)
    if not article:
        return uid, "missing", dict(_ZERO_USAGE)

    try:
        result = handler._get_classifier().classify_single(article, return_format="dict")
    except Exception as e:  # noqa: BLE001 — um artigo ruim não derruba o run
        return uid, f"error:{type(e).__name__}", dict(_ZERO_USAGE)

    usage = (result or {}).get("_usage") or dict(_ZERO_USAGE)
    if handler.is_combined_failure(result):
        error = handler.combined_failure_error(result)
        status = (
            "model_unavailable" if is_model_unavailable_error(error) else "classification_failed"
        )
        print(f"  {uid}: {status} ({error})")
        return uid, status, usage

    result["unique_id"] = uid
    try:
        stats = update_news_enrichment(
            handler._get_database_url(), [result], handler._get_code_to_id()
        )
        if not stats.get("updated"):
            return uid, "update_failed", usage
        # Só o sentimento: entidades ficam como estão (sem NER neste script).
        handler._upsert_ai_features(uid, {"sentiment": result.get("sentiment")})
    except Exception as e:  # noqa: BLE001 — tokens já gastos: devolve o usage
        return uid, f"error:{type(e).__name__}", usage
    return uid, "ok", usage


def _count_uids(sql: str, uids: list) -> int:
    """Executa um COUNT(*) parametrizado pela lista de uids (só leitura)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, (list(uids),))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()


def count_missing_sentiment(uids: list) -> int:
    """Quantos dos uids não têm sentimento em news_features (null-summary só reporta)."""
    return _count_uids(MISSING_SENTIMENT_SQL, uids)


def count_with_embedding(uids: list) -> int:
    """Quantos dos uids já têm content_embedding (null-summary só reporta)."""
    return _count_uids(WITH_EMBEDDING_SQL, uids)


def update_summary_only(uid: str, summary: str) -> bool:
    """Grava SÓ o resumo (UPDATE_SUMMARY_SQL). True se gravou; False se o artigo
    já tinha resumo (guarda IS NULL) ou não existe."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(UPDATE_SUMMARY_SQL, (summary, uid))
        written = cur.rowcount == 1
        conn.commit()
        return written
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_one_summary(uid: str):
    """Gera e grava SÓ o resumo (--select null-summary). Retorna (uid, status, usage).

    status: ok | missing | summary_failed | model_unavailable | summary_present |
    error:<Exceção>. usage = tokens da chamada só-resumo (todas as tentativas).
    NUNCA chama a combinada nem o NER, NUNCA grava news_features (nem sentimento),
    NUNCA publica evento.
    """
    article = handler.fetch_article(uid)
    if not article:
        return uid, "missing", dict(_ZERO_USAGE)

    try:
        result = handler._get_classifier().llm_client.summarize_single(article)
    except Exception as e:  # noqa: BLE001 — um artigo ruim não derruba o run
        return uid, f"error:{type(e).__name__}", dict(_ZERO_USAGE)

    result = result or {}
    usage = result.get("_usage") or dict(_ZERO_USAGE)
    error = result.get("_error")
    summary = result.get("summary")
    if error or not isinstance(summary, str) or not summary.strip():
        # Não grava: o artigo segue com summary NULL e selecionável no próximo run.
        status = "model_unavailable" if is_model_unavailable_error(error) else "summary_failed"
        print(f"  {uid}: {status} ({error or 'resumo vazio ou inválido'})")
        return uid, status, usage

    try:
        written = update_summary_only(uid, summary.strip())
    except Exception as e:  # noqa: BLE001 — tokens já gastos: devolve o usage
        return uid, f"error:{type(e).__name__}", usage
    return uid, ("ok" if written else "summary_present"), usage


def _record_usage_for(conn, model_id: str, usage: dict) -> None:
    """Grava o usage de uma chamada no ledger (se não-zero)."""
    if not usage:
        return
    in_tok = usage.get("input_tokens") or 0
    out_tok = usage.get("output_tokens") or 0
    if in_tok or out_tok:
        record_usage(conn, model_id, in_tok, out_tok)


def run_reenrich(
    uids: list,
    *,
    model_id: str,
    daily_quota,
    quota_fraction: float,
    workers: int,
    process=process_one,
) -> dict:
    """Processa uids com governador de cota. Resumível e capado.

    `process(uid) -> (uid, status, usage)`: process_one (chamada combinada) ou
    process_one_summary (null-summary). Para em budget_exhausted (parada graciosa)
    ou no primeiro modelo indisponível. Sem cota (None/<=0) → modo sem-teto
    (apenas grava o ledger).
    """
    stats: dict = {"budget_exhausted": False, "model_unavailable": False}
    has_quota = bool(daily_quota and daily_quota > 0)
    if not has_quota:
        print(f"AVISO: sem cota diária para {model_id!r} — modo sem-teto.")

    ledger_conn = _get_conn()
    try:
        t0 = time.time()
        done = 0

        def _consume(status: str, usage: dict) -> None:
            nonlocal done
            _record_usage_for(ledger_conn, model_id, usage)
            key = status.split(":")[0]
            stats[key] = stats.get(key, 0) + 1
            if status == "model_unavailable":
                stats["model_unavailable"] = True
            done += 1
            if done % 25 == 0 or done == len(uids):
                print(f"  {done}/{len(uids)}  {_pretty(stats)}  ({time.time() - t0:.0f}s)")

        if workers <= 1:
            for i, uid in enumerate(uids):
                if (
                    has_quota
                    and i % BUDGET_CHECK_EVERY == 0
                    and budget_exhausted(ledger_conn, model_id, daily_quota, quota_fraction)
                ):
                    print(f"budget exhausted — parando gracioso em {i}/{len(uids)}.")
                    stats["budget_exhausted"] = True
                    break
                _, status, usage = process(uid)
                _consume(status, usage)
                if stats["model_unavailable"]:
                    print("modelo indisponível (EOL/inexistente) — abortando.")
                    break
        else:
            # Lotes de chunk_size para o governador poder parar entre lotes (um
            # `break` no as_completed não cancela futures já submetidas).
            chunk_size = max(workers * 2, BUDGET_CHECK_EVERY)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for chunk_start in range(0, len(uids), chunk_size):
                    if has_quota and budget_exhausted(
                        ledger_conn, model_id, daily_quota, quota_fraction
                    ):
                        print(f"budget exhausted — parando no lote {chunk_start}/{len(uids)}.")
                        stats["budget_exhausted"] = True
                        break
                    chunk_end = chunk_start + chunk_size
                    chunk = uids[chunk_start:chunk_end]
                    futs = [ex.submit(process, uid) for uid in chunk]
                    for fut in as_completed(futs):
                        _, status, usage = fut.result()
                        _consume(status, usage)
                    if stats["model_unavailable"]:
                        print("modelo indisponível (EOL/inexistente) — abortando.")
                        break

        print(f"FIM: {_pretty(stats)}  total={done}  {time.time() - t0:.0f}s")
        return stats
    finally:
        try:
            ledger_conn.close()
        except Exception:  # noqa: BLE001
            pass


def _pretty(stats: dict) -> dict:
    return {
        k: v for k, v in stats.items() if k not in ("budget_exhausted", "model_unavailable") or v
    }


def _missing_sentiment_line(missing: int, selected: int) -> str:
    return (
        f"sem_sentimento={missing} dos {selected} selecionados (fora do escopo do "
        "null-summary: o sentimento não é gerado aqui)"
    )


def _with_embedding_line(with_embedding: int, selected: int) -> str:
    return (
        f"com_embedding={with_embedding} dos {selected} selecionados (embedding feito "
        "sem o resumo; não é tocado aqui e o B3 só pega content_embedding IS NULL: "
        "exigem passo separado, ver o README do worker)"
    )


def _summary_only_gaps(missing_sentiment: int, with_embedding: int, selected: int) -> None:
    print(_missing_sentiment_line(missing_sentiment, selected))
    print(_with_embedding_line(with_embedding, selected))


def _today_brt() -> datetime.date:
    """Data de hoje no fuso BRT (America/Sao_Paulo)."""
    return datetime.datetime.now(BRT).date()


def _iso_date(value: str) -> str:
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"data inválida {value!r} (use AAAA-MM-DD)") from e


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--select",
        choices=SELECT_CHOICES,
        required=True,
        help="null-theme: tema NULL na janela; mock: summary LIKE '[MOCK]%%' na janela; "
        "null-summary: tema gravado e summary NULL na janela (só o resumo, prompt enxuto)",
    )
    ap.add_argument(
        "--date-from", type=_iso_date, required=True, help="dia BRT inicial (inclusivo)"
    )
    ap.add_argument(
        "--date-to",
        type=_iso_date,
        default=None,
        help="dia BRT final (EXCLUSIVO). Obrigatório com --select null-theme e "
        "null-summary, e no máximo hoje (BRT); opcional com --select mock",
    )
    ap.add_argument("--limit", type=int, default=500, help="teto de artigos neste run")
    ap.add_argument("--workers", type=int, default=1, help="concorrência de chamadas Bedrock")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="só seleciona e lista; não chama o Bedrock nem escreve nada",
    )
    return ap


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if not os.environ.get("DATABASE_URL"):
        print("ERRO: DATABASE_URL nao definida", file=sys.stderr)
        return 1

    model_id = os.environ.get("ENRICHMENT_MODEL_ID")
    if not model_id:
        print(
            "ERRO: ENRICHMENT_MODEL_ID nao definida (obrigatória; sem fallback para o "
            "default legado nem para BEDROCK_MODEL_ID)",
            file=sys.stderr,
        )
        return 1

    if args.date_to and args.date_to <= args.date_from:
        print("ERRO: --date-to (exclusivo) deve ser posterior a --date-from", file=sys.stderr)
        return 1

    if args.select in SELECTS_REQUIRING_DATE_TO:
        # Artigos novos sem tema são do worker ao vivo (que roda o NER e publica).
        today = _today_brt().isoformat()
        if not args.date_to:
            print(
                f"ERRO: --select {args.select} exige --date-to (exclusivo, no máximo hoje "
                f"BRT = {today}); {_EXAMPLE_WINDOW[args.select]}",
                file=sys.stderr,
            )
            return 1
        if args.date_to > today:
            print(
                f"ERRO: --date-to {args.date_to} passa de hoje BRT ({today}): a janela "
                "incluiria artigos que o worker ao vivo ainda vai processar",
                file=sys.stderr,
            )
            return 1

    quota_cfg = parse_daily_quota_env()
    daily_quota = quota_cfg["quota"].get(model_id)
    quota_fraction = quota_cfg["fraction"]

    print(
        f"ENRICHMENT_MODEL_ID={model_id!r}  select={args.select}  "
        f"janela=[{args.date_from}, {args.date_to or '…'}) BRT  dry_run={args.dry_run}  "
        f"cota={daily_quota}  fração={quota_fraction}"
    )

    summary_only = args.select == "null-summary"
    uids = get_window_uids(args.select, args.date_from, args.date_to, args.limit)
    print(f"selecionados={len(uids)} (limit={args.limit})")
    if not uids:
        print("nada pendente — concluido.")
        return 0

    if summary_only:
        missing_sentiment = count_missing_sentiment(uids)
        with_embedding = count_with_embedding(uids)
        _summary_only_gaps(missing_sentiment, with_embedding, len(uids))

    if args.dry_run:
        for uid in uids[:DRY_RUN_SAMPLE]:
            print(f"  {uid}")
        if len(uids) > DRY_RUN_SAMPLE:
            print(f"  … e mais {len(uids) - DRY_RUN_SAMPLE}")
        print("dry-run: nada foi classificado nem escrito.")
        return 0

    # Aquece os caches do handler antes das threads e confere o modelo em uso.
    classifier_model = handler._get_classifier().llm_client.model_id
    if classifier_model != model_id:
        print(
            f"ERRO: classificador usa {classifier_model!r}, esperado {model_id!r}",
            file=sys.stderr,
        )
        return 1
    if not summary_only:
        handler._get_code_to_id()  # null-summary não grava tema

    stats = run_reenrich(
        uids,
        model_id=model_id,
        daily_quota=daily_quota,
        quota_fraction=quota_fraction,
        workers=args.workers,
        process=process_one_summary if summary_only else process_one,
    )
    if summary_only:
        _summary_only_gaps(missing_sentiment, with_embedding, len(uids))
    return 1 if stats["model_unavailable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
