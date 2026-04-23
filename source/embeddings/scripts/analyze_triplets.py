#!/usr/bin/env python3
"""
Análise das anotações para extração de triplas de fine-tuning.

Analisa ground_truth.json para determinar quantas triplas (query, positive, negative)
podem ser extraídas para fine-tuning de modelos de embedding.
"""

import json
from pathlib import Path
from collections import defaultdict, Counter
import pandas as pd

# Paths
BASE_DIR = Path(__file__).parent.parent
ANNOTATIONS_FILE = BASE_DIR / "data" / "annotations" / "ground_truth.json"

def load_ground_truth():
    """Carrega anotações."""
    with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_annotations(ground_truth):
    """Analisa estatísticas das anotações."""

    stats = {
        'total_queries': len(ground_truth),
        'total_annotations': 0,
        'relevance_counts': Counter(),
        'docs_per_query': [],
        'queries_by_base': defaultdict(list),
    }

    # Contar anotações por query
    for query_id, annotations in ground_truth.items():
        stats['total_annotations'] += len(annotations)
        stats['docs_per_query'].append(len(annotations))

        # Agrupar por query base (q001, q002, etc)
        base_query = query_id.split('_')[0]
        stats['queries_by_base'][base_query].append(query_id)

        # Contar distribuição de relevância
        for doc_id, relevance in annotations.items():
            stats['relevance_counts'][relevance] += 1

    return stats

def extract_triplets(ground_truth, positive_threshold=2):
    """
    Extrai triplas (query, positive, negative) das anotações.

    Args:
        ground_truth: Dicionário com anotações
        positive_threshold: Relevância mínima para considerar documento como positivo
                          2 = apenas relevante/muito relevante
                          1 = inclui "um pouco relevante"

    Returns:
        Lista de triplas (query_id, positive_doc, negative_doc)
    """
    triplets = []
    triplet_strategies = {
        'hard_negatives': [],  # negatives que apareceram no Top-10
        'random_negatives': []  # qualquer negative
    }

    for query_id, annotations in ground_truth.items():
        # Separar positivos e negativos
        positives = [doc_id for doc_id, rel in annotations.items() if rel >= positive_threshold]
        negatives = [doc_id for doc_id, rel in annotations.items() if rel == 0]

        # Gerar todas as combinações possíveis de triplas
        for pos_doc in positives:
            for neg_doc in negatives:
                triplet = (query_id, pos_doc, neg_doc)
                triplets.append(triplet)

                # Hard negatives são os que apareceram no Top-10 mas são irrelevantes
                triplet_strategies['hard_negatives'].append(triplet)

    return triplets, triplet_strategies

def analyze_triplet_potential(ground_truth):
    """Analisa quantas triplas podemos gerar com diferentes estratégias."""

    results = {}

    # Estratégia 1: Threshold = 2 (apenas relevante/muito relevante como positive)
    triplets_t2, _ = extract_triplets(ground_truth, positive_threshold=2)
    results['threshold_2'] = len(triplets_t2)

    # Estratégia 2: Threshold = 1 (inclui "um pouco relevante")
    triplets_t1, _ = extract_triplets(ground_truth, positive_threshold=1)
    results['threshold_1'] = len(triplets_t1)

    # Analisar queries sem positivos suficientes
    queries_without_positives = []
    queries_without_negatives = []
    queries_ok = 0

    for query_id, annotations in ground_truth.items():
        positives_t2 = sum(1 for rel in annotations.values() if rel >= 2)
        positives_t1 = sum(1 for rel in annotations.values() if rel >= 1)
        negatives = sum(1 for rel in annotations.values() if rel == 0)

        if positives_t2 == 0:
            queries_without_positives.append((query_id, positives_t1, negatives))

        if negatives == 0:
            queries_without_negatives.append(query_id)

        if positives_t2 > 0 and negatives > 0:
            queries_ok += 1

    results['queries_ok_t2'] = queries_ok
    results['queries_without_positives_t2'] = len(queries_without_positives)
    results['queries_without_negatives'] = len(queries_without_negatives)
    results['problematic_queries'] = queries_without_positives[:10]  # Primeiras 10

    return results

def analyze_by_category(ground_truth):
    """Analisa distribuição por categoria de documento."""

    category_stats = defaultdict(lambda: {'positives': 0, 'negatives': 0, 'queries': set()})

    for query_id, annotations in ground_truth.items():
        for doc_id, relevance in annotations.items():
            # Extrair categoria do doc_id (formato: doc_XX_YY onde XX é categoria)
            category = doc_id.split('_')[1]

            category_stats[category]['queries'].add(query_id)

            if relevance >= 2:
                category_stats[category]['positives'] += 1
            elif relevance == 0:
                category_stats[category]['negatives'] += 1

    # Converter para DataFrame
    df_data = []
    for cat, stats in sorted(category_stats.items()):
        df_data.append({
            'categoria': cat,
            'queries_envolvidas': len(stats['queries']),
            'docs_positivos': stats['positives'],
            'docs_negativos': stats['negatives'],
            'ratio_pos_neg': stats['positives'] / max(stats['negatives'], 1)
        })

    return pd.DataFrame(df_data)

def main():
    print("=" * 80)
    print("ANÁLISE DE TRIPLAS PARA FINE-TUNING")
    print("=" * 80)
    print()

    # Carregar dados
    print("📂 Carregando anotações...")
    ground_truth = load_ground_truth()
    print(f"✅ {len(ground_truth)} queries carregadas")
    print()

    # Estatísticas gerais
    print("=" * 80)
    print("1. ESTATÍSTICAS GERAIS")
    print("=" * 80)
    stats = analyze_annotations(ground_truth)

    print(f"Total de queries: {stats['total_queries']}")
    print(f"Total de anotações: {stats['total_annotations']}")
    print(f"Média de docs por query: {sum(stats['docs_per_query'])/len(stats['docs_per_query']):.1f}")
    print()

    print("Distribuição de relevância:")
    total = sum(stats['relevance_counts'].values())
    for rel in [0, 1, 2, 3]:
        count = stats['relevance_counts'][rel]
        pct = (count / total) * 100
        label = {0: "Irrelevante", 1: "Um pouco relevante", 2: "Relevante", 3: "Muito relevante"}[rel]
        print(f"  {label} ({rel}): {count:4d} ({pct:5.1f}%)")
    print()

    # Queries base
    print(f"Queries base (sem variantes): {len(stats['queries_by_base'])}")
    print(f"Média de variantes por query: {stats['total_queries']/len(stats['queries_by_base']):.1f}")
    print()

    # Análise de triplas
    print("=" * 80)
    print("2. POTENCIAL DE EXTRAÇÃO DE TRIPLAS")
    print("=" * 80)
    triplet_results = analyze_triplet_potential(ground_truth)

    print("Estratégia 1: Positive = relevância >= 2 (relevante + muito relevante)")
    print(f"  ✅ Triplas possíveis: {triplet_results['threshold_2']:,}")
    print(f"  ✅ Queries válidas: {triplet_results['queries_ok_t2']} / {stats['total_queries']}")
    print(f"  ⚠️  Queries sem positivos: {triplet_results['queries_without_positives_t2']}")
    print()

    print("Estratégia 2: Positive = relevância >= 1 (inclui 'um pouco relevante')")
    print(f"  ✅ Triplas possíveis: {triplet_results['threshold_1']:,}")
    print()

    print(f"Queries sem negativos: {triplet_results['queries_without_negatives']}")
    print()

    if triplet_results['problematic_queries']:
        print("Exemplos de queries problemáticas (sem positivos >= 2):")
        for query_id, pos_t1, neg in triplet_results['problematic_queries'][:5]:
            print(f"  {query_id}: {pos_t1} docs com rel>=1, {neg} negativos")
        print()

    # Análise por categoria
    print("=" * 80)
    print("3. ANÁLISE POR CATEGORIA DE DOCUMENTO")
    print("=" * 80)
    df_categories = analyze_by_category(ground_truth)
    print(df_categories.to_string(index=False))
    print()

    # Recomendações
    print("=" * 80)
    print("4. RECOMENDAÇÕES PARA FINE-TUNING")
    print("=" * 80)

    print("📊 Dataset sizes recomendados:")
    print()

    t2_triplets = triplet_results['threshold_2']

    print(f"  Few-shot (500 triplas):")
    print(f"    - Usar ~2% das triplas disponíveis")
    print(f"    - Sampling estratificado por categoria")
    print()

    print(f"  Medium (5,000 triplas):")
    print(f"    - Usar ~20% das triplas disponíveis")
    print(f"    - Bom balanço entre custo e performance")
    print()

    print(f"  Full ({t2_triplets:,} triplas):")
    print(f"    - Usar todas as triplas disponíveis (threshold >= 2)")
    print(f"    - Máxima utilização dos dados anotados")
    print()

    print("🎯 Estratégia recomendada:")
    print("  1. Usar threshold >= 2 para positivos (mais conservador)")
    print("  2. Hard negatives: docs que apareceram no Top-10 mas são irrelevantes")
    print("  3. Splits: 70% train, 15% val, 15% test")
    print("  4. Sampling estratificado para manter distribuição de categorias")
    print()

    print("=" * 80)
    print("✅ Análise concluída!")
    print("=" * 80)

if __name__ == "__main__":
    main()
