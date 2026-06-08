#!/usr/bin/env python3
"""
Consolidate Corpus Script

Collects all news documents from various sources and creates a unified corpus
for indexing.

Usage:
    python consolidate_corpus.py [--output OUTPUT] [--min-docs MIN_DOCS]

Output: JSON file with all documents in standardized format
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import argparse

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def find_corpus_files(base_dir: Path) -> List[Path]:
    """Find all corpus JSON files."""

    corpus_files = []

    # Search patterns
    patterns = [
        "data/corpus/*.json",
        "data/corpus*/*.json",
        "../embeddings/data/corpus/*.json",
        "../embeddings/data/corpus*/*.json",
    ]

    for pattern in patterns:
        files = list(base_dir.glob(pattern))
        corpus_files.extend(files)

    # Deduplicate
    corpus_files = list(set(corpus_files))

    # Filter out non-document files
    corpus_files = [
        f for f in corpus_files
        if not f.name.startswith('corpus_')  # Avoid corpus_100.json, corpus_sample.json
        and f.name.startswith('doc_')
    ]

    return sorted(corpus_files)


def load_document(file_path: Path) -> Optional[Dict]:
    """Load and validate a single document."""

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            doc = json.load(f)

        # Validate required fields
        required = ['id', 'title', 'content']
        if not all(field in doc for field in required):
            print(f"⚠️  Skipping {file_path.name}: missing required fields")
            return None

        # Ensure metadata exists
        if 'metadata' not in doc:
            doc['metadata'] = {}

        # Extract fields
        standardized = {
            'id': doc['id'],
            'title': doc['title'],
            'content': doc['content'],
            'category': doc.get('category', 'Uncategorized'),
            'url': doc.get('metadata', {}).get('source_url'),
            'source_agency': doc.get('metadata', {}).get('agency', 'unknown'),
            'published_at': doc.get('metadata', {}).get('published_date'),
            'metadata': doc.get('metadata', {})
        }

        return standardized

    except json.JSONDecodeError as e:
        print(f"⚠️  Error parsing {file_path.name}: {e}")
        return None
    except Exception as e:
        print(f"⚠️  Error loading {file_path.name}: {e}")
        return None


def consolidate_corpus(
    base_dir: Path,
    output_file: Path,
    min_docs: int = 100
) -> int:
    """
    Consolidate all corpus files into a single JSON.

    Returns:
        Number of documents consolidated
    """

    print("🔍 Searching for corpus files...")
    corpus_files = find_corpus_files(base_dir)

    print(f"📂 Found {len(corpus_files)} corpus files")

    if len(corpus_files) == 0:
        print("❌ No corpus files found!")
        print(f"   Searched in: {base_dir}")
        return 0

    # Load all documents
    print("\n📖 Loading documents...")
    documents = []
    seen_ids = set()

    for i, file_path in enumerate(corpus_files, 1):
        if i % 50 == 0:
            print(f"   Progress: {i}/{len(corpus_files)}")

        doc = load_document(file_path)
        if doc and doc['id'] not in seen_ids:
            documents.append(doc)
            seen_ids.add(doc['id'])

    print(f"\n✅ Loaded {len(documents)} unique documents")

    if len(documents) < min_docs:
        print(f"⚠️  Warning: Only {len(documents)} documents found (minimum: {min_docs})")
        print("   Consider collecting more data before indexing")

    # Sort by published date (most recent first)
    documents_with_dates = [
        d for d in documents
        if d.get('published_at')
    ]
    documents_without_dates = [
        d for d in documents
        if not d.get('published_at')
    ]

    documents_with_dates.sort(
        key=lambda x: x['published_at'],
        reverse=True
    )

    sorted_documents = documents_with_dates + documents_without_dates

    # Statistics
    print("\n📊 Corpus Statistics:")
    print(f"   Total documents:      {len(sorted_documents)}")
    print(f"   With publication date: {len(documents_with_dates)}")
    print(f"   Without date:          {len(documents_without_dates)}")

    # Category breakdown
    categories = {}
    for doc in sorted_documents:
        cat = doc.get('category', 'Uncategorized')
        categories[cat] = categories.get(cat, 0) + 1

    print("\n   Top categories:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"     {cat:30} {count:4} docs")

    # Save consolidated corpus
    print(f"\n💾 Saving consolidated corpus to: {output_file}")

    output_data = {
        'metadata': {
            'total_documents': len(sorted_documents),
            'created_at': datetime.now().isoformat(),
            'source_files': len(corpus_files),
            'categories': len(categories)
        },
        'documents': sorted_documents
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Consolidated corpus saved: {len(sorted_documents)} documents")
    print(f"   File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

    return len(sorted_documents)


def main():
    parser = argparse.ArgumentParser(description='Consolidate corpus from multiple sources')
    parser.add_argument(
        '--output',
        type=str,
        default='data/corpus_consolidated.json',
        help='Output file path (default: data/corpus_consolidated.json)'
    )
    parser.add_argument(
        '--min-docs',
        type=int,
        default=1000,
        help='Minimum expected documents (default: 1000)'
    )
    parser.add_argument(
        '--base-dir',
        type=str,
        default='.',
        help='Base directory to search (default: current directory)'
    )

    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    output_file = Path(args.output)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║            Corpus Consolidation Script                      ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    print(f"Base directory: {base_dir}")
    print(f"Output file:    {output_file}")
    print(f"Min docs:       {args.min_docs}\n")

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Consolidate
    total_docs = consolidate_corpus(base_dir, output_file, args.min_docs)

    if total_docs == 0:
        print("\n❌ No documents consolidated!")
        sys.exit(1)

    print("\n" + "="*64)
    print("✅ Consolidation complete!")
    print("="*64)
    print("\nNext steps:")
    print(f"  1. Review: cat {output_file} | jq '.metadata'")
    print(f"  2. Index:  python deploy/batch_indexing.py --gpu")
    print("")


if __name__ == "__main__":
    main()
