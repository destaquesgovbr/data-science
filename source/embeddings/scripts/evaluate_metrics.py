#!/usr/bin/env python3
"""
Calculate retrieval metrics (NDCG, MAP, MRR, Recall@K).

Requires:
- Search results from semantic_search.py
- Ground truth relevance annotations from data/annotations/

Computes metrics per model and per query category.

Usage:
    python evaluate_metrics.py [--models MODEL1 ...] [--k 10]
"""

import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats


def dcg_at_k(relevances: List[float], k: int) -> float:
    """
    Compute Discounted Cumulative Gain at rank k.

    DCG = sum(rel_i / log2(i+1)) for i=1 to k

    Args:
        relevances: List of relevance scores (0-3) in ranked order
        k: Cutoff position

    Returns:
        DCG@k score
    """
    relevances = np.array(relevances[:k])
    if len(relevances) == 0:
        return 0.0

    # Positions start at 1, so add 1
    discounts = np.log2(np.arange(2, len(relevances) + 2))
    return np.sum(relevances / discounts)


def ndcg_at_k(relevances: List[float], k: int) -> float:
    """
    Compute Normalized DCG at rank k.

    NDCG = DCG@k / IDCG@k

    where IDCG is the DCG of the ideal ranking (sorted by relevance)

    Args:
        relevances: List of relevance scores in ranked order
        k: Cutoff position

    Returns:
        NDCG@k score (0 to 1)
    """
    dcg = dcg_at_k(relevances, k)

    # Ideal DCG: sort relevances descending
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = dcg_at_k(ideal_relevances, k)

    if idcg == 0:
        return 0.0

    return dcg / idcg


def average_precision(relevances: List[int]) -> float:
    """
    Compute Average Precision.

    AP = (1/R) * sum(Precision@k * rel_k) for all k

    where R is total number of relevant docs

    Args:
        relevances: Binary relevances (0 or 1) in ranked order

    Returns:
        AP score
    """
    relevances = np.array(relevances)
    relevant_count = np.sum(relevances)

    if relevant_count == 0:
        return 0.0

    # Precision at each position where doc is relevant
    precision_at_k = np.cumsum(relevances) / np.arange(1, len(relevances) + 1)

    # Average only at positions where doc is relevant
    ap = np.sum(precision_at_k * relevances) / relevant_count

    return ap


def reciprocal_rank(relevances: List[int]) -> float:
    """
    Compute Reciprocal Rank (RR).

    RR = 1 / (position of first relevant doc)

    Args:
        relevances: Binary relevances in ranked order

    Returns:
        RR score (0 to 1)
    """
    for i, rel in enumerate(relevances, 1):
        if rel > 0:
            return 1.0 / i
    return 0.0


def recall_at_k(relevances: List[int], k: int, total_relevant: int) -> float:
    """
    Compute Recall@K.

    Recall@K = (relevant docs in top-K) / (total relevant docs)

    Args:
        relevances: Binary relevances in ranked order
        k: Cutoff position
        total_relevant: Total number of relevant docs in corpus

    Returns:
        Recall@K score (0 to 1)
    """
    if total_relevant == 0:
        return 0.0

    relevant_in_topk = np.sum(relevances[:k])
    return relevant_in_topk / total_relevant


def load_ground_truth():
    """Load relevance annotations."""
    gt_file = Path(__file__).parent.parent / "data" / "annotations" / "ground_truth.json"

    if not gt_file.exists():
        raise FileNotFoundError(
            f"Ground truth não encontrado: {gt_file}\n"
            "Execute o script de anotação primeiro!"
        )

    with open(gt_file) as f:
        ground_truth = json.load(f)

    print(f"✅ Ground truth carregado: {len(ground_truth)} queries anotadas")

    return ground_truth


def load_search_results(model_id: str) -> Dict:
    """Load search results for a model."""
    results_file = Path(__file__).parent.parent / "results" / "search_results" / f"{model_id}_results.json"

    with open(results_file) as f:
        results = json.load(f)

    return results


def evaluate_query(
    query_id: str,
    search_results: List[Dict],
    ground_truth: Dict,
    k_values: List[int] = [5, 10, 20, 100]
) -> Dict:
    """
    Evaluate one query.

    Args:
        query_id: Query identifier
        search_results: Ranked list of retrieved docs with scores
        ground_truth: Relevance annotations for this query
        k_values: List of k values to compute metrics

    Returns:
        Dict with all metrics
    """

    # Get relevance scores in ranked order
    relevances = []
    binary_relevances = []

    for result in search_results:
        doc_id = result['doc_id']

        # Get relevance from ground truth (default: 0 if not annotated)
        relevance = ground_truth.get(doc_id, 0)
        relevances.append(relevance)

        # Binary: relevant if score > 0
        binary_relevances.append(1 if relevance > 0 else 0)

    # Total relevant docs for this query
    total_relevant = sum(1 for rel in ground_truth.values() if rel > 0)

    # Compute metrics
    metrics = {}

    # NDCG@K (uses graded relevance 0-3)
    for k in k_values:
        metrics[f'ndcg@{k}'] = ndcg_at_k(relevances, k)

    # MAP (uses binary relevance)
    metrics['map'] = average_precision(binary_relevances)

    # MRR (uses binary relevance)
    metrics['mrr'] = reciprocal_rank(binary_relevances)

    # Recall@K (uses binary relevance)
    for k in k_values:
        metrics[f'recall@{k}'] = recall_at_k(binary_relevances, k, total_relevant)

    return metrics


def evaluate_model(
    model_id: str,
    ground_truth: Dict,
    k_values: List[int] = [5, 10, 20, 100]
) -> Dict:
    """
    Evaluate all queries for one model.

    Returns:
        Dict with per-query metrics and aggregated statistics
    """

    print(f"\n{'='*70}")
    print(f"📊 Avaliando: {model_id.upper()}")
    print(f"{'='*70}")

    # Load search results
    search_results = load_search_results(model_id)

    # Evaluate each query
    query_metrics = {}
    by_category = defaultdict(list)
    by_type = defaultdict(list)
    by_variant_type = defaultdict(list)

    for query_id, query_data in search_results.items():
        # Check if query has ground truth
        if query_id not in ground_truth:
            print(f"⚠️  Query {query_id} sem ground truth, pulando...")
            continue

        # Evaluate
        metrics = evaluate_query(
            query_id,
            query_data['results'],
            ground_truth[query_id],
            k_values
        )

        query_metrics[query_id] = {
            **metrics,
            'category': query_data['category'],
            'query_type': query_data['suggested_type']
        }

        # Group by category
        category = query_data['category']
        by_category[category].append(metrics)

        # Group by type
        query_type = query_data['suggested_type']
        by_type[query_type].append(metrics)

        # Group by variant type (if available)
        variant_type = query_data.get('variant_type', 'unknown')
        by_variant_type[variant_type].append(metrics)

    # Aggregate metrics
    all_metrics = list(query_metrics.values())

    # Overall averages
    overall = {}
    for metric in all_metrics[0].keys():
        if metric in ['category', 'query_type']:
            continue
        values = [m[metric] for m in all_metrics]
        overall[metric] = {
            'mean': np.mean(values),
            'median': np.median(values),
            'std': np.std(values),
            'min': np.min(values),
            'max': np.max(values)
        }

    # By category
    by_category_agg = {}
    for category, metrics_list in by_category.items():
        by_category_agg[category] = {}
        for metric in k_values:
            key = f'ndcg@{metric}'
            values = [m[key] for m in metrics_list]
            by_category_agg[category][key] = np.mean(values)

    # By type
    by_type_agg = {}
    for qtype, metrics_list in by_type.items():
        by_type_agg[qtype] = {}
        for metric in k_values:
            key = f'ndcg@{metric}'
            values = [m[key] for m in metrics_list]
            by_type_agg[qtype][key] = np.mean(values)

    # By variant type
    by_variant_type_agg = {}
    for vtype, metrics_list in by_variant_type.items():
        by_variant_type_agg[vtype] = {}
        for metric in k_values:
            key = f'ndcg@{metric}'
            values = [m[key] for m in metrics_list]
            by_variant_type_agg[vtype][key] = np.mean(values)

    # Print summary
    print(f"\n📊 Resultados Gerais:")
    print(f"   NDCG@10: {overall['ndcg@10']['mean']:.4f} (±{overall['ndcg@10']['std']:.4f})")
    print(f"   MAP:     {overall['map']['mean']:.4f} (±{overall['map']['std']:.4f})")
    print(f"   MRR:     {overall['mrr']['mean']:.4f} (±{overall['mrr']['std']:.4f})")

    # Print variant type breakdown if available
    if by_variant_type_agg:
        print(f"\n📊 Por Tipo de Variante:")
        for vtype, metrics in by_variant_type_agg.items():
            if 'ndcg@10' in metrics:
                print(f"   {vtype:20} NDCG@10: {metrics['ndcg@10']:.4f}")

    return {
        'model_id': model_id,
        'overall': overall,
        'by_category': by_category_agg,
        'by_type': by_type_agg,
        'by_variant_type': by_variant_type_agg,
        'per_query': query_metrics
    }


def compare_models(all_results: Dict, k: int = 10):
    """
    Compare models statistically.

    Performs paired t-test to check if differences are significant.
    """

    print(f"\n{'='*70}")
    print(f"📊 COMPARAÇÃO ESTATÍSTICA (NDCG@{k})")
    print(f"{'='*70}")

    # Extract NDCG@k scores per model
    model_scores = {}
    for model_id, results in all_results.items():
        scores = [
            q[f'ndcg@{k}']
            for q in results['per_query'].values()
        ]
        model_scores[model_id] = scores

    # Create comparison matrix
    model_ids = list(model_scores.keys())

    print(f"\n🔬 Teste t pareado (p-value):")
    print("   (p < 0.05 = diferença significativa)\n")

    # Header
    print(f"{'':20}", end='')
    for mid in model_ids:
        print(f"{mid[:15]:>15}", end='')
    print()

    # Rows
    for mid1 in model_ids:
        print(f"{mid1[:20]:20}", end='')
        for mid2 in model_ids:
            if mid1 == mid2:
                print(f"{'---':>15}", end='')
            else:
                # Paired t-test
                t_stat, p_value = stats.ttest_rel(
                    model_scores[mid1],
                    model_scores[mid2]
                )

                # Format p-value
                if p_value < 0.001:
                    p_str = "***"
                elif p_value < 0.01:
                    p_str = "**"
                elif p_value < 0.05:
                    p_str = "*"
                else:
                    p_str = "n.s."

                print(f"{p_str:>15}", end='')
        print()

    print("\n   *** p<0.001  ** p<0.01  * p<0.05  n.s. = não significativo")


def save_results(all_results: Dict):
    """Save evaluation results."""
    output_dir = Path(__file__).parent.parent / "results" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save complete results
    results_file = output_dir / "evaluation_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Resultados completos: {results_file}")

    # Create summary table
    summary_data = []

    for model_id, results in all_results.items():
        row = {
            'model': model_id,
            'ndcg@5': results['overall']['ndcg@5']['mean'],
            'ndcg@10': results['overall']['ndcg@10']['mean'],
            'ndcg@20': results['overall']['ndcg@20']['mean'],
            'map': results['overall']['map']['mean'],
            'mrr': results['overall']['mrr']['mean'],
            'recall@10': results['overall']['recall@10']['mean'],
        }
        summary_data.append(row)

    df_summary = pd.DataFrame(summary_data)
    df_summary = df_summary.sort_values('ndcg@10', ascending=False)

    # Save CSV
    csv_file = output_dir / "metrics_summary.csv"
    df_summary.to_csv(csv_file, index=False, float_format='%.4f')
    print(f"💾 Resumo (CSV): {csv_file}")

    # Print table
    print(f"\n{'='*70}")
    print("📊 RANKING DOS MODELOS (por NDCG@10)")
    print(f"{'='*70}\n")
    print(df_summary.to_string(index=False, float_format=lambda x: f'{x:.4f}'))


def main():
    """Main evaluation routine."""
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate retrieval metrics")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Models to evaluate (default: all with results)")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10, 20, 100],
                        help="K values for metrics (default: 5 10 20 100)")

    args = parser.parse_args()

    print("="*70)
    print("📊 AVALIAÇÃO DE MÉTRICAS")
    print("="*70)

    # Load ground truth
    try:
        ground_truth = load_ground_truth()
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        return

    # Find available results
    results_dir = Path(__file__).parent.parent / "results" / "search_results"
    available_models = [
        f.stem.replace('_results', '')
        for f in results_dir.glob("*_results.json")
    ]

    if not available_models:
        print("\n❌ Nenhum resultado de busca encontrado!")
        print("   Execute semantic_search.py primeiro.")
        return

    # Select models
    models_to_eval = args.models if args.models else available_models

    print(f"\n📊 Modelos a avaliar: {len(models_to_eval)}")
    print(f"📊 Queries anotadas: {len(ground_truth)}")
    print(f"📊 K values: {args.k}")

    # Evaluate each model
    all_results = {}

    for model_id in models_to_eval:
        try:
            results = evaluate_model(model_id, ground_truth, k_values=args.k)
            all_results[model_id] = results

        except Exception as e:
            print(f"\n❌ Erro ao avaliar {model_id}: {e}")
            continue

    if not all_results:
        print("\n❌ Nenhum modelo avaliado com sucesso")
        return

    # Compare models statistically
    if len(all_results) > 1:
        compare_models(all_results, k=10)

    # Save results
    save_results(all_results)

    print(f"\n{'='*70}")
    print("✅ AVALIAÇÃO COMPLETA!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
