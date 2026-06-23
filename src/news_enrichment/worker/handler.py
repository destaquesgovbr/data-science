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

from news_enrichment import quota_governor
from news_enrichment.classifier import NewsClassifier
from news_enrichment.enrichment_job import update_news_enrichment
from news_enrichment.llm_client import check_summary_safety
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
        # Modelo combinado (tema+resumo+sentimento) — configurável.
        # ENRICHMENT_MODEL_ID é o nome preferido; BEDROCK_MODEL_ID mantido por
        # retrocompatibilidade com o env atual.
        enrichment_model_id = (
            os.environ.get("ENRICHMENT_MODEL_ID")
            or os.environ.get("BEDROCK_MODEL_ID")
            or "anthropic.claude-3-haiku-20240307-v1:0"
        )
        # Modelo NER dedicado (Sonnet 4.6 em prod) — configurável via NER_MODEL_ID.
        # Em prod o Terraform define o inference-profile id do Sonnet 4.6 (us-east-1).
        ner_model_id = os.environ.get("NER_MODEL_ID") or enrichment_model_id
        _classifier = NewsClassifier(
            model_id=enrichment_model_id,
            ner_model_id=ner_model_id,
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

    # Classify (chamada COMBINADA: tema + resumo + sentimento)
    classifier = _get_classifier()
    result = classifier.classify_single(article, return_format="dict")

    if not result:
        logger.warning(f"Classification failed for {unique_id}")
        return {"status": "classification_failed"}

    # Ensure unique_id is in result for update_news_enrichment
    result["unique_id"] = unique_id

    # Content Safety: Verificar segurança do resumo gerado
    summary = result.get("summary")
    if summary:
        is_safe, blocked_reason = check_summary_safety(
            summary, classifier.llm_client.bedrock_client, classifier.llm_client.model_id
        )
        if not is_safe:
            logger.warning(f"Summary blocked for {unique_id}: {blocked_reason}")
            # Remove o resumo do result para não gravar no PostgreSQL
            result.pop("summary", None)
            # Adiciona flags de bloqueio para gravar na tabela news
            result["summary_blocked"] = True
            result["summary_blocked_reason"] = blocked_reason
            result["summary_blocked_at"] = datetime.now(timezone.utc)
        else:
            logger.info(f"Summary approved for {unique_id}")
            result["summary_blocked"] = False

    # NER (chamada DEDICADA, modelo Sonnet 4.6 em prod). Resiliente: uma falha
    # no NER não derruba o enriquecimento de tema/sentimento.
    ner_raw: dict | None = None
    try:
        entities, ner_raw = classifier.llm_client.extract_entities(
            article, return_raw=True
        )
        result["entities"] = entities
        # Grava a resposta crua em news_llm_raw (não fatal se falhar).
        store_raw_llm_response(unique_id, "ner", ner_raw)
    except Exception as e:
        logger.error(f"NER extraction failed for {unique_id}: {e}")
        result["entities"] = []

    # Ledger de cota: registra os tokens consumidos (chamada combinada + NER).
    # O worker SÓ ESCREVE no ledger — NUNCA se auto-limita (ele atende o tempo
    # real; só os jobs de backfill cedem quando o consumo do dia bate o teto).
    _record_ledger_usage(result, ner_raw)

    # Update PostgreSQL
    code_to_id = _get_code_to_id()
    stats = update_news_enrichment(_get_database_url(), [result], code_to_id)

    # Upsert sentiment + entities to news_features
    _upsert_ai_features(unique_id, result)

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


def _normalize_mention(raw: dict) -> dict:
    """
    Garante o shape evoluído da menção em news_features.features.entities[]:
    {text, type, count, forma_canonica, salience}.

    canonical_id e offsets ficam DE FORA (preenchidos por fases posteriores).
    """
    text = raw.get("text")
    count = raw.get("count", 1)
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 1
    salience = raw.get("salience")
    forma_canonica = raw.get("forma_canonica") or text
    return {
        "text": text,
        "type": raw.get("type"),
        "count": count,
        "forma_canonica": forma_canonica,
        "salience": salience,
    }


def _upsert_ai_features(unique_id: str, enrichment_result: dict) -> None:
    """Upsert AI-computed features (sentiment, entities) to news_features table."""
    from psycopg2.extras import Json

    features = {}
    sentiment = enrichment_result.get("sentiment")
    if sentiment and sentiment.get("label"):
        features["sentiment"] = sentiment
    entities = enrichment_result.get("entities")
    if entities:
        # Shape evoluído: {text, type, count, forma_canonica, salience}.
        features["entities"] = [_normalize_mention(e) for e in entities]

    if not features:
        return

    db_url = _get_database_url()
    conn = psycopg2.connect(db_url)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO news_features (unique_id, features)
            VALUES (%s, %s)
            ON CONFLICT (unique_id) DO UPDATE SET
                features = news_features.features || EXCLUDED.features
            """,
            (unique_id, Json(features)),
        )
        conn.commit()
        cursor.close()
        logger.info(f"Upserted AI features for {unique_id}: {list(features.keys())}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to upsert AI features for {unique_id}: {e}")
    finally:
        conn.close()


def _record_ledger_usage(combined_result: dict, ner_raw: dict | None) -> None:
    """Grava no ledger llm_daily_usage os tokens das chamadas Bedrock do worker.

    Escreve duas linhas (uma por modelo): a chamada combinada (tema+resumo+
    sentimento, modelo `_model_id`) e a chamada NER (modelo do ner_raw). Cada
    UPSERT acumula sobre o consumo do dia (quota_governor.record_usage).

    RESILIENTE: o worker NUNCA se auto-limita e uma falha aqui jamais derruba o
    enriquecimento — abre uma conexão própria e ignora qualquer erro.
    """
    entries: list[tuple[str, dict]] = []

    combined_usage = (combined_result or {}).get("_usage")
    combined_model = (combined_result or {}).get("_model_id")
    if combined_usage and combined_model:
        entries.append((combined_model, combined_usage))

    if ner_raw:
        ner_usage = ner_raw.get("usage")
        ner_model = ner_raw.get("model_id")
        if ner_usage and ner_model:
            entries.append((ner_model, ner_usage))

    if not entries:
        return

    try:
        conn = psycopg2.connect(_get_database_url())
    except Exception as e:
        logger.warning(f"Failed to connect to record ledger usage: {e}")
        return
    try:
        for model_id, usage in entries:
            quota_governor.record_usage(
                conn,
                model_id,
                usage.get("input_tokens"),
                usage.get("output_tokens"),
            )
    finally:
        try:
            conn.close()
        except Exception:
            pass


def store_raw_llm_response(unique_id: str, task: str, raw: dict | None) -> None:
    """
    Append-only: grava a resposta crua do LLM em news_llm_raw para
    reprocessabilidade (re-parse sem re-chamar o Bedrock).

    Resiliente: qualquer falha (tabela ausente, DB indisponível) é logada e
    ignorada — NUNCA derruba o enriquecimento. `raw` None (chamada Bedrock
    falhou) é no-op.

    Args:
        unique_id: ID da notícia.
        task: rótulo da tarefa, ex.: 'ner'.
        raw: dict com model_id, prompt_version, prompt_hash, raw_response.

    A tabela news_llm_raw é criada pela migração 019 do data-platform.
    """
    if not raw:
        return

    from psycopg2.extras import Json

    try:
        conn = psycopg2.connect(_get_database_url())
    except Exception as e:
        logger.warning(f"Failed to connect to store raw LLM response for {unique_id}: {e}")
        return

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO news_llm_raw
                (unique_id, task, model_id, prompt_version, prompt_hash, raw_response)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                unique_id,
                task,
                raw.get("model_id"),
                raw.get("prompt_version"),
                raw.get("prompt_hash"),
                Json(raw.get("raw_response")),
            ),
        )
        conn.commit()
        cursor.close()
        logger.info(f"Stored raw LLM response for {unique_id} (task={task})")
    except Exception as e:
        # Não fatal: o enriquecimento continua mesmo sem o raw armazenado.
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning(f"Failed to store raw LLM response for {unique_id} (task={task}): {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
