#!/usr/bin/env python3
"""Test temporality feature."""

import sys
sys.path.insert(0, '.')

from sentence_transformers import SentenceTransformer
from src.retrieval import Retriever, RetrieverConfig
from src.generation import Generator
from src.llm_providers import create_llm_provider

# Config
CONN_STRING = "host=localhost port=5433 dbname=news_db user=rag_user"

print("Loading embedder...")
embedder = SentenceTransformer('BAAI/bge-m3', device='cpu')

print("Creating retriever...")
config = RetrieverConfig(
    final_top_k=5,
    use_vector=True,
    use_fulltext=False,
    use_reranking=False
)
retriever = Retriever(CONN_STRING, embedder, config, None)

print("Creating LLM provider...")
llm = create_llm_provider('bedrock', model_id='us.anthropic.claude-haiku-4-5-20251001-v1:0')

print("Creating generator...")
generator = Generator(retriever, llm, min_source_score=0.0)

# Test query about recent events
queries = [
    "Quais as notícias mais recentes sobre periferias?",
    "O que aconteceu em março de 2026?",
    "Notícias sobre conferência de arquivos"
]

for query in queries:
    print(f"\n{'='*80}")
    print(f"QUERY: {query}")
    print('='*80)

    response = generator.generate(query, max_tokens=1500, temperature=0.0)

    print(f"\nANSWER:\n{response.answer}\n")
    print("SOURCES:")
    for src in response.sources:
        print(f"  [{src['index']}] {src['title']}")
        print(f"      Data: {src.get('published_at', 'N/A')} | Score: {src['score']:.3f}")

