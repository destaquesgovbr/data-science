"""
Enrichment Worker — FastAPI application.

Cloud Run service that receives Pub/Sub push messages from
dgb.news.scraped topic, classifies news via Bedrock, updates
PostgreSQL, and publishes dgb.news.enriched events.

Concorrência: o `enrich_article` é síncrono (boto3/Bedrock + psycopg2) e roda num
executor de threads dedicado, nunca no event loop. Antes (até a revisão 00026) o
`/process` o chamava direto dentro de um endpoint `async`: a instância processava uma
mensagem por vez e o `/health` ficava sem resposta durante a rajada, até o liveness
matar a instância (incidentes de 26/10, 29/10 e 02/11/2026). O `/health` é `async` e
responde no próprio event loop, sem depender de thread livre.
"""

import asyncio
import base64
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from fastapi import FastAPI, Request, Response

from news_enrichment.worker.handler import RetryableEnrichmentError, enrich_article

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Threads de trabalho por instância. Deve acompanhar o max_instance_request_concurrency
# do Cloud Run (infra/terraform/enrichment-worker.tf); requisições além disso esperam
# no executor sem bloquear o event loop.
WORKER_THREADS = int(os.environ.get("ENRICHMENT_WORKER_THREADS", "4"))
_executor = ThreadPoolExecutor(max_workers=WORKER_THREADS, thread_name_prefix="enrich-worker")

app = FastAPI(title="Enrichment Worker", version="1.0.0")


def _delivery_attempt(envelope: dict) -> int | None:
    """Número da tentativa de entrega (o push manda `deliveryAttempt` com dead-letter policy)."""
    try:
        value = int(envelope.get("deliveryAttempt"))
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else None


@app.get("/health")
async def health() -> dict:
    # `async` de propósito: responde no event loop, sem esperar thread do pool.
    return {"status": "ok"}


@app.post("/process")
async def process(request: Request) -> Response:
    """
    Handle Pub/Sub push message from dgb.news.scraped.

    Pub/Sub sends:
    {
      "message": {
        "data": "<base64 JSON with unique_id>",
        "attributes": {"trace_id": "...", "event_version": "1.0"},
        "messageId": "..."
      }
    }

    Returns 200 to ACK, 400 for bad requests, 503 on RetryableEnrichmentError
    (e.g. dgb.news.enriched not confirmed; Pub/Sub redelivers and the handler
    republishes).
    """
    try:
        envelope = await request.json()
    except Exception:
        return Response(status_code=400, content="Invalid JSON")

    message = envelope.get("message", {})
    data_b64 = message.get("data")
    if not data_b64:
        return Response(status_code=400, content="No data")

    try:
        payload = json.loads(base64.b64decode(data_b64))
    except Exception:
        return Response(status_code=400, content="Invalid data encoding")

    unique_id = payload.get("unique_id")
    if not unique_id:
        return Response(status_code=400, content="Missing unique_id")

    trace_id = message.get("attributes", {}).get("trace_id", "")
    delivery_attempt = _delivery_attempt(envelope)
    logger.info(f"Processing {unique_id} (trace={trace_id}, attempt={delivery_attempt})")

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            _executor, partial(enrich_article, unique_id, delivery_attempt=delivery_attempt)
        )
        logger.info(f"Result for {unique_id}: {result['status']}")
        return Response(status_code=200, content=json.dumps(result))
    except RetryableEnrichmentError as e:
        # Ex.: publish do enriched não confirmado. Tema/resumo podem já estar gravados:
        # sem o evento, o artigo fica sem embedding e fora do Typesense. NACK → o
        # Pub/Sub reentrega e o handler republica no caminho already_enriched.
        logger.error(f"Retryable failure for {unique_id}, NACK: {e}")
        return Response(status_code=503, content=f"NACK ({e})")
    except Exception as e:
        logger.error(f"Unhandled error for {unique_id}: {e}", exc_info=True)
        # ACK to avoid infinite retries — reconciliation DAG will catch it
        return Response(status_code=200, content=f"ACK (error: {e})")
