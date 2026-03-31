#!/usr/bin/env python3
"""
Create ground truth relevance annotations.

Two modes:
1. Interactive: Manual annotation with UI
2. Semi-auto: Use anchor docs as perfect matches (score=3), others need annotation

Ground truth format:
{
  "q001": {
    "doc_01_08": 3,  # Very relevant (anchor doc)
    "doc_01_02": 2,  # Relevant
    "doc_03_04": 1,  # Somewhat relevant
    "doc_05_01": 0   # Not relevant
  },
  ...
}

Relevance scale:
  0 = Irrelevant (não responde à query)
  1 = Somewhat relevant (menciona tema mas não responde diretamente)
  2 = Relevant (responde parcialmente à query)
  3 = Very relevant (responde completamente à query)

Usage:
    # Start with anchor docs only (automatic)
    python create_ground_truth.py --mode anchor-only

    # Interactive annotation for top-K results
    python create_ground_truth.py --mode interactive --model bge-m3 --top-k 20

    # Manual annotation from scratch
    python create_ground_truth.py --mode manual
"""

import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict


def load_queries():
    """Load queries from template."""
    query_file = Path(__file__).parent.parent / "data" / "query_template_85.json"

    with open(query_file) as f:
        queries_data = json.load(f)

    queries = {}
    for q in queries_data:
        query_text = q.get('query_text', '').strip()
        if not query_text:
            query_text = q.get('recommended_query', '').strip()

        if query_text:
            queries[q['query_id']] = {
                'text': query_text,
                'anchor_doc_id': q['anchor_doc_id'],
                'category': q['category']
            }

    return queries


def load_corpus():
    """Load corpus documents."""
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"

    documents = {}

    for json_file in sorted(corpus_dir.glob("doc_*.json")):
        with open(json_file) as f:
            doc = json.load(f)
            documents[doc['id']] = {
                'title': doc['title'],
                'content': doc['content'],
                'category': doc['category']
            }

    return documents


def create_anchor_only(queries: Dict, documents: Dict) -> Dict:
    """
    Create ground truth with only anchor documents marked.

    Anchor docs get relevance=3 (perfect match).
    All others are left unannotated (to be filled later).

    This is a good starting point.
    """

    print("📝 Criando ground truth com apenas documentos âncora...\n")

    ground_truth = {}

    for query_id, query_info in queries.items():
        anchor_doc_id = query_info['anchor_doc_id']

        # Start with anchor doc = 3 (very relevant)
        ground_truth[query_id] = {
            anchor_doc_id: 3
        }

        print(f"   {query_id}: '{query_info['text'][:50]}...'")
        print(f"      Âncora: {anchor_doc_id} (score=3)")

    print(f"\n✅ Ground truth criado para {len(ground_truth)} queries")
    print("   (apenas documentos âncora anotados)")

    return ground_truth


def load_search_results(model_id: str) -> Dict:
    """Load search results from a model."""
    results_file = Path(__file__).parent.parent / "results" / "search_results" / f"{model_id}_results.json"

    if not results_file.exists():
        raise FileNotFoundError(f"Resultados não encontrados: {results_file}")

    with open(results_file) as f:
        results = json.load(f)

    return results


def interactive_annotation(
    queries: Dict,
    documents: Dict,
    model_id: str,
    top_k: int = 20
) -> Dict:
    """
    Interactive annotation of top-K results.

    Shows query + document and asks user to rate relevance.
    """

    print(f"🤝 Anotação Interativa")
    print(f"   Modelo base: {model_id}")
    print(f"   Top-K: {top_k}")
    print(f"   Queries: {len(queries)}\n")

    # Load search results
    try:
        search_results = load_search_results(model_id)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("   Execute semantic_search.py primeiro!")
        return {}

    ground_truth = {}

    # Instructions
    print("="*70)
    print("INSTRUÇÕES")
    print("="*70)
    print("\nPara cada query + documento, avalie a relevância:")
    print("  0 = Irrelevante")
    print("  1 = Pouco relevante (menciona tema)")
    print("  2 = Relevante (responde parcialmente)")
    print("  3 = Muito relevante (responde completamente)")
    print("  s = Pular este documento")
    print("  q = Sair e salvar")
    print("\n" + "="*70 + "\n")

    total_annotations = 0

    try:
        for query_id in sorted(queries.keys()):
            query_info = queries[query_id]

            # Get top-K results for this query
            if query_id not in search_results:
                continue

            results = search_results[query_id]['results'][:top_k]

            print(f"\n{'='*70}")
            print(f"Query: {query_id}")
            print(f"{'='*70}")
            print(f"Texto: \"{query_info['text']}\"")
            print(f"Categoria: {query_info['category']}")
            print(f"Âncora: {query_info['anchor_doc_id']}")
            print()

            query_annotations = {}

            for i, result in enumerate(results, 1):
                doc_id = result['doc_id']
                score = result['score']

                # Skip if already annotated
                if doc_id in query_annotations:
                    continue

                doc = documents[doc_id]

                print(f"\n--- Documento {i}/{top_k} (score: {score:.3f}) ---")
                print(f"ID: {doc_id}")
                print(f"Título: {doc['title']}")
                print(f"\nConteúdo (preview):\n{doc['content'][:400]}...")
                print()

                while True:
                    relevance_input = input("Relevância (0-3, s=skip, q=quit): ").strip().lower()

                    if relevance_input == 'q':
                        raise KeyboardInterrupt

                    if relevance_input == 's':
                        break

                    if relevance_input in ['0', '1', '2', '3']:
                        relevance = int(relevance_input)
                        query_annotations[doc_id] = relevance
                        total_annotations += 1
                        print(f"✓ Anotado: {doc_id} = {relevance}")
                        break
                    else:
                        print("❌ Entrada inválida. Use 0-3, s, ou q")

            ground_truth[query_id] = query_annotations

            print(f"\n✅ Query {query_id} concluída ({len(query_annotations)} anotações)")

    except KeyboardInterrupt:
        print("\n\n⚠️  Anotação interrompida pelo usuário")

    print(f"\n{'='*70}")
    print("📊 RESUMO DA ANOTAÇÃO")
    print(f"{'='*70}")
    print(f"Queries anotadas: {len(ground_truth)}")
    print(f"Total de anotações: {total_annotations}")

    return ground_truth


def save_ground_truth(ground_truth: Dict):
    """Save ground truth to file."""
    output_dir = Path(__file__).parent.parent / "data" / "annotations"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "ground_truth.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Ground truth salvo em: {output_file}")

    # Statistics
    total_queries = len(ground_truth)
    total_annotations = sum(len(docs) for docs in ground_truth.values())

    print(f"\n📊 Estatísticas:")
    print(f"   Queries: {total_queries}")
    print(f"   Anotações: {total_annotations}")
    print(f"   Média: {total_annotations/total_queries:.1f} docs por query")

    # Distribution of relevance scores
    all_scores = []
    for docs in ground_truth.values():
        all_scores.extend(docs.values())

    if all_scores:
        print(f"\n   Distribuição de relevância:")
        for score in [0, 1, 2, 3]:
            count = all_scores.count(score)
            pct = (count / len(all_scores)) * 100
            print(f"      {score}: {count:4d} ({pct:5.1f}%)")


def merge_ground_truth(existing: Dict, new: Dict) -> Dict:
    """Merge new annotations with existing ones."""
    merged = existing.copy()

    for query_id, annotations in new.items():
        if query_id in merged:
            # Merge annotations, new values override existing
            merged[query_id].update(annotations)
        else:
            merged[query_id] = annotations

    return merged


def main():
    """Main annotation routine."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Create ground truth relevance annotations",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--mode", required=True,
                        choices=["anchor-only", "interactive", "manual"],
                        help="Annotation mode")
    parser.add_argument("--model", default="bge-m3",
                        help="Model to use for interactive mode (default: bge-m3)")
    parser.add_argument("--top-k", type=int, default=20,
                        help="Number of top results to annotate (default: 20)")
    parser.add_argument("--merge", action="store_true",
                        help="Merge with existing ground truth")

    args = parser.parse_args()

    print("="*70)
    print("📝 CRIAÇÃO DE GROUND TRUTH")
    print("="*70)

    # Load data
    print("\n📂 Carregando dados...")
    queries = load_queries()
    documents = load_corpus()

    print(f"✅ {len(queries)} queries carregadas")
    print(f"✅ {len(documents)} documentos carregados")

    # Load existing ground truth if merging
    existing_gt = {}
    if args.merge:
        gt_file = Path(__file__).parent.parent / "data" / "annotations" / "ground_truth.json"
        if gt_file.exists():
            with open(gt_file) as f:
                existing_gt = json.load(f)
            print(f"✅ Ground truth existente: {len(existing_gt)} queries")

    # Create ground truth based on mode
    if args.mode == "anchor-only":
        ground_truth = create_anchor_only(queries, documents)

    elif args.mode == "interactive":
        ground_truth = interactive_annotation(
            queries,
            documents,
            model_id=args.model,
            top_k=args.top_k
        )

    elif args.mode == "manual":
        print("\n❌ Modo manual ainda não implementado")
        print("   Use --mode anchor-only ou --mode interactive")
        return 1

    # Merge if requested
    if args.merge and existing_gt:
        print("\n🔄 Mesclando com ground truth existente...")
        ground_truth = merge_ground_truth(existing_gt, ground_truth)

    # Save
    if ground_truth:
        save_ground_truth(ground_truth)
        return 0
    else:
        print("\n⚠️  Nenhuma anotação criada")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
