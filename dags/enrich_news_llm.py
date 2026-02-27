"""
DAG para enriquecimento de notícias via LLM (AWS Bedrock).

Classifica notícias sem tema atribuído usando Claude Haiku via Bedrock,
atribuindo taxonomia hierárquica de 3 níveis e gerando summary.
Roda a cada 10 minutos, processando notícias pendentes.
"""

from datetime import datetime, timedelta
import logging
import os

from airflow.decorators import dag, task
from airflow.hooks.base import BaseHook


@dag(
    dag_id="enrich_news_llm",
    description="Enriquece notícias via LLM (Bedrock) — classificação temática + summary",
    schedule="*/10 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["llm", "enrichment", "bedrock"],
    default_args={
        "owner": "data-science",
        "depends_on_past": False,
        "email_on_failure": False,
        "email_on_retry": False,
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=10),
    },
)
def enrich_news_llm_dag():
    """Enriquece notícias pendentes via LLM Bedrock."""

    @task
    def enrich() -> dict:
        """Classifica notícias sem tema via Bedrock e grava no PostgreSQL."""
        from news_enrichment.enrichment_job import run_enrichment

        # Obter connections do Airflow
        pg_conn = BaseHook.get_connection("postgres_default")
        database_url = pg_conn.get_uri()

        # Credenciais AWS do Airflow connection
        try:
            aws_conn = BaseHook.get_connection("aws_bedrock")
            aws_access_key_id = aws_conn.login
            aws_secret_access_key = aws_conn.password
            # Região pode vir do extra ou do schema
            import json
            extra = json.loads(aws_conn.extra) if aws_conn.extra else {}
            region = extra.get("region_name", aws_conn.schema or "us-east-1")
            logging.info(f"Usando credenciais AWS da connection 'aws_bedrock' (região: {region})")
        except Exception:
            # Fallback: usar credenciais do ambiente (IAM role do Composer)
            aws_access_key_id = None
            aws_secret_access_key = None
            region = "us-east-1"
            logging.info("Connection 'aws_bedrock' não encontrada, usando credenciais do ambiente")

        # Mock mode: classificação sintética sem chamar LLM
        mock_llm = os.getenv("MOCK_LLM", "false").lower() == "true"
        if mock_llm:
            logging.info("MOCK_LLM=true — executando com classificações sintéticas")

        # Executar enriquecimento
        result = run_enrichment(
            database_url=database_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region=region,
            batch_limit=200,
            batch_size=4,
            sleep_between_batches=0.5,
            mock=mock_llm,
        )

        logging.info("=" * 60)
        logging.info(f"Resultado: {result}")
        logging.info("=" * 60)

        return result

    enrich()


dag_instance = enrich_news_llm_dag()
