"""
Job de enriquecimento de notícias via LLM (Bedrock).

Lê notícias sem classificação do PostgreSQL, classifica via Bedrock,
e grava os resultados de volta no PostgreSQL.
"""

import logging
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import execute_batch

from .classifier import NewsClassifier
from .taxonomy import build_theme_code_to_id_map, load_taxonomy_from_postgres

logger = logging.getLogger(__name__)

# Limite de notícias por execução para evitar timeouts
DEFAULT_BATCH_LIMIT = 200


def fetch_unenriched_news(
    database_url: str,
    limit: int = DEFAULT_BATCH_LIMIT,
    lookback_days: Optional[int] = None,
) -> List[Dict]:
    """
    Busca notícias sem classificação temática do PostgreSQL.

    Args:
        database_url: Connection string PostgreSQL
        limit: Máximo de notícias a processar por execução
        lookback_days: Se definido, filtra apenas notícias publicadas nos últimos N dias

    Returns:
        Lista de dicts com campos necessários para classificação
    """
    if lookback_days is not None:
        query = """
            SELECT unique_id, title, subtitle, editorial_lead, content
            FROM news
            WHERE most_specific_theme_id IS NULL
              AND published_at >= NOW() - INTERVAL '%s days'
            ORDER BY published_at DESC
            LIMIT %s
        """
        params = (lookback_days, limit)
    else:
        query = """
            SELECT unique_id, title, subtitle, editorial_lead, content
            FROM news
            WHERE most_specific_theme_id IS NULL
            ORDER BY published_at DESC
            LIMIT %s
        """
        params = (limit,)

    conn = psycopg2.connect(database_url)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    logger.info(f"Encontradas {len(rows)} notícias sem classificação" +
                (f" (últimos {lookback_days} dias)" if lookback_days else ""))
    return rows


def update_news_enrichment(
    database_url: str,
    enriched_rows: List[Dict],
    code_to_id: Dict[str, int],
) -> Dict[str, int]:
    """
    Atualiza notícias no PostgreSQL com classificação e summary.

    Args:
        database_url: Connection string PostgreSQL
        enriched_rows: Lista de dicts com resultados do classificador
        code_to_id: Mapeamento theme code → theme id

    Returns:
        Estatísticas: {updated, skipped, failed}
    """
    update_query = """
        UPDATE news
        SET theme_l1_id = %s,
            theme_l2_id = %s,
            theme_l3_id = %s,
            most_specific_theme_id = %s,
            summary = %s,
            updated_at = NOW()
        WHERE unique_id = %s
    """

    stats = {"updated": 0, "skipped": 0, "failed": 0}
    update_params = []

    for row in enriched_rows:
        unique_id = row.get("unique_id")
        if not unique_id:
            stats["skipped"] += 1
            continue

        # Mapear codes para IDs
        l1_code = row.get("theme_1_level_1_code")
        l2_code = row.get("theme_1_level_2_code")
        l3_code = row.get("theme_1_level_3_code")
        summary = row.get("summary")

        l1_id = code_to_id.get(l1_code) if l1_code else None
        l2_id = code_to_id.get(l2_code) if l2_code else None
        l3_id = code_to_id.get(l3_code) if l3_code else None

        # most_specific: L3 > L2 > L1
        most_specific_id = l3_id or l2_id or l1_id

        if most_specific_id is None:
            # Classificação falhou — sem tema identificado
            stats["skipped"] += 1
            logger.warning(f"Sem tema para {unique_id} (codes: {l1_code}/{l2_code}/{l3_code})")
            continue

        update_params.append((l1_id, l2_id, l3_id, most_specific_id, summary, unique_id))

    if not update_params:
        logger.info("Nenhuma notícia para atualizar")
        return stats

    conn = psycopg2.connect(database_url)
    try:
        cursor = conn.cursor()
        execute_batch(cursor, update_query, update_params, page_size=100)
        stats["updated"] = len(update_params)
        conn.commit()
        cursor.close()
    except Exception as e:
        conn.rollback()
        stats["failed"] = len(update_params)
        logger.error(f"Erro ao atualizar PostgreSQL: {e}")
        raise
    finally:
        conn.close()

    logger.info(f"Atualizadas {stats['updated']} notícias no PostgreSQL")
    return stats


def _generate_mock_classifications(
    news: List[Dict],
    code_to_id: Dict[str, int],
) -> List[Dict]:
    """
    Gera classificações mock para teste local sem chamar LLM.

    Atribui o primeiro tema L1 disponível a todas as notícias.
    """
    # Pegar primeiro code L1 disponível
    l1_codes = [code for code in code_to_id if "." not in code]
    default_l1 = l1_codes[0] if l1_codes else "01"

    mock_results = []
    for item in news:
        mock_results.append({
            "unique_id": item.get("unique_id"),
            "theme_1_level_1_code": default_l1,
            "theme_1_level_1_label": f"Mock L1 ({default_l1})",
            "theme_1_level_2_code": None,
            "theme_1_level_2_label": None,
            "theme_1_level_3_code": None,
            "theme_1_level_3_label": None,
            "most_specific_theme_code": default_l1,
            "most_specific_theme_label": f"Mock L1 ({default_l1})",
            "summary": f"[MOCK] Resumo gerado para teste local — {item.get('title', '')[:80]}",
        })

    logger.info(f"Mock: geradas {len(mock_results)} classificações sintéticas")
    return mock_results


def run_enrichment(
    database_url: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
    region: str = "us-east-1",
    model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
    batch_limit: int = DEFAULT_BATCH_LIMIT,
    batch_size: int = 4,
    sleep_between_batches: float = 0.5,
    mock: bool = False,
    lookback_days: Optional[int] = None,
) -> Dict:
    """
    Executa o pipeline completo de enriquecimento.

    Args:
        database_url: Connection string PostgreSQL
        aws_access_key_id: Credencial AWS
        aws_secret_access_key: Credencial AWS
        aws_session_token: Token de sessão AWS
        region: Região AWS do Bedrock
        model_id: ID do modelo Bedrock
        batch_limit: Máximo de notícias por execução
        batch_size: Tamanho do batch para o LLM
        sleep_between_batches: Delay entre batches
        mock: Se True, gera classificações sintéticas sem chamar LLM
        lookback_days: Se definido, filtra notícias dos últimos N dias

    Returns:
        Dict com estatísticas da execução
    """
    # 1. Buscar notícias sem classificação
    news = fetch_unenriched_news(database_url, limit=batch_limit, lookback_days=lookback_days)

    if not news:
        logger.info("Nenhuma notícia pendente de classificação")
        return {"total": 0, "enriched": 0, "skipped": 0, "failed": 0}

    # 2. Carregar mapeamento code → id
    code_to_id = build_theme_code_to_id_map(database_url)

    # 3. Classificar
    if mock:
        logger.info("MODO MOCK ativo — classificações sintéticas, sem chamada LLM")
        enriched = _generate_mock_classifications(news, code_to_id)
    else:
        # Carregar taxonomia para prompt do LLM
        taxonomy = load_taxonomy_from_postgres(database_url)

        classifier = NewsClassifier(
            model_id=model_id,
            region=region,
            taxonomy=taxonomy,
            batch_size=batch_size,
            sleep_between_batches=sleep_between_batches,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )

        enriched = classifier.classify_batch(news, return_format="list")

    # 4. Atualizar PostgreSQL
    stats = update_news_enrichment(database_url, enriched, code_to_id)

    result = {
        "total": len(news),
        "enriched": stats["updated"],
        "skipped": stats["skipped"],
        "failed": stats["failed"],
        "mock": mock,
    }

    logger.info("=" * 60)
    logger.info(f"Resultado: {result}")
    logger.info("=" * 60)

    return result
