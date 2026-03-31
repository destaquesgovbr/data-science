#!/usr/bin/env python3
"""
Semantic search implementation using pre-computed embeddings.

Performs similarity search between queries and corpus documents.
Saves ranked results for each query-model combination.

Usage:
    python semantic_search.py [--models MODEL1 ...] [--top-k 100]
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

from setup_models import MODELS


def load_queries():
    """Load queries from query_template_85.json."""
    query_file = Path(__file__).parent.parent / "data" / "query_template_85.json"

    with open(query_file) as f:
        queries_data = json.load(f)

    # Extract only filled queries (non-empty query_text)
    queries = []
    for q in queries_data:
        # Check if query has manual text OR recommended_query
        query_text = q.get('query_text', '').strip()
        if not query_text:
            # Fallback to recommended_query if query_text is empty
            query_text = q.get('recommended_query', '').strip()

        if query_text:
            queries.append({
                'query_id': q['query_id'],
                'text': query_text,
                'category': q['category'],
                'anchor_doc_id': q['anchor_doc_id'],
                'suggested_type': q.get('suggested_type', 'geral')
            })

    print(f"✅ {len(queries)} queries carregadas")
    return queries


def load_corpus_embeddings(model_id: str) -> Tuple[np.ndarray, List[str]]:
    """Load pre-computed corpus embeddings."""
    embeddings_dir = Path(__file__).parent.parent / "results" / "embeddings"

    # Load embeddings
    emb_file = embeddings_dir / f"{model_id}_corpus.npy"
    embeddings = np.load(emb_file)

    # Load doc IDs
    ids_file = embeddings_dir / f"{model_id}_doc_ids.json"
    with open(ids_file) as f:
        doc_ids = json.load(f)

    return embeddings, doc_ids


def generate_query_embeddings(
    model_id: str,
    model_info: Dict,
    queries: List[Dict],
    device: str = "cuda"
) -> np.ndarray:
    """Generate embeddings for all queries."""

    print(f"\n🔄 Gerando embeddings de queries para {model_id}...")

    # Load model
    model = SentenceTransformer(model_info['name'], device=device)

    # Extract query texts
    query_texts = [q['text'] for q in queries]

    # Generate embeddings
    query_embeddings = model.encode(
        query_texts,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    print(f"✅ {len(queries)} query embeddings gerados")

    del model

    return query_embeddings


def search_similar_documents(
    query_embedding: np.ndarray,
    corpus_embeddings: np.ndarray,
    doc_ids: List[str],
    top_k: int = 100
) -> List[Tuple[str, float]]:
    """
    Find top-k most similar documents to query.

    Returns:
        List of (doc_id, similarity_score) tuples, sorted by score (descending)
    """

    # Compute cosine similarity
    similarities = cosine_similarity([query_embedding], corpus_embeddings)[0]

    # Get top-k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]

    # Return (doc_id, score) pairs
    results = [(doc_ids[idx], float(similarities[idx])) for idx in top_indices]

    return results


def run_search_for_model(
    model_id: str,
    model_info: Dict,
    queries: List[Dict],
    top_k: int = 100,
    device: str = "cuda"
):
    """Run semantic search for all queries using one model."""

    print(f"\n{'='*70}")
    print(f"🔍 BUSCA SEMÂNTICA - {model_id.upper()}")
    print(f"{'='*70}")

    # Load corpus embeddings
    print("📂 Carregando embeddings do corpus...")
    corpus_embeddings, doc_ids = load_corpus_embeddings(model_id)
    print(f"✅ {len(doc_ids)} documentos carregados")

    # Generate query embeddings
    query_embeddings = generate_query_embeddings(model_id, model_info, queries, device)

    # Perform search for each query
    print(f"\n🔍 Executando busca para {len(queries)} queries...")

    results = {}

    for i, query in enumerate(tqdm(queries, desc="Buscando")):
        query_id = query['query_id']
        query_emb = query_embeddings[i]

        # Search
        top_docs = search_similar_documents(
            query_emb,
            corpus_embeddings,
            doc_ids,
            top_k=top_k
        )

        results[query_id] = {
            'query_text': query['text'],
            'category': query['category'],
            'anchor_doc_id': query['anchor_doc_id'],
            'suggested_type': query['suggested_type'],
            'results': [
                {
                    'doc_id': doc_id,
                    'score': score,
                    'rank': rank + 1
                }
                for rank, (doc_id, score) in enumerate(top_docs)
            ]
        }

    # Save results
    output_dir = Path(__file__).parent.parent / "results" / "search_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{model_id}_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Resultados salvos: {output_file}")

    return results


def main():
    """Main search routine."""
    import argparse
    import torch

    parser = argparse.ArgumentParser(description="Run semantic search")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Models to use (default: all)")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu",
                        help="Device to use")
    parser.add_argument("--top-k", type=int, default=100,
                        help="Number of results per query (default: 100)")

    args = parser.parse_args()

    print("="*70)
    print("🔍 BUSCA SEMÂNTICA")
    print("="*70)

    # Load queries
    queries = load_queries()

    if len(queries) == 0:
        print("\n❌ Nenhuma query encontrada! Termine de preencher query_template_85.json")
        return

    # Select models
    models_to_use = args.models if args.models else list(MODELS.keys())

    print(f"\n📊 Configuração:")
    print(f"   Modelos: {len(models_to_use)}")
    print(f"   Queries: {len(queries)}")
    print(f"   Top-K: {args.top_k}")
    print(f"   Device: {args.device.upper()}")

    # Run search for each model
    for i, model_id in enumerate(models_to_use, 1):
        if model_id not in MODELS:
            print(f"\n⚠️  Modelo '{model_id}' não encontrado")
            continue

        model_info = MODELS[model_id]

        print(f"\n{'='*70}")
        print(f"📊 Progresso: {i}/{len(models_to_use)}")
        print(f"{'='*70}")

        try:
            run_search_for_model(
                model_id,
                model_info,
                queries,
                top_k=args.top_k,
                device=args.device
            )

        except Exception as e:
            print(f"\n❌ Erro ao processar {model_id}: {e}")
            continue

    print(f"\n{'='*70}")
    print("✅ BUSCA COMPLETA!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
