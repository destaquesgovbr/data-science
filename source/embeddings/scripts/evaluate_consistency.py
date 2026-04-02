#!/usr/bin/env python3
"""
Evaluate intra-document consistency across query variants.

Measures how consistently a model returns the anchor document for different
formulations (variants) of the same query.

Key Metric: Consistency@K
  For each base query (e.g., q001):
    - Check if anchor doc appears in top-K for variant 1
    - Check if anchor doc appears in top-K for variant 2
    - Check if anchor doc appears in top-K for variant 3
    - Consistency@K = (num variants with anchor in top-K) / (total variants)

High consistency (→ 1.0) = Robust to query reformulation
Low consistency (→ 0.0) = Fragile, depends on exact wording

Usage:
    python evaluate_consistency.py [--models MODEL1 ...] [--k 10]
"""

import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

import numpy as np
import pandas as pd


def load_search_results(model_id: str) -> Dict:
    """Load search results for a model."""
    results_file = Path(__file__).parent.parent / "results" / "search_results" / f"{model_id}_results.json"

    with open(results_file) as f:
        results = json.load(f)

    return results


def calculate_consistency(
    base_query_id: str,
    variant_results: Dict[str, List],
    anchor_doc_id: str,
    k: int = 10
) -> Dict:
    """
    Calculate consistency metrics for one base query across its variants.

    Args:
        base_query_id: Base query ID (e.g., "q001")
        variant_results: Dict mapping variant_id -> list of top results
        anchor_doc_id: Expected anchor document ID
        k: Top-K cutoff

    Returns:
        Dict with consistency metrics
    """

    num_variants = len(variant_results)
    variants_with_anchor_in_topk = 0
    anchor_ranks = []

    for variant_id, results in variant_results.items():
        # Check if anchor is in top-K
        top_k_docs = [r['doc_id'] for r in results[:k]]

        if anchor_doc_id in top_k_docs:
            variants_with_anchor_in_topk += 1
            rank = top_k_docs.index(anchor_doc_id) + 1  # 1-indexed
            anchor_ranks.append(rank)
        else:
            anchor_ranks.append(k + 1)  # Not found

    # Consistency = proportion of variants with anchor in top-K
    consistency = variants_with_anchor_in_topk / num_variants if num_variants > 0 else 0.0

    # Average rank (among variants where it appears)
    found_ranks = [r for r in anchor_ranks if r <= k]
    avg_rank = np.mean(found_ranks) if found_ranks else k + 1

    return {
        'base_query_id': base_query_id,
        'num_variants': num_variants,
        'variants_found': variants_with_anchor_in_topk,
        'consistency': consistency,
        'avg_rank': avg_rank,
        'best_rank': min(anchor_ranks),
        'worst_rank': max(anchor_ranks),
        'all_ranks': anchor_ranks
    }


def evaluate_model_consistency(
    model_id: str,
    k: int = 10
) -> Dict:
    """
    Evaluate consistency for all queries of one model.

    Returns:
        Dict with per-base-query and aggregate consistency metrics
    """

    print(f"\n{'='*70}")
    print(f"📊 AVALIANDO CONSISTÊNCIA - {model_id.upper()}")
    print(f"{'='*70}")

    # Load search results
    search_results = load_search_results(model_id)

    # Group variants by base query
    base_queries = defaultdict(dict)

    for query_id, query_data in search_results.items():
        # Parse query ID (e.g., "q001_v1" -> base="q001", variant=1)
        if '_v' in query_id:
            base_query_id = query_id.rsplit('_v', 1)[0]
        else:
            base_query_id = query_id

        anchor_doc_id = query_data['anchor_doc_id']
        results = query_data['results']

        base_queries[base_query_id][query_id] = {
            'anchor_doc_id': anchor_doc_id,
            'results': results
        }

    # Calculate consistency for each base query
    all_consistency = []

    for base_query_id, variants_data in sorted(base_queries.items()):
        # Get anchor doc (same for all variants)
        anchor_doc_id = list(variants_data.values())[0]['anchor_doc_id']

        # Get results for each variant
        variant_results = {
            variant_id: data['results']
            for variant_id, data in variants_data.items()
        }

        # Calculate consistency
        consistency_metrics = calculate_consistency(
            base_query_id,
            variant_results,
            anchor_doc_id,
            k=k
        )

        all_consistency.append(consistency_metrics)

    # Aggregate metrics
    consistencies = [c['consistency'] for c in all_consistency]

    aggregate = {
        'model_id': model_id,
        'k': k,
        'num_base_queries': len(all_consistency),
        'mean_consistency': np.mean(consistencies),
        'median_consistency': np.median(consistencies),
        'std_consistency': np.std(consistencies),
        'min_consistency': np.min(consistencies),
        'max_consistency': np.max(consistencies),
        'perfect_consistency': sum(1 for c in consistencies if c == 1.0),
        'zero_consistency': sum(1 for c in consistencies if c == 0.0),
    }

    # Print summary
    print(f"\n📊 Resumo:")
    print(f"   Base queries avaliadas: {aggregate['num_base_queries']}")
    print(f"   Consistência média@{k}: {aggregate['mean_consistency']:.3f}")
    print(f"   Mediana: {aggregate['median_consistency']:.3f}")
    print(f"   Desvio padrão: {aggregate['std_consistency']:.3f}")
    print(f"   Consistência perfeita (1.0): {aggregate['perfect_consistency']} queries")
    print(f"   Consistência zero (0.0): {aggregate['zero_consistency']} queries")

    return {
        'aggregate': aggregate,
        'per_base_query': all_consistency
    }


def save_results(all_results: Dict):
    """Save consistency evaluation results."""
    output_dir = Path(__file__).parent.parent / "results" / "consistency"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save complete results
    results_file = output_dir / "consistency_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Resultados completos: {results_file}")

    # Create summary table
    summary_data = []

    for model_id, results in all_results.items():
        agg = results['aggregate']
        summary_data.append({
            'model': model_id,
            'consistency_mean': agg['mean_consistency'],
            'consistency_median': agg['median_consistency'],
            'perfect_count': agg['perfect_consistency'],
            'zero_count': agg['zero_consistency']
        })

    df_summary = pd.DataFrame(summary_data)
    df_summary = df_summary.sort_values('consistency_mean', ascending=False)

    # Save CSV
    csv_file = output_dir / "consistency_summary.csv"
    df_summary.to_csv(csv_file, index=False, float_format='%.4f')
    print(f"💾 Resumo (CSV): {csv_file}")

    # Print table
    print(f"\n{'='*70}")
    print("📊 RANKING DE CONSISTÊNCIA")
    print(f"{'='*70}\n")
    print(df_summary.to_string(index=False, float_format=lambda x: f'{x:.4f}'))


def main():
    """Main consistency evaluation routine."""
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate query variant consistency")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Models to evaluate (default: all with results)")
    parser.add_argument("--k", type=int, default=10,
                        help="Top-K cutoff (default: 10)")

    args = parser.parse_args()

    print("="*70)
    print("📊 AVALIAÇÃO DE CONSISTÊNCIA INTRA-DOCUMENTO")
    print("="*70)

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
    print(f"📊 K value: {args.k}")

    # Evaluate each model
    all_results = {}

    for model_id in models_to_eval:
        try:
            results = evaluate_model_consistency(model_id, k=args.k)
            all_results[model_id] = results

        except Exception as e:
            print(f"\n❌ Erro ao avaliar {model_id}: {e}")
            continue

    if not all_results:
        print("\n❌ Nenhum modelo avaliado com sucesso")
        return

    # Save results
    save_results(all_results)

    print(f"\n{'='*70}")
    print("✅ AVALIAÇÃO DE CONSISTÊNCIA COMPLETA!")
    print(f"{'='*70}")

    print(f"\n💡 Interpretação:")
    print(f"   Consistência alta (>0.8): Modelo robusto a reformulações")
    print(f"   Consistência média (0.5-0.8): Sensível a palavras exatas")
    print(f"   Consistência baixa (<0.5): Frágil, depende muito da formulação")


if __name__ == "__main__":
    main()
