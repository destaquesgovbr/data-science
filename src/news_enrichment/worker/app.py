"""
Enrichment Worker — FastAPI application.

Cloud Run service that receives Pub/Sub push messages from
dgb.news.scraped topic, classifies news via Bedrock, updates
PostgreSQL, and publishes dgb.news.enriched events.
"""

import base64
import json
import logging

from fastapi import FastAPI, Request, Response

from news_enrichment.worker.handler import enrich_article

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Enrichment Worker", version="1.0.0")


@app.get("/health")
def health() -> dict:
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

    Returns 200 to ACK, 400 for bad requests.
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
    logger.info(f"Processing {unique_id} (trace={trace_id})")

    try:
        result = enrich_article(unique_id)
        logger.info(f"Result for {unique_id}: {result['status']}")
        return Response(status_code=200, content=json.dumps(result))
    except Exception as e:
        logger.error(f"Unhandled error for {unique_id}: {e}", exc_info=True)
        # ACK to avoid infinite retries — reconciliation DAG will catch it
        return Response(status_code=200, content=f"ACK (error: {e})")
