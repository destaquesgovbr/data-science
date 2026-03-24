#!/usr/bin/env python3
"""
Intelligent corpus curation - selects 25 best docs per category.

Selection criteria:
- Agency diversity (avoid concentration)
- Size balance (7 short, 13 medium, 5 long)
- No duplicates
- Topic diversity
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
import random

random.seed(42)  # Reproducibility


def load_corpus():
    """Load all documents grouped by category."""
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"

    categories = defaultdict(list)

    for json_file in sorted(corpus_dir.glob("doc_*.json")):
        with open(json_file) as f:
            doc = json.load(f)
            doc['file_path'] = json_file
            categories[doc['category']].append(doc)

    return categories


def remove_duplicates(docs):
    """Remove duplicate documents based on title similarity."""
    seen_titles = {}
    unique_docs = []

    for doc in docs:
        # Normalize title for comparison
        title_key = doc['title'].lower().strip()[:100]

        if title_key not in seen_titles:
            seen_titles[title_key] = doc
            unique_docs.append(doc)
        else:
            print(f"    ⚠️  Duplicata removida: {doc['id']}")

    return unique_docs


def score_document(doc, agency_counts, target_sizes, current_sizes):
    """Score document based on selection criteria."""
    score = 0

    # Favor less represented agencies (diversity)
    agency = doc['metadata']['agency']
    agency_score = 1.0 / (agency_counts.get(agency, 0) + 1)
    score += agency_score * 10

    # Favor sizes we need more of
    size = doc['metadata']['size_category']
    needed = target_sizes.get(size, 0) - current_sizes.get(size, 0)
    if needed > 0:
        score += needed * 5

    # Slight preference for medium length (more informative)
    if 3000 <= doc['length'] <= 5500:
        score += 2

    return score


def select_documents(docs, n=25):
    """Select n documents with optimal diversity."""
    print(f"    📊 {len(docs)} docs disponíveis")

    # Remove duplicates first
    docs = remove_duplicates(docs)
    print(f"    ✅ {len(docs)} docs únicos")

    if len(docs) <= n:
        print(f"    ⚠️  Menos que {n} docs, retornando todos")
        return docs

    # Target distribution
    target_sizes = {
        'Curta': 7,
        'Média': 13,
        'Longa': 5
    }

    selected = []
    remaining = docs.copy()

    # Iterative selection
    while len(selected) < n and remaining:
        # Count current state
        agency_counts = Counter(d['metadata']['agency'] for d in selected)
        current_sizes = Counter(d['metadata']['size_category'] for d in selected)

        # Score all remaining documents
        scored = []
        for doc in remaining:
            score = score_document(doc, agency_counts, target_sizes, current_sizes)
            scored.append((score, doc))

        # Sort by score (descending) and pick best
        scored.sort(reverse=True, key=lambda x: x[0])
        best_doc = scored[0][1]

        selected.append(best_doc)
        remaining.remove(best_doc)

    return selected


def analyze_selection(docs, category_name):
    """Print analysis of selected documents."""
    agencies = Counter(d['metadata']['agency'] for d in docs)
    sizes = Counter(d['metadata']['size_category'] for d in docs)

    print(f"\n  📊 {category_name}:")
    print(f"    Total: {len(docs)} docs")
    print(f"    Órgãos únicos: {len(agencies)}")

    print(f"    Distribuição de tamanhos:")
    for size in ['Curta', 'Média', 'Longa']:
        count = sizes.get(size, 0)
        pct = (count / len(docs)) * 100 if docs else 0
        print(f"      {size:10} → {count:2} docs ({pct:.0f}%)")

    print(f"    Top 5 órgãos:")
    for agency, count in agencies.most_common(5):
        print(f"      {agency:20} → {count:2} docs")


def main():
    print("🔍 Carregando corpus...")
    categories = load_corpus()

    print(f"\n📂 Encontradas {len(categories)} categorias")
    print(f"📊 Total de documentos: {sum(len(docs) for docs in categories.values())}\n")

    print("="*60)
    print("🎯 INICIANDO CURADORIA INTELIGENTE")
    print("="*60)

    all_selected = {}
    all_removed = {}

    for category, docs in sorted(categories.items()):
        print(f"\n{'='*60}")
        print(f"📂 {category}")
        print(f"{'='*60}")

        selected = select_documents(docs, n=25)

        # Identify files to remove
        selected_paths = {doc['file_path'] for doc in selected}
        removed = [doc for doc in docs if doc['file_path'] not in selected_paths]

        all_selected[category] = selected
        all_removed[category] = removed

        analyze_selection(selected, category)

    # Summary
    print(f"\n{'='*60}")
    print("📊 RESUMO FINAL")
    print(f"{'='*60}")

    total_selected = sum(len(docs) for docs in all_selected.values())
    total_removed = sum(len(docs) for docs in all_removed.values())

    print(f"\n✅ Documentos selecionados: {total_selected}")
    print(f"🗑️  Documentos a remover: {total_removed}")

    # Confirm removal
    print(f"\n⚠️  ATENÇÃO: Isso vai DELETAR {total_removed} arquivos JSON!")
    response = input("Confirma remoção? (sim/não): ").strip().lower()

    if response == 'sim':
        print("\n🗑️  Removendo arquivos...")
        removed_count = 0
        for category, docs in all_removed.items():
            for doc in docs:
                doc['file_path'].unlink()
                removed_count += 1

        print(f"✅ {removed_count} arquivos removidos com sucesso!")

        # Final verification
        corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
        remaining = len(list(corpus_dir.glob("doc_*.json")))
        print(f"\n📊 Corpus final: {remaining} documentos")

        if remaining == 250:
            print("🎉 PERFEITO! Exatos 250 documentos (25 por categoria)")
        else:
            print(f"⚠️  Esperado: 250, Atual: {remaining}")
    else:
        print("\n❌ Operação cancelada. Nenhum arquivo foi removido.")


if __name__ == "__main__":
    main()
