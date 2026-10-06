"""
Enrichment Worker — business logic.

Fetches a single news article from PostgreSQL, classifies it
via Bedrock (themes + summary), updates PostgreSQL, and publishes
a dgb.news.enriched event to Pub/Sub.

Linhas de log estáveis (para métricas/alertas baseados em log; ver README.md):
  - ERROR    enrichment_combined_failed uid=<uid> model=<id> error=<ErrorCode>: <msg>
  - CRITICAL enrichment_model_unavailable model=<id> error_code=<ErrorCode>
  - ERROR    enrichment_update_failed uid=<uid> model=<id> stats=<stats>
  - ERROR    enrichment_model_env_missing default=<id> ...
  - INFO     enrichment_ner uid=<uid> status=<ran|failed|skipped_already_done> model=<id>
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
from news_enrichment.llm_client import DEFAULT_ENRICHMENT_MODEL_ID, is_model_unavailable_error
from news_enrichment.taxonomy import build_theme_code_to_id_map, load_taxonomy_from_postgres

logger = logging.getLogger(__name__)

# Cached objects (initialized once, reused across requests)
_classifier: NewsClassifier | None = None
_code_to_id: dict[str, int] | None = None

# Campos de tema da chamada combinada: todos nulos = a classificação falhou.
_THEME_CODE_FIELDS = (
    "theme_1_level_1_code",
    "theme_1_level_2_code",
    "theme_1_level_3_code",
    "most_specific_theme_code",
)

# "NER já feito" para o uid: entidades gravadas em news_features OU resposta crua
# de NER em news_llm_raw (cobre NER que respondeu sem entidades). Índice
# idx_news_llm_raw_unique_id_task (migração 019 do data-platform).
_NER_ALREADY_DONE_SQL = """
    SELECT EXISTS (
        SELECT 1 FROM news_features nf
        WHERE nf.unique_id = %s AND nf.features ? 'entities'
    ) OR EXISTS (
        SELECT 1 FROM news_llm_raw r
        WHERE r.unique_id = %s AND r.task = 'ner'
    )
"""


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


def _resolve_enrichment_model_id() -> str:
    """Modelo da chamada combinada (tema+resumo+sentimento).

    ENRICHMENT_MODEL_ID é o nome preferido (Terraform, infra#215); BEDROCK_MODEL_ID
    é mantido por retrocompatibilidade. Sem nenhuma das duas, cai no default
    legado (DEFAULT_ENRICHMENT_MODEL_ID, inalterado) e loga em ERROR: o Haiku 3
    teve EOL no Bedrock e o default silencioso zerou o enriquecimento por 15 dias.
    """
    model_id = os.environ.get("ENRICHMENT_MODEL_ID") or os.environ.get("BEDROCK_MODEL_ID")
    if model_id:
        return model_id
    logger.error(
        "enrichment_model_env_missing default=%s "
        "(ENRICHMENT_MODEL_ID/BEDROCK_MODEL_ID ausentes; usando o default legado)",
        DEFAULT_ENRICHMENT_MODEL_ID,
    )
    return DEFAULT_ENRICHMENT_MODEL_ID


def _get_classifier() -> NewsClassifier:
    """Lazy-init classifier with taxonomy from PG."""
    global _classifier
    if _classifier is None:
        database_url = _get_database_url()
        taxonomy = load_taxonomy_from_postgres(database_url)
        aws_access_key, aws_secret_key, aws_region = _parse_aws_credentials()
        # Modelo combinado (tema+resumo+sentimento) — configurável por env.
        enrichment_model_id = _resolve_enrichment_model_id()
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


def ner_already_done(unique_id: str) -> bool:
    """True se o NER já rodou para o uid (anti-amplificação: no máximo 1x por uid).

    O scraper republica `dgb.news.scraped` a cada re-scrape (~13x/dia por artigo).
    Sem tema gravado (falha da chamada combinada), cada republicação chegava ao
    NER (Sonnet) de novo. Também protege entidades já canonicalizadas, que o merge
    `features || {"entities": ...}` sobrescreveria.

    Falha de DB → True (fail-closed: pula o NER e loga WARNING). Um NER pulado é
    recuperável pelo scripts/backfill_ner_corpus.py; amplificação de custo não é.
    """
    try:
        conn = psycopg2.connect(_get_database_url())
    except Exception as e:
        logger.warning(f"ner_already_done: falha ao conectar para {unique_id} (NER pulado): {e}")
        return True
    try:
        cursor = conn.cursor()
        cursor.execute(_NER_ALREADY_DONE_SQL, (unique_id, unique_id))
        row = cursor.fetchone()
        cursor.close()
        return bool(row and row[0])
    except Exception as e:
        logger.warning(f"ner_already_done: falha na consulta para {unique_id} (NER pulado): {e}")
        return True
    finally:
        try:
            conn.close()
        except Exception:
            pass


def is_combined_failure(result: dict | None) -> bool:
    """A chamada combinada falhou? (`_error` presente ou todos os campos de tema nulos)."""
    if not result:
        return True
    if result.get("_error"):
        return True
    return all(not result.get(field) for field in _THEME_CODE_FIELDS)


def combined_failure_error(result: dict | None) -> str:
    """Erro da chamada combinada para log/status ("<ErrorCode>: <msg>")."""
    if not result:
        return "EmptyResult: classify_single devolveu vazio"
    return result.get("_error") or "AllThemeFieldsNull: resposta sem nenhum código de tema"


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

    if is_combined_failure(result):
        return _handle_combined_failure(unique_id, article, classifier, result)

    # Ensure unique_id is in result for update_news_enrichment
    result["unique_id"] = unique_id

    # NER (chamada DEDICADA, modelo Sonnet 4.6 em prod), no máximo 1x por uid.
    # Resiliente: uma falha no NER não derruba o enriquecimento de tema/sentimento.
    entities, ner_raw, _ = _run_ner_once(classifier, article, unique_id)
    result["entities"] = entities

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
        logger.error(
            "enrichment_update_failed uid=%s model=%s stats=%s",
            unique_id,
            result.get("_model_id"),
            stats,
        )
        return {"status": "update_failed", "stats": stats}

    # Publish event
    publish_enriched_event(
        unique_id,
        result.get("most_specific_theme_code"),
        bool(result.get("summary")),
    )

    return {"status": "enriched", "stats": stats}


def _handle_combined_failure(
    unique_id: str, article: dict, classifier: NewsClassifier, result: dict | None
) -> dict[str, Any]:
    """Falha da chamada combinada: torna visível e evita amplificar o NER.

    - ERROR estável "enrichment_combined_failed uid= model= error=";
    - CRITICAL estável "enrichment_model_unavailable model=" se o erro for de fim
      de vida / modelo inexistente (alerta);
    - NER só se ainda não rodou para o uid; entidades novas são gravadas;
    - NÃO atualiza tema/resumo e NÃO publica dgb.news.enriched;
    - devolve status "classification_failed" (o app continua respondendo 200/ACK).
    """
    error = combined_failure_error(result)
    model_id = (result or {}).get("_model_id") or getattr(classifier.llm_client, "model_id", None)
    logger.error(
        "enrichment_combined_failed uid=%s model=%s error=%s", unique_id, model_id, error
    )
    if is_model_unavailable_error(error):
        logger.critical(
            "enrichment_model_unavailable model=%s error_code=%s",
            model_id,
            error.partition(":")[0].strip(),
        )

    entities, ner_raw, ner_status = _run_ner_once(classifier, article, unique_id)
    # Ledger: tokens do NER e, se a resposta combinada veio (temas nulos), dela.
    _record_ledger_usage(result or {}, ner_raw)
    if entities:
        _upsert_ai_features(unique_id, {"entities": entities})

    return {"status": "classification_failed", "error": error, "ner": ner_status}


def _run_ner_once(
    classifier: NewsClassifier, article: dict, unique_id: str
) -> tuple[list, dict | None, str]:
    """Roda o NER se ainda não rodou para o uid. Devolve (entities, ner_raw, status).

    status: "ran" | "failed" | "skipped_already_done". Nunca levanta.
    """
    ner_model_id = getattr(classifier.llm_client, "ner_model_id", None)
    if ner_already_done(unique_id):
        logger.info(
            "enrichment_ner uid=%s status=skipped_already_done model=%s", unique_id, ner_model_id
        )
        return [], None, "skipped_already_done"

    try:
        entities, ner_raw = classifier.llm_client.extract_entities(article, return_raw=True)
    except Exception as e:
        logger.error(f"NER extraction failed for {unique_id}: {e}")
        logger.info("enrichment_ner uid=%s status=failed model=%s", unique_id, ner_model_id)
        return [], None, "failed"

    # Grava a resposta crua em news_llm_raw (não fatal se falhar; None é no-op).
    store_raw_llm_response(unique_id, "ner", ner_raw)
    status = "ran" if ner_raw is not None else "failed"
    logger.info(
        "enrichment_ner uid=%s status=%s model=%s entities=%d",
        unique_id,
        status,
        ner_model_id,
        len(entities or []),
    )
    return entities or [], ner_raw, status


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
