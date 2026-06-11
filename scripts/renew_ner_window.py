#!/usr/bin/env python3
"""
Re-NER de uma janela de noticias (fatia de ~1 mes), newest-first, capado e resumivel.

Reprocessa as entidades com o NER NOVO (Sonnet 4.6 via NER_MODEL_ID), substituindo
as entidades antigas. NAO roda tema/resumo/sentimento — apenas o NER dedicado.

Mirror exato do caminho do worker (handler.enrich_article):
    entities, ner_raw = classifier.llm_client.extract_entities(article, return_raw=True)
    store_raw_llm_response(uid, "ner", ner_raw)
    _upsert_ai_features(uid, {"entities": entities})

Seguranca:
  - `_upsert_ai_features` so grava a chave `entities` quando NAO vazia (merge `||`),
    entao uma falha de NER (ner_raw None / entities []) NUNCA apaga entidades boas.
  - Resumivel: pula uids que ja tem news_llm_raw task='ner' na prompt_version atual.
  - Capado por --limit; ordene newest-first por padrao (--order desc).

Env necessarias: DATABASE_URL, NER_MODEL_ID, e creds AWS (AWS_BEDROCK_CONNECTION_URI
ou AWS_ACCESS_KEY_ID/SECRET) — o handler parseia via _get_classifier().

Uso:
    PYTHONPATH=src .venv/bin/python scripts/renew_ner_window.py --days 30 --limit 50 --order desc [--workers 4] [--dry-run]
"""
import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from news_enrichment.llm_client import NER_PROMPT_VERSION  # noqa: E402
from news_enrichment.worker import handler  # noqa: E402


def get_window_uids(days: int, limit: int, order: str) -> list[str]:
    """uids da janela (published_at >= now-days), ja-enriquecidos e ainda nao
    re-NERados na prompt_version atual, ordenados por data."""
    order_sql = "DESC" if order == "desc" else "ASC"
    conn = psycopg2.connect(handler._get_database_url())
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT n.unique_id
            FROM news n
            JOIN news_features nf ON nf.unique_id = n.unique_id
            WHERE n.published_at >= NOW() - (%s || ' days')::interval
              AND nf.features ? 'entities'
              AND NOT EXISTS (
                  SELECT 1 FROM news_llm_raw r
                  WHERE r.unique_id = n.unique_id
                    AND r.task = 'ner'
                    AND r.prompt_version = %s
              )
            ORDER BY n.published_at {order_sql}
            LIMIT %s
            """,
            (str(days), NER_PROMPT_VERSION, limit),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def process_one(uid: str, dry_run: bool) -> tuple[str, str]:
    article = handler.fetch_article(uid)
    if not article:
        return uid, "missing"
    try:
        entities, ner_raw = handler._get_classifier().llm_client.extract_entities(
            article, return_raw=True
        )
    except Exception as e:  # transient Bedrock/etc — leave old entities intact
        return uid, f"error:{type(e).__name__}"
    if ner_raw is None:
        return uid, "ner_failed"  # falha — nao mexe nas entidades existentes
    if dry_run:
        return uid, f"dry:{len(entities)}ent"
    handler._upsert_ai_features(uid, {"entities": entities})
    handler.store_raw_llm_response(uid, "ner", ner_raw)
    return uid, f"ok:{len(entities)}ent"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30, help="janela: ultimos N dias")
    ap.add_argument("--limit", type=int, default=50, help="teto de artigos neste run")
    ap.add_argument("--workers", type=int, default=1, help="concorrencia de chamadas Bedrock")
    ap.add_argument("--order", choices=["desc", "asc"], default="desc", help="ordem por published_at")
    ap.add_argument("--dry-run", action="store_true", help="nao escreve nada nem chama Bedrock em escrita")
    args = ap.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERRO: DATABASE_URL nao definida", file=sys.stderr)
        return 1
    ner_model = os.environ.get("NER_MODEL_ID")
    print(f"NER_MODEL_ID={ner_model!r}  prompt_version={NER_PROMPT_VERSION}  dry_run={args.dry_run}")

    uids = get_window_uids(args.days, args.limit, args.order)
    print(f"janela={args.days}d  selecionados={len(uids)} (order={args.order}, limit={args.limit})")
    if not uids:
        print("nada pendente — concluido.")
        return 0

    t0 = time.time()
    counts: dict[str, int] = {}
    done = 0
    if args.workers <= 1:
        for uid in uids:
            _, status = process_one(uid, args.dry_run)
            key = status.split(":")[0]
            counts[key] = counts.get(key, 0) + 1
            done += 1
            if done % 25 == 0 or done == len(uids):
                print(f"  {done}/{len(uids)}  {counts}  ({time.time()-t0:.0f}s)")
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(process_one, uid, args.dry_run): uid for uid in uids}
            for fut in as_completed(futs):
                _, status = fut.result()
                key = status.split(":")[0]
                counts[key] = counts.get(key, 0) + 1
                done += 1
                if done % 25 == 0 or done == len(uids):
                    print(f"  {done}/{len(uids)}  {counts}  ({time.time()-t0:.0f}s)")

    print(f"FIM: {counts}  total={done}  {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
