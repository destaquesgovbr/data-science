"""
Enrichment Worker — business logic.

Fetches a single news article from PostgreSQL, classifies it
via Bedrock (themes + summary), updates PostgreSQL, and publishes
a dgb.news.enriched event to Pub/Sub.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import psycopg2

from news_enrichment.classifier import NewsClassifier
from news_enrichment.enrichment_job import update_news_enrichment
from news_enrichment.taxonomy import build_theme_code_to_id_map, load_taxonomy_from_postgres

logger = logging.getLogger(__name__)

# Cached objects (initialized once, reused across requests)
_classifier: NewsClassifier | None = None
_code_to_id: dict[str, int] | None = None


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return url


def _parse_aws_credentials() -> tuple[str | None, str | None, str | None]:
    """Extract AWS credentials from env vars or Airflow-style connection URI.

    Supports:
      - Individual env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
      - Airflow URI: aws://ACCESS_KEY:SECRET_KEY@/?region_name=us-east-1
    """
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_REGION", "us-east-1")

    if access_key and secret_key:
        return access_key, secret_key, region

    # Fallback: parse Airflow connection URI
    conn_uri = os.environ.get("AWS_BEDROCK_CONNECTION_URI", "")
    if conn_uri:
        parsed = urlparse(conn_uri)
        access_key = unquote(parsed.username) if parsed.username else None
        secret_key = unquote(parsed.password) if parsed.password else None
        qs = parse_qs(parsed.query)
        region = qs.get("region_name", [region])[0]
        logger.info("Parsed AWS credentials from AWS_BEDROCK_CONNECTION_URI")

    return access_key, secret_key, region


def _get_classifier() -> NewsClassifier:
    """Lazy-init classifier with taxonomy from PG."""
    global _classifier
    if _classifier is None:
        database_url = _get_database_url()
        taxonomy = load_taxonomy_from_postgres(database_url)
        aws_access_key, aws_secret_key, aws_region = _parse_aws_credentials()
        _classifier = NewsClassifier(
            model_id=os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
            ),
            region=aws_region,
            taxonomy=taxonomy,
            batch_size=1,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
        )
        logger.info("NewsClassifier initialized")
    return _classifier


def _get_code_to_id() -> dict[str, int]:
    """Lazy-init theme code → id mapping."""
    global _code_to_id
    if _code_to_id is None:
        _code_to_id = build_theme_code_to_id_map(_get_database_url())
        logger.info(f"Theme code_to_id loaded: {len(_code_to_id)} entries")
    return _code_to_id


def fetch_article(unique_id: str) -> dict | None:
    """Fetch article fields needed for classification."""
    database_url = _get_database_url()
    conn = psycopg2.connect(database_url)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT unique_id, title, subtitle, editorial_lead, content
            FROM news
            WHERE unique_id = %s
            """,
            (unique_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    finally:
        conn.close()


def is_already_enriched(unique_id: str) -> bool:
    """Check if article already has theme classification (idempotency)."""
    database_url = _get_database_url()
    conn = psycopg2.connect(database_url)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT most_specific_theme_id FROM news WHERE unique_id = %s",
            (unique_id,),
        )
        row = cursor.fetchone()
        return row is not None and row[0] is not None
    finally:
        conn.close()


def publish_enriched_event(unique_id: str, most_specific_theme_code: str | None, has_summary: bool) -> None:
    """Publish dgb.news.enriched event to Pub/Sub."""
    topic = os.environ.get("PUBSUB_TOPIC_NEWS_ENRICHED")
    if not topic:
        logger.debug("PUBSUB_TOPIC_NEWS_ENRICHED not set — skipping publish")
        return

    try:
        from google.cloud import pubsub_v1

        client = pubsub_v1.PublisherClient()
        message = {
            "unique_id": unique_id,
            "enriched_at": datetime.now(timezone.utc).isoformat(),
            "most_specific_theme_code": most_specific_theme_code or "",
            "has_summary": has_summary,
        }
        client.publish(
            topic,
            json.dumps(message).encode("utf-8"),
            trace_id=str(uuid.uuid4()),
            event_version="1.0",
        )
        logger.info(f"Published dgb.news.enriched for {unique_id}")
    except Exception as e:
        logger.warning(f"Failed to publish enriched event for {unique_id}: {e}")


def enrich_article(unique_id: str) -> dict[str, Any]:
    """
    Full enrichment pipeline for a single article.

    Returns:
        Dict with status and stats.
    """
    # Idempotency check
    if is_already_enriched(unique_id):
        logger.info(f"Already enriched: {unique_id}")
        return {"status": "skipped", "reason": "already_enriched"}

    # Fetch article
    article = fetch_article(unique_id)
    if article is None:
        logger.warning(f"Article not found: {unique_id}")
        return {"status": "not_found"}

    # Classify
    classifier = _get_classifier()
    result = classifier.classify_single(article, return_format="dict")

    if not result:
        logger.warning(f"Classification failed for {unique_id}")
        return {"status": "classification_failed"}

    # Ensure unique_id is in result for update_news_enrichment
    result["unique_id"] = unique_id

    # Update PostgreSQL
    code_to_id = _get_code_to_id()
    stats = update_news_enrichment(_get_database_url(), [result], code_to_id)

    if stats["updated"] == 0:
        logger.warning(f"No update for {unique_id}: {stats}")
        return {"status": "update_failed", "stats": stats}

    # Publish event
    publish_enriched_event(
        unique_id,
        result.get("most_specific_theme_code"),
        bool(result.get("summary")),
    )

    return {"status": "enriched", "stats": stats}
