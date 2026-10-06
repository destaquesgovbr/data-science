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

Env obrigatórias: DATABASE_URL, ENRICHMENT_MODEL_ID (sem fallback para o default
legado nem para BEDROCK_MODEL_ID), creds AWS (AWS_BEDROCK_CONNECTION_URI ou
AWS_ACCESS_KEY_ID/SECRET). Opcionais: BEDROCK_DAILY_TOKEN_QUOTA (JSON
{model_id: tokens/dia}), BACKFILL_QUOTA_FRACTION.

Uso (sempre --dry-run → --limit 10 → completo, cada etapa com OK):
    ENRICHMENT_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \\
    PYTHONPATH=src .venv/bin/python scripts/reenrich_combined_window.py \\
        --select null-theme --date-from 2026-09-25 --date-to 2026-10-06 \\
        [--limit 500] [--workers 1] [--dry-run]
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

SELECT_CHOICES = ("null-theme", "mock")
# Seleções que disputam artigos com o worker ao vivo: exigem --date-to <= hoje BRT.
SELECTS_REQUIRING_DATE_TO = frozenset({"null-theme"})
BRT = ZoneInfo("America/Sao_Paulo")
MOCK_SUMMARY_PATTERN = "[MOCK]%"
# Checa o budget a cada N artigos (tolera pequena ultrapassagem; margem ~fração).
BUDGET_CHECK_EVERY = 5
DRY_RUN_SAMPLE = 20
_ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0}

# Limites da janela: meia-noite do dia em BRT, convertida para timestamptz.
_BRT_DAY_START = "(%({param})s::date::timestamp AT TIME ZONE 'America/Sao_Paulo')"


def build_select_sql(select: str, with_date_to: bool) -> str:
    """SELECT da janela: `null-theme` (tema NULL) ou `mock` (summary '[MOCK]%').

    Parâmetros nomeados (ver build_select_params). Ordem: mais recentes primeiro.
    `null-theme` sem teto (with_date_to=False) é recusado: ver o docstring do módulo.
    """
    if select in SELECTS_REQUIRING_DATE_TO and not with_date_to:
        raise ValueError(f"--select {select} exige --date-to (teto da janela)")
    if select == "null-theme":
        predicate = "n.most_specific_theme_id IS NULL"
    elif select == "mock":
        predicate = "n.summary LIKE %(mock_pattern)s"
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
) -> dict:
    """Processa uids com governador de cota. Resumível e capado.

    Para em budget_exhausted (parada graciosa) ou no primeiro modelo
    indisponível. Sem cota (None/<=0) → modo sem-teto (apenas grava o ledger).
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
                _, status, usage = process_one(uid)
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
                    futs = [ex.submit(process_one, uid) for uid in chunk]
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
        help="null-theme: tema NULL na janela; mock: summary LIKE '[MOCK]%%' na janela",
    )
    ap.add_argument(
        "--date-from", type=_iso_date, required=True, help="dia BRT inicial (inclusivo)"
    )
    ap.add_argument(
        "--date-to",
        type=_iso_date,
        default=None,
        help="dia BRT final (EXCLUSIVO). Obrigatório com --select null-theme e no "
        "máximo hoje (BRT); opcional com --select mock",
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
                f"BRT = {today}); no B2: --date-from 2026-09-25 --date-to 2026-10-06",
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

    uids = get_window_uids(args.select, args.date_from, args.date_to, args.limit)
    print(f"selecionados={len(uids)} (limit={args.limit})")
    if not uids:
        print("nada pendente — concluido.")
        return 0

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
    handler._get_code_to_id()

    stats = run_reenrich(
        uids,
        model_id=model_id,
        daily_quota=daily_quota,
        quota_fraction=quota_fraction,
        workers=args.workers,
    )
    return 1 if stats["model_unavailable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
