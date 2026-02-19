"""
PostgresExporter - Exporta dados enriquecidos para PostgreSQL
"""
import polars as pl
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
import logging
from typing import Optional
from io import StringIO

logger = logging.getLogger(__name__)


class PostgresExporter:
    """Exporta DataFrames Polars para PostgreSQL."""

    def __init__(self, connection_string: Optional[str] = None):
        """
        Inicializa o exportador Postgres.

        Args:
            connection_string: String de conexão PostgreSQL
                             Formato: "postgresql://user:password@host:port/dbname"
        """
        self.connection_string = connection_string

    def export_to_postgres(
        self,
        df: pl.DataFrame,
        table_name: str,
        if_exists: str = "append"
    ):
        """
        Exporta DataFrame para PostgreSQL.

        Args:
            df: DataFrame Polars para exportar
            table_name: Nome da tabela de destino
            if_exists: "append" (adicionar) ou "replace" (substituir)

        Raises:
            ValueError: Se connection_string não fornecido
        """
        if not self.connection_string:
            raise ValueError(
                "connection_string não fornecido. "
                "Configure ao inicializar PostgresExporter."
            )

        logger.info(f"Exportando {len(df)} linhas para Postgres: {table_name}")

        try:
            # Conectar ao Postgres
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()

            logger.info("✅ Conexão com Postgres estabelecida")

            # Criar ou limpar tabela
            if if_exists == "replace":
                logger.info(f"Modo 'replace': recriando tabela {table_name}")
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                create_table_sql = self.get_schema_sql(table_name, df)
                cursor.execute(create_table_sql)
                conn.commit()
            elif if_exists == "append":
                logger.info(f"Modo 'append': adicionando dados à tabela {table_name}")
                # Verificar se tabela existe
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=%s)",
                    (table_name,)
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    logger.info(f"Tabela {table_name} não existe. Criando...")
                    create_table_sql = self.get_schema_sql(table_name, df)
                    cursor.execute(create_table_sql)
                    conn.commit()
            else:
                raise ValueError(f"if_exists deve ser 'append' ou 'replace', não '{if_exists}'")

            # Bulk insert usando COPY (mais eficiente)
            logger.info("Inserindo dados com COPY...")
            self._bulk_insert_copy(cursor, df, table_name)

            conn.commit()
            logger.info(f"✅ {len(df)} linhas exportadas com sucesso para {table_name}")

            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"❌ Erro ao exportar para Postgres: {e}")
            raise

    def _bulk_insert_copy(self, cursor, df: pl.DataFrame, table_name: str):
        """
        Usa COPY para bulk insert eficiente.

        Args:
            cursor: Cursor do psycopg2
            df: DataFrame
            table_name: Nome da tabela
        """
        # Converter DataFrame para CSV em memória
        csv_buffer = StringIO()

        # Converter para pandas (temporariamente) para facilitar COPY
        pandas_df = df.to_pandas()
        pandas_df.to_csv(csv_buffer, index=False, header=False, sep='\t', na_rep='\\N')
        csv_buffer.seek(0)

        # Usar COPY
        columns = df.columns
        copy_sql = f"COPY {table_name} ({','.join(columns)}) FROM STDIN WITH CSV DELIMITER E'\\t' NULL '\\N'"

        cursor.copy_expert(copy_sql, csv_buffer)

    def get_schema_sql(
        self,
        table_name: str,
        df: Optional[pl.DataFrame] = None
    ) -> str:
        """
        Gera SQL DDL para criar tabela com schema adequado.

        Args:
            table_name: Nome da tabela
            df: DataFrame de referência (opcional, para inferir schema)

        Returns:
            String com SQL DDL
        """
        if df is None:
            # Schema padrão baseado no plano
            return self._get_default_schema_sql(table_name)
        else:
            # Inferir schema do DataFrame
            return self._infer_schema_sql(table_name, df)

    def _get_default_schema_sql(self, table_name: str) -> str:
        """Retorna schema SQL padrão para notícias enriquecidas."""
        return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    unique_id VARCHAR PRIMARY KEY,
    agency VARCHAR,
    published_at TIMESTAMP,
    updated_datetime TIMESTAMP,
    extracted_at TIMESTAMP,
    title TEXT,
    subtitle TEXT,
    editorial_lead TEXT,
    url VARCHAR,
    content TEXT,
    image VARCHAR,
    video_url VARCHAR,
    category VARCHAR,
    tags TEXT[],

    -- Campos enriquecidos
    theme_1_level_1 VARCHAR,
    theme_1_level_1_code VARCHAR,
    theme_1_level_1_label VARCHAR,
    theme_1_level_2_code VARCHAR,
    theme_1_level_2_label VARCHAR,
    theme_1_level_3_code VARCHAR,
    theme_1_level_3_label VARCHAR,
    most_specific_theme_code VARCHAR,
    most_specific_theme_label VARCHAR,
    summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_theme_level_1 ON {table_name}(theme_1_level_1_code);
CREATE INDEX IF NOT EXISTS idx_{table_name}_theme_level_2 ON {table_name}(theme_1_level_2_code);
CREATE INDEX IF NOT EXISTS idx_{table_name}_theme_level_3 ON {table_name}(theme_1_level_3_code);
CREATE INDEX IF NOT EXISTS idx_{table_name}_published_at ON {table_name}(published_at);
"""

    def _infer_schema_sql(self, table_name: str, df: pl.DataFrame) -> str:
        """
        Infere schema SQL do DataFrame Polars.

        Args:
            table_name: Nome da tabela
            df: DataFrame

        Returns:
            SQL DDL
        """
        columns = []
        for col_name, dtype in zip(df.columns, df.dtypes):
            pg_type = self._convert_polars_to_postgres_type(dtype)

            # Chave primária
            if col_name == 'unique_id':
                columns.append(f"    {col_name} {pg_type} PRIMARY KEY")
            else:
                columns.append(f"    {col_name} {pg_type}")

        columns_sql = ",\n".join(columns)

        return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
{columns_sql}
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_theme_level_1 ON {table_name}(theme_1_level_1_code);
CREATE INDEX IF NOT EXISTS idx_{table_name}_theme_level_2 ON {table_name}(theme_1_level_2_code);
CREATE INDEX IF NOT EXISTS idx_{table_name}_theme_level_3 ON {table_name}(theme_1_level_3_code);
CREATE INDEX IF NOT EXISTS idx_{table_name}_published_at ON {table_name}(published_at);
"""

    def _convert_polars_to_postgres_type(self, dtype) -> str:
        """
        Mapeia tipo Polars para tipo PostgreSQL.

        Args:
            dtype: Tipo Polars

        Returns:
            String com tipo PostgreSQL
        """
        type_mapping = {
            pl.String: "TEXT",
            pl.Int64: "BIGINT",
            pl.Int32: "INTEGER",
            pl.Float64: "DOUBLE PRECISION",
            pl.Float32: "REAL",
            pl.Boolean: "BOOLEAN",
            pl.Date: "DATE",
            pl.Datetime: "TIMESTAMP",
        }

        # Tipo base
        base_type = str(dtype)

        # Verificar se é lista (array)
        if "List" in base_type:
            return "TEXT[]"

        # Mapear tipo
        for pl_type, pg_type in type_mapping.items():
            if dtype == pl_type:
                return pg_type

        # Default: TEXT
        logger.warning(f"Tipo Polars desconhecido: {dtype}. Usando TEXT como fallback.")
        return "TEXT"
