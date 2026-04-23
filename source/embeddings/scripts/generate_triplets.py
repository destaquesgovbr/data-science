#!/usr/bin/env python3
"""
Generate training triplets from ground truth annotations.

Creates (query, positive, negative) triplets for fine-tuning embedding models.
Supports stratified sampling and train/val/test splits.

Output format compatible with sentence-transformers:
- CSV with columns: query, positive, negative
- JSON with list of {query, positive, negative} objects
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
import pandas as pd

# Seed for reproducibility
random.seed(42)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "data" / "finetuning"

# Input files
QUERIES_FILE = DATA_DIR / "query_template_85.json"
CORPUS_DIR = DATA_DIR / "corpus"
GROUND_TRUTH_FILE = DATA_DIR / "annotations" / "ground_truth.json"


def load_queries() -> Dict[str, Dict]:
    """Load and expand queries with variants."""
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        queries_data = json.load(f)

    queries = {}

    for q in queries_data:
        base_query_id = q['query_id']
        anchor_doc_id = q['anchor_doc_id']
        category = q['category']

        # Get all variants
        variants = q.get('variants', [])

        if not variants:
            # Fallback to recommended_query
            query_text = q.get('recommended_query', '').strip()
            if query_text:
                queries[f"{base_query_id}_v1"] = {
                    'text': query_text,
                    'anchor_doc_id': anchor_doc_id,
                    'category': category,
                    'base_query_id': base_query_id
                }
        else:
            # Expand variants
            for i, variant in enumerate(variants, 1):
                variant_text = variant.get('text', '').strip()
                if variant_text:
                    queries[f"{base_query_id}_v{i}"] = {
                        'text': variant_text,
                        'anchor_doc_id': anchor_doc_id,
                        'category': category,
                        'base_query_id': base_query_id,
                        'variant_num': i,
                        'variant_type': variant.get('type', 'unknown')
                    }

    return queries


def load_corpus() -> Dict[str, Dict]:
    """Load corpus documents."""
    documents = {}

    for json_file in sorted(CORPUS_DIR.glob("doc_*.json")):
        with open(json_file, 'r', encoding='utf-8') as f:
            doc = json.load(f)
            documents[doc['id']] = {
                'title': doc['title'],
                'content': doc['content'],
                'category': doc['category']
            }

    return documents


def load_ground_truth() -> Dict:
    """Load ground truth annotations."""
    with open(GROUND_TRUTH_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_triplets(
    queries: Dict,
    documents: Dict,
    ground_truth: Dict,
    positive_threshold: int = 2
) -> List[Dict]:
    """
    Extract triplets from annotations.

    Args:
        queries: Query texts by ID
        documents: Document texts by ID
        ground_truth: Relevance annotations
        positive_threshold: Minimum relevance for positive (2 = relevant/very relevant)

    Returns:
        List of {query_id, query, positive_id, positive, negative_id, negative, category}
    """
    triplets = []

    for query_id, annotations in ground_truth.items():
        if query_id not in queries:
            print(f"⚠️  Query {query_id} not found in query template, skipping")
            continue

        query_text = queries[query_id]['text']
        query_category = queries[query_id]['category']

        # Separate positives and negatives
        positives = [doc_id for doc_id, rel in annotations.items() if rel >= positive_threshold]
        negatives = [doc_id for doc_id, rel in annotations.items() if rel == 0]

        # Skip if no positives or negatives
        if not positives or not negatives:
            continue

        # Generate all possible triplets
        for pos_doc_id in positives:
            if pos_doc_id not in documents:
                print(f"⚠️  Document {pos_doc_id} not found in corpus, skipping")
                continue

            pos_text = f"{documents[pos_doc_id]['title']} {documents[pos_doc_id]['content']}"

            for neg_doc_id in negatives:
                if neg_doc_id not in documents:
                    print(f"⚠️  Document {neg_doc_id} not found in corpus, skipping")
                    continue

                neg_text = f"{documents[neg_doc_id]['title']} {documents[neg_doc_id]['content']}"

                triplets.append({
                    'query_id': query_id,
                    'query': query_text,
                    'positive_id': pos_doc_id,
                    'positive': pos_text,
                    'negative_id': neg_doc_id,
                    'negative': neg_text,
                    'category': query_category
                })

    return triplets


def stratified_split(
    triplets: List[Dict],
    train_size: float = 0.70,
    val_size: float = 0.15,
    test_size: float = 0.15
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Split triplets maintaining category distribution.

    Splits by base query to avoid data leakage (same query in train/test).
    """
    assert abs(train_size + val_size + test_size - 1.0) < 1e-6, "Sizes must sum to 1.0"

    # Group triplets by base query
    by_base_query = defaultdict(list)
    for triplet in triplets:
        base_query = triplet['query_id'].split('_')[0]  # q001_v1 -> q001
        by_base_query[base_query].append(triplet)

    # Get list of base queries
    base_queries = list(by_base_query.keys())
    random.shuffle(base_queries)

    # Calculate split points
    n_queries = len(base_queries)
    n_train = int(n_queries * train_size)
    n_val = int(n_queries * val_size)

    # Split base queries
    train_queries = base_queries[:n_train]
    val_queries = base_queries[n_train:n_train + n_val]
    test_queries = base_queries[n_train + n_val:]

    # Collect triplets for each split
    train_triplets = []
    val_triplets = []
    test_triplets = []

    for base_q in train_queries:
        train_triplets.extend(by_base_query[base_q])

    for base_q in val_queries:
        val_triplets.extend(by_base_query[base_q])

    for base_q in test_queries:
        test_triplets.extend(by_base_query[base_q])

    return train_triplets, val_triplets, test_triplets


def sample_few_shot(train_triplets: List[Dict], n_samples: int = 500) -> List[Dict]:
    """
    Sample few-shot subset with stratified sampling by category.
    """
    # Group by category
    by_category = defaultdict(list)
    for triplet in train_triplets:
        by_category[triplet['category']].append(triplet)

    # Calculate samples per category (proportional)
    category_counts = {cat: len(trips) for cat, trips in by_category.items()}
    total = sum(category_counts.values())

    few_shot = []
    for category, triplets_cat in by_category.items():
        # Proportional sampling
        n_cat = max(1, int(n_samples * len(triplets_cat) / total))
        n_cat = min(n_cat, len(triplets_cat))  # Don't sample more than available

        sampled = random.sample(triplets_cat, n_cat)
        few_shot.extend(sampled)

    # If we didn't reach target, sample more randomly
    if len(few_shot) < n_samples:
        remaining = n_samples - len(few_shot)
        pool = [t for t in train_triplets if t not in few_shot]
        if pool:
            few_shot.extend(random.sample(pool, min(remaining, len(pool))))

    return few_shot[:n_samples]


def save_triplets(triplets: List[Dict], output_path: Path, format: str = 'csv'):
    """Save triplets to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == 'csv':
        # Save as CSV (sentence-transformers compatible)
        df = pd.DataFrame([
            {
                'query': t['query'],
                'positive': t['positive'],
                'negative': t['negative']
            }
            for t in triplets
        ])
        df.to_csv(output_path, index=False, encoding='utf-8')

    elif format == 'json':
        # Save as JSON with metadata
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(triplets, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(triplets)} triplets to {output_path}")


def print_statistics(triplets: List[Dict], name: str):
    """Print statistics about triplet set."""
    print(f"\n{'='*60}")
    print(f"{name.upper()}")
    print(f"{'='*60}")

    # Total
    print(f"Total triplets: {len(triplets):,}")

    # By category
    by_category = defaultdict(int)
    for t in triplets:
        by_category[t['category']] += 1

    print(f"\nBy category:")
    for cat in sorted(by_category.keys()):
        count = by_category[cat]
        pct = (count / len(triplets)) * 100
        print(f"  {cat:20s}: {count:4d} ({pct:5.1f}%)")

    # Unique queries/docs
    unique_queries = len(set(t['query_id'] for t in triplets))
    unique_positives = len(set(t['positive_id'] for t in triplets))
    unique_negatives = len(set(t['negative_id'] for t in triplets))

    print(f"\nUnique elements:")
    print(f"  Queries:   {unique_queries}")
    print(f"  Positives: {unique_positives}")
    print(f"  Negatives: {unique_negatives}")


def main():
    print("=" * 80)
    print("GERAÇÃO DE TRIPLAS PARA FINE-TUNING")
    print("=" * 80)
    print()

    # Load data
    print("📂 Carregando dados...")
    queries = load_queries()
    print(f"  ✅ {len(queries)} queries carregadas")

    documents = load_corpus()
    print(f"  ✅ {len(documents)} documentos carregados")

    ground_truth = load_ground_truth()
    print(f"  ✅ {len(ground_truth)} queries anotadas")
    print()

    # Extract triplets
    print("🔄 Extraindo triplas (threshold >= 2)...")
    triplets = extract_triplets(queries, documents, ground_truth, positive_threshold=2)
    print(f"  ✅ {len(triplets):,} triplas extraídas")
    print()

    # Split
    print("✂️  Dividindo em train/val/test (70/15/15)...")
    train, val, test = stratified_split(triplets, train_size=0.70, val_size=0.15, test_size=0.15)
    print(f"  ✅ Train: {len(train):,} triplas")
    print(f"  ✅ Val:   {len(val):,} triplas")
    print(f"  ✅ Test:  {len(test):,} triplas")
    print()

    # Few-shot subset
    print("🎯 Criando subset few-shot (500 triplas)...")
    few_shot = sample_few_shot(train, n_samples=500)
    print(f"  ✅ Few-shot: {len(few_shot)} triplas")
    print()

    # Save all datasets
    print("💾 Salvando datasets...")
    print()

    # Full datasets (CSV for training, JSON with metadata)
    save_triplets(train, OUTPUT_DIR / "train.csv", format='csv')
    save_triplets(train, OUTPUT_DIR / "train_full.json", format='json')
    save_triplets(val, OUTPUT_DIR / "val.csv", format='csv')
    save_triplets(val, OUTPUT_DIR / "val_full.json", format='json')
    save_triplets(test, OUTPUT_DIR / "test.csv", format='csv')
    save_triplets(test, OUTPUT_DIR / "test_full.json", format='json')

    # Few-shot
    save_triplets(few_shot, OUTPUT_DIR / "train_fewshot.csv", format='csv')
    save_triplets(few_shot, OUTPUT_DIR / "train_fewshot.json", format='json')

    # Print statistics
    print_statistics(train, "Train Set")
    print_statistics(val, "Validation Set")
    print_statistics(test, "Test Set")
    print_statistics(few_shot, "Few-shot Set")

    print()
    print("=" * 80)
    print("✅ GERAÇÃO CONCLUÍDA!")
    print("=" * 80)
    print()
    print(f"📁 Arquivos salvos em: {OUTPUT_DIR}")
    print()
    print("Próximos passos:")
    print("  1. Revisar distribuição de categorias nos splits")
    print("  2. Iniciar fine-tuning com few-shot (500 triplas)")
    print("  3. Se resultados promissores, escalar para full dataset")
    print()


if __name__ == "__main__":
    main()
