"""
news_enrichment - Sistema de enriquecimento de notícias com LLM
Suporta Bedrock (AWS) e modelos locais (Ollama)
"""

from .dataset_manager import NewsDatasetManager
from .llm_client import BedrockLLMClient
from .llm_client_optimized import BedrockLLMClientOptimized
from .local_llm_client import LocalLLMClient
from .enricher import NewsEnricher
from .postgres_exporter import PostgresExporter
from .classifier import NewsClassifier

__all__ = [
    'NewsDatasetManager',
    'BedrockLLMClient',
    'BedrockLLMClientOptimized',
    'LocalLLMClient',
    'NewsEnricher',
    'PostgresExporter',
    'NewsClassifier'
]

__version__ = '0.3.0'
