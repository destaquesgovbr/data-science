#!/usr/bin/env python3
"""
Backfill NER do ACERVO COMPLETO: extrai entidades (Sonnet 4.6 via NER_MODEL_ID)
de TODA notícia que ainda NÃO tem NER na prompt_version atual — incluindo os
~314k artigos que nunca foram NERados (não só os já-enriquecidos).

Diferença vs `scripts/renew_ner_window.py` (que re-NERa uma janela já-enriquecida):
  - SELECT cobre o acervo inteiro: `news` SEM `news_llm_raw` task='ner' na
    prompt_version atual, via `NOT EXISTS` (há índice em news_llm_raw); NÃO exige
    que o artigo já tenha features.entities.
  - `_upsert_ai_features` faz INSERT-on-conflict — cria a linha de news_features
    quando ela não existe (idempotente).
  - Governador de cota: para gracioso quando o consumo do dia (account-wide, por
    modelo) bate `fração × cota` (quota_governor). Resumível: roda de novo amanhã.

Mirror do caminho do worker (handler.enrich_article):
    entities, ner_raw = classifier.llm_client.extract_entities(article, return_raw=True)
    store_raw_llm_response(uid, "ner", ner_raw)
    _upsert_ai_features(uid, {"entities": entities})

Segurança:
  - Falha de NER (ner_raw None / entities []) NUNCA apaga entidades existentes
    (`_upsert_ai_features` só grava `entities` quando não-vazia, via merge `||`).
  - Os tokens de TODA chamada são gravados no ledger (record_usage), inclusive
    as do worker ao vivo — o governador mede o pool compartilhado do modelo.

Env necessárias: DATABASE_URL, NER_MODEL_ID, creds AWS (AWS_BEDROCK_CONNECTION_URI
ou AWS_ACCESS_KEY_ID/SECRET), e (opcional) BEDROCK_DAILY_TOKEN_QUOTA / BACKFILL_QUOTA_FRACTION.

Uso:
    PYTHONPATH=src .venv/bin/python scripts/backfill_ner_corpus.py \
        --limit 500 --order asc [--workers 4] [--dry-run]
"""
import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from news_enrichment.llm_client import NER_PROMPT_VERSION  # noqa: E402
from news_enrichment.quota_governor import (  # noqa: E402
    budget_exhausted,
    parse_daily_quota_env,
    record_usage,
)
from news_enrichment.worker import handler  # noqa: E402

# Checa o budget a cada N artigos (tolera pequena ultrapassagem; margem ~fração).
BUDGET_CHECK_EVERY = 5
_ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0}


def build_select_sql(order: str) -> str:
    """SELECT resumível do acervo: news SEM NER na prompt_version atual.

    `NOT EXISTS` sobre news_llm_raw(unique_id, task, prompt_version) — há índice;
    NÃO exige features.entities (cobre os ~314k nunca NERados). Ordem por
    published_at (asc=oldest-first default).
    """
    order_sql = "DESC" if order == "desc" else "ASC"
    return f"""
        SELECT n.unique_id
        FROM news n
        WHERE NOT EXISTS (
            SELECT 1 FROM news_llm_raw r
            WHERE r.unique_id = n.unique_id
              AND r.task = 'ner'
              AND r.prompt_version = %s
        )
        ORDER BY n.published_at {order_sql}
        LIMIT %s
    """


def _get_conn():
    """Conexão psycopg2 (separada para ler ledger / selecionar uids)."""
    return psycopg2.connect(handler._get_database_url())


def get_corpus_uids(limit: int, order: str) -> list[str]:
    """uids do acervo ainda sem NER na prompt_version atual."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(build_select_sql(order), (NER_PROMPT_VERSION, limit))
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def process_one(uid: str, dry_run: bool):
    """Processa um artigo. Retorna (uid, status, usage).

    usage = {input_tokens, output_tokens} da chamada NER (para o ledger de cota).
    """
    article = handler.fetch_article(uid)
    if not article:
        return uid, "missing", dict(_ZERO_USAGE)
    try:
        entities, ner_raw = handler._get_classifier().llm_client.extract_entities(
            article, return_raw=True
        )
    except Exception as e:  # transient Bedrock/etc — não mexe nas entidades antigas
        return uid, f"error:{type(e).__name__}", dict(_ZERO_USAGE)

    usage = dict(_ZERO_USAGE)
    if ner_raw is not None:
        usage = ner_raw.get("usage") or dict(_ZERO_USAGE)

    if ner_raw is None:
        return uid, "ner_failed", usage  # falha — não mexe nas entidades existentes
    if dry_run:
        return uid, f"dry:{len(entities)}ent", usage
    handler._upsert_ai_features(uid, {"entities": entities})
    handler.store_raw_llm_response(uid, "ner", ner_raw)
    return uid, f"ok:{len(entities)}ent", usage


def _record_usage_for(conn, model_id: str, usage: dict) -> None:
    """Grava o usage de uma chamada no ledger (se não-zero)."""
    if not usage:
        return
    in_tok = usage.get("input_tokens") or 0
    out_tok = usage.get("output_tokens") or 0
    if in_tok or out_tok:
        record_usage(conn, model_id, in_tok, out_tok)


def run_backfill(
    uids: list[str],
    *,
    model_id: str,
    daily_quota,
    quota_fraction: float,
    workers: int,
    dry_run: bool,
) -> dict:
    """Processa uids com governador de cota. Resumível e capado.

    Sem cota (daily_quota None/<=0) → modo sem-teto (apenas grava o ledger).
    """
    stats: dict = {"budget_exhausted": False}
    has_quota = bool(daily_quota and daily_quota > 0)
    if not has_quota:
        print(f"AVISO: sem cota diária para {model_id!r} — modo sem-teto.")

    ledger_conn = _get_conn()
    try:
        t0 = time.time()
        done = 0

        def _tally(status: str) -> None:
            key = status.split(":")[0]
            stats[key] = stats.get(key, 0) + 1

        if workers <= 1:
            for i, uid in enumerate(uids):
                if has_quota and i % BUDGET_CHECK_EVERY == 0 and budget_exhausted(
                    ledger_conn, model_id, daily_quota, quota_fraction
                ):
                    print(f"budget exhausted — parando gracioso em {i}/{len(uids)}.")
                    stats["budget_exhausted"] = True
                    break
                _, status, usage = process_one(uid, dry_run)
                if not dry_run:
                    _record_usage_for(ledger_conn, model_id, usage)
                _tally(status)
                done += 1
                if done % 25 == 0 or done == len(uids):
                    print(f"  {done}/{len(uids)}  {_pretty(stats)}  ({time.time()-t0:.0f}s)")
        else:
            # Concorrência com controle de cota: submete em lotes de chunk_size para
            # que o governador possa parar entre lotes. Submeter todos de uma vez e
            # fazer `break` do as_completed NÃO cancela futures — shutdown(wait=True)
            # executa tudo na saída do `with`, anulando o teto de 80% de cota.
            chunk_size = max(workers * 2, BUDGET_CHECK_EVERY)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for chunk_start in range(0, len(uids), chunk_size):
                    if has_quota and budget_exhausted(
                        ledger_conn, model_id, daily_quota, quota_fraction
                    ):
                        print(
                            f"budget exhausted — parando no lote {chunk_start}/{len(uids)}."
                        )
                        stats["budget_exhausted"] = True
                        break
                    chunk = uids[chunk_start : chunk_start + chunk_size]
                    futs = {ex.submit(process_one, uid, dry_run): uid for uid in chunk}
                    for fut in as_completed(futs):
                        _, status, usage = fut.result()
                        if not dry_run:
                            _record_usage_for(ledger_conn, model_id, usage)
                        _tally(status)
                        done += 1
                        if done % 25 == 0:
                            print(
                                f"  {done}/{len(uids)}  {_pretty(stats)}  ({time.time()-t0:.0f}s)"
                            )

        print(f"FIM: {_pretty(stats)}  total={done}  {time.time()-t0:.0f}s")
        return stats
    finally:
        try:
            ledger_conn.close()
        except Exception:
            pass


def _pretty(stats: dict) -> dict:
    return {k: v for k, v in stats.items() if k != "budget_exhausted" or v}


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=500, help="teto de artigos neste run")
    ap.add_argument("--workers", type=int, default=1, help="concorrência de chamadas Bedrock")
    ap.add_argument(
        "--order", choices=["asc", "desc"], default="asc",
        help="ordem por published_at (asc=oldest-first, cobre o acervo histórico)",
    )
    ap.add_argument("--dry-run", action="store_true", help="não escreve nada (lê só)")
    return ap


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if not os.environ.get("DATABASE_URL"):
        print("ERRO: DATABASE_URL nao definida", file=sys.stderr)
        return 1

    model_id = os.environ.get("NER_MODEL_ID")
    if not model_id:
        print("ERRO: NER_MODEL_ID nao definida", file=sys.stderr)
        return 1

    quota_cfg = parse_daily_quota_env()
    daily_quota = quota_cfg["quota"].get(model_id)
    quota_fraction = quota_cfg["fraction"]

    print(
        f"NER_MODEL_ID={model_id!r}  prompt_version={NER_PROMPT_VERSION}  "
        f"dry_run={args.dry_run}  cota={daily_quota}  fração={quota_fraction}"
    )

    uids = get_corpus_uids(args.limit, args.order)
    print(f"selecionados={len(uids)} (order={args.order}, limit={args.limit})")
    if not uids:
        print("nada pendente — concluido.")
        return 0

    run_backfill(
        uids,
        model_id=model_id,
        daily_quota=daily_quota,
        quota_fraction=quota_fraction,
        workers=args.workers,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
