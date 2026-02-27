"""
news_enrichment - Sistema de enriquecimento de notícias com LLM
Suporta Bedrock (AWS) e modelos locais (Ollama)
"""

from .classifier import NewsClassifier
from .enrichment_job import run_enrichment
from .llm_client import BedrockLLMClient
from .taxonomy import build_theme_code_to_id_map, load_taxonomy_from_postgres

__all__ = [
    'NewsClassifier',
    'BedrockLLMClient',
    'run_enrichment',
    'load_taxonomy_from_postgres',
    'build_theme_code_to_id_map',
]

__version__ = '0.4.0'
