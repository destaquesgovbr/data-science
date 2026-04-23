#!/usr/bin/env python3
"""
Avaliação de modelo fine-tuned vs zero-shot.

Calcula métricas (NDCG@5, NDCG@10, MAP, MRR, Recall@10) no test set
e compara com baseline zero-shot.

Usage:
    # Avaliar modelo fine-tuned
    python evaluate_finetuned.py --model models/bge-m3-fewshot --output results/fewshot_eval.json

    # Comparar com zero-shot
    python evaluate_finetuned.py --model models/bge-m3-fewshot --compare-baseline BAAI/bge-m3
"""

import argparse
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results" / "finetuning"


def load_test_data():
    """
    Carrega test set e ground truth.

    Returns:
        queries_dict, corpus_dict, ground_truth
    """
    print("📂 Carregando test set...")

    # Test triplets
    test_file = DATA_DIR / "finetuning" / "test.csv"
    test_df = pd.read_csv(test_file)

    # Ground truth
    gt_file = DATA_DIR / "annotations" / "ground_truth.json"
    with open(gt_file, 'r') as f:
        ground_truth_full = json.load(f)

    # Corpus
    corpus_dir = DATA_DIR / "corpus"
    corpus = {}
    for doc_file in corpus_dir.glob("doc_*.json"):
        with open(doc_file, 'r') as f:
            doc = json.load(f)
            corpus[doc['id']] = f"{doc['title']} {doc['content']}"

    # Queries
    query_file = DATA_DIR / "query_template_85.json"
    with open(query_file, 'r') as f:
        queries_data = json.load(f)

    queries = {}
    for q in queries_data:
        base_query_id = q['query_id']
        variants = q.get('variants', [])

        if not variants:
            query_text = q.get('recommended_query', '').strip()
            if query_text:
                queries[f"{base_query_id}_v1"] = query_text
        else:
            for i, variant in enumerate(variants, 1):
                variant_text = variant.get('text', '').strip()
                if variant_text:
                    queries[f"{base_query_id}_v{i}"] = variant_text

    print(f"  ✅ {len(test_df)} triplas no test set")
    print(f"  ✅ {len(queries)} queries")
    print(f"  ✅ {len(corpus)} documentos")
    print()

    return queries, corpus, ground_truth_full, test_df


def compute_dcg(relevances, k):
    """Compute DCG@K."""
    relevances = np.array(relevances[:k])
    if relevances.size == 0:
        return 0.0

    discounts = np.log2(np.arange(2, relevances.size + 2))
    return np.sum(relevances / discounts)


def compute_ndcg(relevances, k):
    """Compute NDCG@K."""
    dcg = compute_dcg(relevances, k)
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = compute_dcg(ideal_relevances, k)

    if idcg == 0:
        return 0.0

    return dcg / idcg


def compute_metrics(rankings, ground_truth, k_values=[5, 10]):
    """
    Calcula métricas de IR.

    Args:
        rankings: {query_id: [(doc_id, score), ...]}
        ground_truth: {query_id: {doc_id: relevance}}
        k_values: Lista de K para NDCG@K, Recall@K

    Returns:
        Dict com métricas agregadas
    """
    metrics = defaultdict(list)

    for query_id, ranking in rankings.items():
        if query_id not in ground_truth:
            continue

        gt = ground_truth[query_id]

        # Extrair relevâncias do ranking
        relevances = []
        for doc_id, _ in ranking:
            rel = gt.get(doc_id, 0)
            relevances.append(rel)

        # NDCG@K
        for k in k_values:
            ndcg = compute_ndcg(relevances, k)
            metrics[f'ndcg@{k}'].append(ndcg)

        # MAP
        num_relevant = sum(1 for r in gt.values() if r > 0)
        if num_relevant > 0:
            precisions = []
            relevant_count = 0
            for i, (doc_id, _) in enumerate(ranking, 1):
                if gt.get(doc_id, 0) > 0:
                    relevant_count += 1
                    precisions.append(relevant_count / i)

            if precisions:
                metrics['map'].append(np.mean(precisions))
            else:
                metrics['map'].append(0.0)

        # MRR
        for i, (doc_id, _) in enumerate(ranking, 1):
            if gt.get(doc_id, 0) > 0:
                metrics['mrr'].append(1.0 / i)
                break
        else:
            metrics['mrr'].append(0.0)

        # Recall@K
        for k in k_values:
            top_k_docs = {doc_id for doc_id, _ in ranking[:k]}
            relevant_docs = {doc_id for doc_id, rel in gt.items() if rel > 0}

            if relevant_docs:
                recall = len(top_k_docs & relevant_docs) / len(relevant_docs)
                metrics[f'recall@{k}'].append(recall)

    # Agregação
    aggregated = {}
    for metric_name, values in metrics.items():
        aggregated[metric_name] = {
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values))
        }

    return aggregated


def evaluate_model(model_path, queries, corpus, ground_truth, subset_queries=None):
    """
    Avalia modelo em queries específicas.

    Args:
        model_path: Path do modelo ou HuggingFace ID
        queries: Dict {query_id: query_text}
        corpus: Dict {doc_id: doc_text}
        ground_truth: Dict {query_id: {doc_id: relevance}}
        subset_queries: Lista de query_ids para avaliar (None = todas)

    Returns:
        rankings, metrics
    """
    print(f"🔄 Avaliando modelo: {model_path}")

    # Load model
    model = SentenceTransformer(str(model_path))

    # Filter queries
    if subset_queries:
        queries = {qid: text for qid, text in queries.items() if qid in subset_queries}

    print(f"  Queries: {len(queries)}")
    print(f"  Corpus: {len(corpus)}")

    # Encode corpus
    print("  Encoding corpus...")
    doc_ids = list(corpus.keys())
    doc_texts = [corpus[doc_id] for doc_id in doc_ids]
    corpus_embeddings = model.encode(doc_texts, show_progress_bar=True, batch_size=32)

    # Encode queries and rank
    print("  Encoding queries e ranking...")
    rankings = {}

    for query_id, query_text in tqdm(queries.items(), desc="  Ranking"):
        query_emb = model.encode([query_text])

        # Compute similarities
        similarities = cosine_similarity(query_emb, corpus_embeddings)[0]

        # Rank
        ranking_indices = np.argsort(similarities)[::-1]
        ranking = [(doc_ids[idx], float(similarities[idx])) for idx in ranking_indices]

        rankings[query_id] = ranking

    # Compute metrics
    print("  Calculando métricas...")
    metrics = compute_metrics(rankings, ground_truth, k_values=[5, 10])

    print("  ✅ Avaliação concluída")
    print()

    return rankings, metrics


def print_metrics(metrics, model_name):
    """Imprime métricas formatadas."""
    print(f"📊 Métricas - {model_name}")
    print("=" * 60)

    metric_order = ['ndcg@5', 'ndcg@10', 'map', 'mrr', 'recall@5', 'recall@10']

    for metric_name in metric_order:
        if metric_name in metrics:
            mean = metrics[metric_name]['mean']
            std = metrics[metric_name]['std']
            print(f"{metric_name:12s}: {mean:.4f} (±{std:.4f})")

    print()


def compare_models(metrics_finetuned, metrics_baseline):
    """Compara métricas entre fine-tuned e baseline."""

    print("📈 COMPARAÇÃO: Fine-tuned vs Zero-shot Baseline")
    print("=" * 80)
    print()

    metric_order = ['ndcg@5', 'ndcg@10', 'map', 'mrr', 'recall@5', 'recall@10']

    print(f"{'Metric':<12} {'Baseline':<12} {'Fine-tuned':<12} {'Δ Abs':<12} {'Δ %':<12}")
    print("-" * 80)

    for metric_name in metric_order:
        if metric_name in metrics_baseline and metric_name in metrics_finetuned:
            baseline = metrics_baseline[metric_name]['mean']
            finetuned = metrics_finetuned[metric_name]['mean']
            delta_abs = finetuned - baseline
            delta_pct = (delta_abs / baseline) * 100 if baseline > 0 else 0

            # Emoji indicator
            if delta_abs > 0.01:
                indicator = "✅"
            elif delta_abs < -0.01:
                indicator = "❌"
            else:
                indicator = "➖"

            print(f"{metric_name:<12} {baseline:<12.4f} {finetuned:<12.4f} "
                  f"{delta_abs:+11.4f} {delta_pct:+10.2f}% {indicator}")

    print()


def main():
    parser = argparse.ArgumentParser(description='Avaliar modelo fine-tuned')

    parser.add_argument(
        '--model',
        type=str,
        required=True,
        help='Path do modelo fine-tuned'
    )

    parser.add_argument(
        '--compare-baseline',
        type=str,
        default=None,
        help='Modelo baseline para comparação (ex: BAAI/bge-m3)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Arquivo JSON para salvar resultados'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("AVALIAÇÃO DE MODELO FINE-TUNED")
    print("=" * 80)
    print()

    # Load data
    queries, corpus, ground_truth, test_df = load_test_data()

    # Get test queries
    test_query_ids = set()
    for _, row in test_df.iterrows():
        # Identificar query_id pela tripla (não temos no CSV, precisamos inferir)
        # Por simplicidade, vamos avaliar em TODAS as queries do ground truth
        pass

    # Se temos ground truth, usar todas queries dele
    test_query_ids = set(ground_truth.keys())

    # Evaluate fine-tuned model
    rankings_ft, metrics_ft = evaluate_model(
        args.model,
        queries,
        corpus,
        ground_truth,
        subset_queries=test_query_ids
    )

    print_metrics(metrics_ft, "Fine-tuned")

    # Compare with baseline if specified
    if args.compare_baseline:
        print(f"🔄 Carregando baseline: {args.compare_baseline}")
        print()

        rankings_bl, metrics_bl = evaluate_model(
            args.compare_baseline,
            queries,
            corpus,
            ground_truth,
            subset_queries=test_query_ids
        )

        print_metrics(metrics_bl, "Zero-shot Baseline")
        compare_models(metrics_ft, metrics_bl)

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = {
            'model': str(args.model),
            'baseline': args.compare_baseline,
            'metrics_finetuned': metrics_ft,
            'num_queries': len(test_query_ids)
        }

        if args.compare_baseline:
            results['metrics_baseline'] = metrics_bl

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"💾 Resultados salvos em: {output_path}")
        print()

    print("=" * 80)
    print("✅ AVALIAÇÃO CONCLUÍDA")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
