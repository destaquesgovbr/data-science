"""
NewsEnricher - Orquestra o processo de enriquecimento de notícias
"""
import polars as pl
import logging
import time
from typing import Optional
from tqdm import tqdm
from pathlib import Path

from .dataset_manager import NewsDatasetManager
from .llm_client import BedrockLLMClient

logger = logging.getLogger(__name__)


class NewsEnricher:
    """Orquestra o processo de enriquecimento de notícias."""

    def __init__(
        self,
        dataset_manager: NewsDatasetManager,
        llm_client: BedrockLLMClient,
        verbose: bool = True
    ):
        """
        Inicializa o enricher.

        Args:
            dataset_manager: Gerenciador de dataset
            llm_client: Cliente LLM para enriquecimento
            verbose: Se True, exibe logs detalhados e progress bar
        """
        self.dataset_manager = dataset_manager
        self.llm_client = llm_client
        self.verbose = verbose

        # Estatísticas
        self.stats = {
            'total_processed': 0,
            'success_count': 0,
            'failure_count': 0,
            'total_time': 0.0
        }

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Configura logging detalhado."""
        if self.verbose:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

    def enrich_sample(self, n: int = 10, seed: Optional[int] = None) -> pl.DataFrame:
        """
        Enriquece amostra aleatória de notícias.

        Args:
            n: Número de notícias na amostra
            seed: Seed para reprodutibilidade

        Returns:
            DataFrame enriquecido
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"ENRIQUECENDO AMOSTRA DE {n} NOTÍCIAS")
        logger.info(f"{'='*80}\n")

        # Obter amostra
        sample_df = self.dataset_manager.get_sample(n=n, seed=seed)

        # Enriquecer
        enriched_df = self._enrich_dataframe(sample_df)

        return enriched_df

    def enrich_full(self) -> pl.DataFrame:
        """
        Enriquece dataset completo.

        Returns:
            DataFrame enriquecido completo
        """
        logger.info(f"\n{'='*80}")
        logger.info("ENRIQUECENDO DATASET COMPLETO")
        logger.info(f"{'='*80}\n")

        # Carregar dataset completo
        full_df = self.dataset_manager.download_and_cache()

        # Enriquecer
        enriched_df = self._enrich_dataframe(full_df)

        return enriched_df

    def _enrich_dataframe(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Enriquece um DataFrame de notícias.

        Args:
            df: DataFrame com notícias

        Returns:
            DataFrame enriquecido
        """
        start_time = time.time()

        # Converter para lista de dicts
        rows = df.to_dicts()

        logger.info(f"Processando {len(rows)} notícias...")
        logger.info(f"Batch size: {self.llm_client.batch_size}")
        logger.info(f"Batches estimados: {len(rows) // self.llm_client.batch_size + 1}\n")

        # Processar com progress bar
        if self.verbose:
            with tqdm(total=len(rows), desc="Enriquecendo", unit="notícia") as pbar:
                enriched_rows = []
                batch_size = self.llm_client.batch_size

                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    enriched_batch = self.llm_client.enrich_news_batch(batch)
                    enriched_rows.extend(enriched_batch)
                    pbar.update(len(batch))

                    # Log de progresso
                    self._log_progress(enriched_batch, pbar)
        else:
            enriched_rows = self.llm_client.enrich_news_batch(rows)

        # Criar DataFrame enriquecido com schema inference aumentado
        enriched_df = pl.DataFrame(enriched_rows, infer_schema_length=len(enriched_rows))

        # Atualizar estatísticas
        elapsed_time = time.time() - start_time
        self._update_stats(enriched_df, elapsed_time)

        logger.info(f"\n{'='*80}")
        logger.info("ENRIQUECIMENTO CONCLUÍDO")
        logger.info(f"{'='*80}")
        logger.info(f"Total processado: {len(enriched_df)} notícias")
        logger.info(f"Tempo total: {elapsed_time:.2f}s")
        logger.info(f"Tempo médio: {elapsed_time/len(enriched_df):.2f}s por notícia\n")

        return enriched_df

    def _log_progress(self, batch: list, pbar: tqdm):
        """
        Loga progresso do batch atual.

        Args:
            batch: Lista de notícias enriquecidas
            pbar: Progress bar do tqdm
        """
        for row in batch:
            unique_id = row.get('unique_id', 'unknown')
            theme = row.get('most_specific_theme_label', 'N/A')

            if theme:
                status = "✅"
                self.stats['success_count'] += 1
            else:
                status = "❌"
                self.stats['failure_count'] += 1

            self.stats['total_processed'] += 1

            if self.verbose and theme:
                level1 = row.get('theme_1_level_1_label', '')
                level2 = row.get('theme_1_level_2_label', '')
                level3 = row.get('theme_1_level_3_label', '')
                theme_path = f"{level1} > {level2} > {level3}"

                logger.info(
                    f"{status} {unique_id[:8]}... | {theme_path}"
                )

    def _update_stats(self, df: pl.DataFrame, elapsed_time: float):
        """
        Atualiza estatísticas de processamento.

        Args:
            df: DataFrame enriquecido
            elapsed_time: Tempo decorrido
        """
        self.stats['total_time'] = elapsed_time

        # Contar sucessos (notícias com summary não-null)
        success_count = df.filter(pl.col('summary').is_not_null()).height
        failure_count = len(df) - success_count

        self.stats['success_count'] = success_count
        self.stats['failure_count'] = failure_count
        self.stats['total_processed'] = len(df)

    def get_enrichment_stats(self) -> dict:
        """
        Retorna estatísticas de enriquecimento.

        Returns:
            Dicionário com estatísticas
        """
        if self.stats['total_processed'] == 0:
            return {
                'total_processed': 0,
                'success_rate': 0.0,
                'avg_time': 0.0
            }

        return {
            'total_processed': self.stats['total_processed'],
            'success_count': self.stats['success_count'],
            'failure_count': self.stats['failure_count'],
            'success_rate': self.stats['success_count'] / self.stats['total_processed'],
            'avg_time': self.stats['total_time'] / self.stats['total_processed']
        }

    def save_enriched(self, df: pl.DataFrame, output_path: str):
        """
        Salva DataFrame enriquecido em parquet.

        Args:
            df: DataFrame enriquecido
            output_path: Caminho para salvar
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Salvando dados enriquecidos em {output_path}...")
        df.write_parquet(output_path)
        logger.info(f"✅ Dados salvos com sucesso: {len(df)} notícias")
