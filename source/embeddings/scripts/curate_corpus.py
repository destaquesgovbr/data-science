#!/usr/bin/env python3
"""
Interactive corpus curation tool.

Helps select 250 news documents (25 per category × 10 categories)
with diverse profiles (short/medium/long).

Usage:
    python curate_corpus.py --explore         # Explore dataset
    python curate_corpus.py --auto           # Auto-select 250 docs
    python curate_corpus.py --manual         # Manual selection (interactive)
"""

import argparse
import pandas as pd
from pathlib import Path
import json


# Mapping from theme_1_level_1 to our 10 target categories
CATEGORY_MAPPING = {
    # New format (recent dataset)
    "Saúde": "Saúde",
    "Educação": "Educação",
    "Economia e Finanças": "Economia",
    "Meio Ambiente e Sustentabilidade": "Meio Ambiente",
    "Segurança Pública": "Segurança Pública",
    "Desenvolvimento Social": "Assistência Social",
    "Infraestrutura e Transportes": "Infraestrutura",
    "Cultura, Artes e Patrimônio": "Cultura",
    "Ciência, Tecnologia e Inovação": "Ciência e Tecnologia",
    "Agricultura, Pecuária e Abastecimento": "Agricultura",
    # Old format (for backwards compatibility)
    "03 - Saúde": "Saúde",
    "02 - Educação": "Educação",
    "01 - Economia": "Economia",
    "05 - Meio Ambiente e Sustentabilidade": "Meio Ambiente",
    "04 - Segurança Pública": "Segurança Pública",
    "10 - Assistência Social e Cidadania": "Assistência Social",
    "08 - Infraestrutura e Transporte": "Infraestrutura",
    "11 - Cultura e Patrimônio": "Cultura",
    "06 - Ciência, Tecnologia e Inovação": "Ciência e Tecnologia",
    "07 - Agricultura e Pecuária": "Agricultura",
}


def load_dataset():
    """Load downloaded dataset."""
    data_dir = Path(__file__).parent.parent / "data" / "raw"

    # Try recent file first
    recent_file = data_dir / "govbrnews_recent_10000.parquet"
    if recent_file.exists():
        print(f"📂 Loading: {recent_file.name}")
        return pd.read_parquet(recent_file)

    # Try sample file
    sample_file = data_dir / "govbrnews_sample_1000.parquet"
    if sample_file.exists():
        print(f"📂 Loading: {sample_file.name}")
        return pd.read_parquet(sample_file)

    raise FileNotFoundError(
        "No dataset found. Run download_recent.py first."
    )


def explore_dataset(df):
    """Show dataset exploration."""
    print(f"\n{'='*60}")
    print(f"📊 DATASET EXPLORATION")
    print(f"{'='*60}")

    print(f"\n📋 Total documents: {len(df)}")
    print(f"📅 Date range: {df['published_at'].min()} to {df['published_at'].max()}")

    # Map to target categories
    df['target_category'] = df['theme_1_level_1'].map(CATEGORY_MAPPING)

    print(f"\n🎯 Documents per TARGET CATEGORY:")
    print(df['target_category'].value_counts().sort_index())
    print(f"\n❌ Unmapped (will be excluded): {df['target_category'].isna().sum()}")

    # Text length distribution
    df['content_length'] = df['content'].str.len()

    print(f"\n📏 Content length distribution:")
    print(df['content_length'].describe())

    # Define size categories
    df['size_category'] = pd.cut(
        df['content_length'],
        bins=[0, 3000, 5500, float('inf')],
        labels=['Curta', 'Média', 'Longa']
    )

    print(f"\n📐 Size categories:")
    print(df['size_category'].value_counts())

    print(f"\n🔍 Size by target category:")
    crosstab = pd.crosstab(df['target_category'], df['size_category'])
    print(crosstab)

    # Agency diversity
    print(f"\n🏛️  Top 15 agencies:")
    print(df['agency'].value_counts().head(15))


def auto_select_corpus(df, docs_per_category=25):
    """Automatically select balanced corpus."""
    print(f"\n{'='*60}")
    print(f"🤖 AUTO-SELECTING {docs_per_category * 10} DOCUMENTS")
    print(f"{'='*60}")

    # Map categories
    df['target_category'] = df['theme_1_level_1'].map(CATEGORY_MAPPING)
    df = df[df['target_category'].notna()].copy()

    # Define size categories
    df['content_length'] = df['content'].str.len()
    df['size_category'] = pd.cut(
        df['content_length'],
        bins=[0, 3000, 5500, float('inf')],
        labels=['Curta', 'Média', 'Longa']
    )

    selected = []

    for category in sorted(CATEGORY_MAPPING.values()):
        cat_df = df[df['target_category'] == category]

        if len(cat_df) < docs_per_category:
            print(f"⚠️  {category}: only {len(cat_df)} docs available (need {docs_per_category})")
            selected.append(cat_df)
            continue

        # Target distribution: 7 curtas, 13 médias, 5 longas
        target_dist = {'Curta': 7, 'Média': 13, 'Longa': 5}

        cat_selected = []
        for size, target_n in target_dist.items():
            size_df = cat_df[cat_df['size_category'] == size]

            if len(size_df) >= target_n:
                # Sample with diversity (different agencies)
                sampled = size_df.groupby('agency', group_keys=False).apply(
                    lambda x: x.sample(min(len(x), max(1, target_n // 3)))
                ).sample(n=target_n, random_state=42)
                cat_selected.append(sampled)
            else:
                print(f"   ⚠️  {category}/{size}: only {len(size_df)} docs (need {target_n})")
                cat_selected.append(size_df)

        cat_selected = pd.concat(cat_selected)

        # If still need more, sample randomly
        if len(cat_selected) < docs_per_category:
            remaining = docs_per_category - len(cat_selected)
            available = cat_df[~cat_df.index.isin(cat_selected.index)]
            cat_selected = pd.concat([
                cat_selected,
                available.sample(n=min(remaining, len(available)), random_state=42)
            ])

        selected.append(cat_selected.head(docs_per_category))
        print(f"✅ {category}: {len(cat_selected.head(docs_per_category))} docs selected")

    result = pd.concat(selected)
    print(f"\n📊 Total selected: {len(result)} documents")

    return result


def export_corpus(df, output_dir=None):
    """Export selected corpus to JSON files."""
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / "corpus"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n💾 Exporting to: {output_dir}")

    # Sort by category for consistent IDs
    df = df.sort_values(['target_category', 'published_at'])

    # Category to ID mapping
    cat_to_id = {cat: i for i, cat in enumerate(sorted(CATEGORY_MAPPING.values()))}

    for idx, row in df.iterrows():
        cat_id = cat_to_id[row['target_category']]

        # Count docs in this category so far
        doc_num = len([f for f in output_dir.glob(f"doc_{cat_id:02d}_*.json")])

        doc_id = f"doc_{cat_id:02d}_{doc_num:02d}"

        doc = {
            "id": doc_id,
            "title": row['title'],
            "content": row['content'],
            "category": row['target_category'],
            "length": len(row['content']),
            "metadata": {
                "source_url": row['url'],
                "published_date": str(row['published_at']),
                "agency": row['agency'],
                "theme_level_1": row['theme_1_level_1'],
                "size_category": row['size_category']
            }
        }

        output_file = output_dir / f"{doc_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"✅ Exported {len(df)} documents")
    print(f"\n📂 Files saved in: {output_dir}")

    # Summary
    print(f"\n📊 Summary by category:")
    summary = df.groupby('target_category').agg({
        'content_length': ['count', 'mean', 'min', 'max']
    }).round(0)
    print(summary)


def main():
    parser = argparse.ArgumentParser(description="Curate corpus for embeddings evaluation")
    parser.add_argument("--explore", action="store_true", help="Explore dataset")
    parser.add_argument("--auto", action="store_true", help="Auto-select 250 docs")
    parser.add_argument("--docs-per-category", type=int, default=25, help="Docs per category (default: 25)")

    args = parser.parse_args()

    df = load_dataset()

    if args.explore:
        explore_dataset(df)
    elif args.auto:
        selected = auto_select_corpus(df, args.docs_per_category)
        export_corpus(selected)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
