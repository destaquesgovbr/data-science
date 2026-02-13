"""
NewsDatasetManager - Gerencia download e cache do dataset de notícias
"""
import polars as pl
from pathlib import Path
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class NewsDatasetManager:
    """Gerencia download e cache do dataset de notícias governamentais."""

    def __init__(self, cache_dir: str = "./data"):
        """
        Inicializa o gerenciador de dataset.

        Args:
            cache_dir: Diretório para cache local do dataset
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "govbrnews_full.parquet"
        self.hf_path = "hf://datasets/nitaibezerra/govbrnews/data/train-*.parquet"

    def download_and_cache(self) -> pl.DataFrame:
        """
        Baixa dataset do HuggingFace se necessário e salva cache local.

        Returns:
            DataFrame com o dataset completo
        """
        if self.cache_file.exists():
            logger.info(f"Cache encontrado em {self.cache_file}. Carregando...")
            return self.load_cached()

        logger.info(f"Cache não encontrado. Baixando dataset de {self.hf_path}...")
        try:
            df = pl.read_parquet(self.hf_path)
            logger.info(f"Dataset baixado com sucesso: {len(df)} notícias")

            # Salvar cache local
            logger.info(f"Salvando cache em {self.cache_file}...")
            df.write_parquet(self.cache_file)
            logger.info("Cache salvo com sucesso")

            return df

        except Exception as e:
            logger.error(f"Erro ao baixar dataset: {e}")
            raise

    def load_cached(self) -> pl.DataFrame:
        """
        Carrega dataset do cache local.

        Returns:
            DataFrame com o dataset completo

        Raises:
            FileNotFoundError: Se o cache não existir
        """
        if not self.cache_file.exists():
            raise FileNotFoundError(
                f"Cache não encontrado em {self.cache_file}. "
                "Execute download_and_cache() primeiro."
            )

        logger.info(f"Carregando dataset do cache: {self.cache_file}")
        df = pl.read_parquet(self.cache_file)
        logger.info(f"Dataset carregado: {len(df)} notícias")
        return df

    def get_sample(self, n: int = 10, seed: Optional[int] = None) -> pl.DataFrame:
        """
        Retorna amostra aleatória do dataset.

        Args:
            n: Número de notícias na amostra
            seed: Seed para reprodutibilidade (opcional)

        Returns:
            DataFrame com amostra aleatória
        """
        logger.info(f"Gerando amostra aleatória de {n} notícias...")

        # Carregar ou baixar dataset
        if self.cache_file.exists():
            df = self.load_cached()
        else:
            df = self.download_and_cache()

        # Sample aleatório
        if seed is not None:
            sample = df.sample(n=n, seed=seed)
        else:
            sample = df.sample(n=n)

        logger.info(f"Amostra gerada com {len(sample)} notícias")
        return sample

    def get_dataset_info(self) -> dict:
        """
        Retorna informações sobre o dataset.

        Returns:
            Dicionário com informações (num_rows, columns, cache_exists)
        """
        cache_exists = self.cache_file.exists()

        if cache_exists:
            df = self.load_cached()
            return {
                "num_rows": len(df),
                "columns": df.columns,
                "cache_exists": True,
                "cache_path": str(self.cache_file)
            }
        else:
            return {
                "cache_exists": False,
                "cache_path": str(self.cache_file)
            }
