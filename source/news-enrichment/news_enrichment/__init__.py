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

# RAG modules (opcional - requer: poetry install --extras rag)
try:
    from .rag_retriever import TaxonomyRAGRetriever
    from .classifier_rag import NewsClassifierRAG
    _RAG_AVAILABLE = True
except ImportError:
    TaxonomyRAGRetriever = None
    NewsClassifierRAG = None
    _RAG_AVAILABLE = False

# BERT modules (opcional - requer: poetry install --extras ml)
try:
    from .classifier_bert import NewsClassifierBERT
    _BERT_AVAILABLE = True
except ImportError:
    NewsClassifierBERT = None
    _BERT_AVAILABLE = False

__all__ = [
    'NewsDatasetManager',
    'BedrockLLMClient',
    'BedrockLLMClientOptimized',
    'LocalLLMClient',
    'NewsEnricher',
    'PostgresExporter',
    'NewsClassifier',
    # RAG (opcional)
    'TaxonomyRAGRetriever',
    'NewsClassifierRAG',
    # BERT (opcional)
    'NewsClassifierBERT',
]

__version__ = '0.5.0'  # Bump: Added BERT fine-tuned support
