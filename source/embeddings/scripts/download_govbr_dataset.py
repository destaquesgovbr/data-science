#!/usr/bin/env python3
"""
Download and explore govbrnews dataset from HuggingFace.

Usage:
    python download_govbr_dataset.py --info          # Show dataset info
    python download_govbr_dataset.py --sample 10     # Show sample
    python download_govbr_dataset.py --download      # Download full dataset
"""

import argparse
from datasets import load_dataset
import pandas as pd
from pathlib import Path


def show_info():
    """Show dataset information without downloading."""
    print("📊 Loading dataset info from HuggingFace...")

    # Load only first few examples to explore structure
    dataset = load_dataset("nitaibezerra/govbrnews", split="train", streaming=True)

    print("\n✅ Dataset: nitaibezerra/govbrnews")
    print(f"📋 Features: {dataset.features}")

    # Get first example
    first_example = next(iter(dataset))
    print(f"\n📄 First example fields:")
    for key, value in first_example.items():
        if isinstance(value, str) and len(value) > 100:
            print(f"  - {key}: {value[:100]}... ({len(value)} chars)")
        else:
            print(f"  - {key}: {value}")


def show_sample(n=10):
    """Show sample of n documents."""
    print(f"📊 Loading {n} sample documents...")

    dataset = load_dataset("nitaibezerra/govbrnews", split="train", streaming=True)

    samples = []
    for i, example in enumerate(dataset):
        if i >= n:
            break
        samples.append(example)

    df = pd.DataFrame(samples)

    print(f"\n✅ Loaded {len(df)} documents")
    print(f"\n📋 Columns: {list(df.columns)}")
    print(f"\n📊 Dataset shape: {df.shape}")

    if 'category' in df.columns or 'categoria' in df.columns:
        cat_col = 'category' if 'category' in df.columns else 'categoria'
        print(f"\n📂 Categories:\n{df[cat_col].value_counts()}")

    # Show text length distribution
    if 'content' in df.columns or 'texto' in df.columns:
        text_col = 'content' if 'content' in df.columns else 'texto'
        df['text_length'] = df[text_col].str.len()
        print(f"\n📏 Text length statistics:")
        print(df['text_length'].describe())

    print(f"\n📄 Sample documents:")
    print(df.head())


def download_full():
    """Download full dataset locally."""
    print("📥 Downloading full govbrnews dataset...")
    print("⚠️  This may take several minutes...")

    # Download full dataset
    dataset = load_dataset("nitaibezerra/govbrnews")

    print(f"\n✅ Downloaded!")
    print(f"📊 Dataset info:")
    print(dataset)

    # Save to local cache
    output_dir = Path(__file__).parent.parent / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert to pandas and save as parquet
    train_df = dataset['train'].to_pandas()
    output_file = output_dir / "govbrnews_full.parquet"
    train_df.to_parquet(output_file)

    print(f"\n💾 Saved to: {output_file}")
    print(f"📊 Total documents: {len(train_df)}")

    if 'category' in train_df.columns or 'categoria' in train_df.columns:
        cat_col = 'category' if 'category' in train_df.columns else 'categoria'
        print(f"\n📂 Categories distribution:")
        print(train_df[cat_col].value_counts())


def main():
    parser = argparse.ArgumentParser(
        description="Download and explore govbrnews dataset"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show dataset information"
    )
    parser.add_argument(
        "--sample",
        type=int,
        metavar="N",
        help="Show N sample documents"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download full dataset locally"
    )

    args = parser.parse_args()

    if args.info:
        show_info()
    elif args.sample:
        show_sample(args.sample)
    elif args.download:
        download_full()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
