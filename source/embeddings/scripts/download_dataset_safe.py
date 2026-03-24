#!/usr/bin/env python3
"""
Download govbrnews dataset safely (avoid threading issues).

Usage:
    python download_dataset_safe.py --sample 1000    # Download 1000 docs
    python download_dataset_safe.py --full           # Download all
"""

import argparse
from datasets import load_dataset
import pandas as pd
from pathlib import Path


def download_sample(n=1000):
    """Download sample of n documents."""
    print(f"📥 Downloading {n} documents from govbrnews...")

    # Load dataset
    dataset = load_dataset("nitaibezerra/govbrnews", split=f"train[:{n}]")

    print(f"✅ Loaded {len(dataset)} documents")

    # Convert to pandas
    df = dataset.to_pandas()

    # Show info
    print(f"\n📊 Dataset shape: {df.shape}")
    print(f"📋 Columns: {list(df.columns)}")

    # Categories
    if 'category' in df.columns:
        print(f"\n📂 Categories (top 10):")
        print(df['category'].value_counts().head(10))

    # Themes
    if 'theme_1_level_1' in df.columns:
        print(f"\n🎯 Themes level 1 (top 10):")
        print(df['theme_1_level_1'].value_counts().head(10))

    # Text length
    if 'content' in df.columns:
        df['content_length'] = df['content'].str.len()
        print(f"\n📏 Content length statistics:")
        print(df['content_length'].describe())

    # Save
    output_dir = Path(__file__).parent.parent / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"govbrnews_sample_{n}.parquet"
    df.to_parquet(output_file, index=False)

    print(f"\n💾 Saved to: {output_file}")
    return df


def download_full():
    """Download full dataset."""
    print(f"📥 Downloading FULL govbrnews dataset...")
    print("⚠️  This may take 5-10 minutes...")

    # Load full dataset
    dataset = load_dataset("nitaibezerra/govbrnews", split="train")

    print(f"✅ Loaded {len(dataset)} documents")

    # Convert to pandas
    df = dataset.to_pandas()

    print(f"\n📊 Dataset shape: {df.shape}")

    # Save
    output_dir = Path(__file__).parent.parent / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "govbrnews_full.parquet"
    df.to_parquet(output_file, index=False)

    print(f"\n💾 Saved to: {output_file}")
    print(f"📊 Total documents: {len(df)}")

    if 'category' in df.columns:
        print(f"\n📂 Categories distribution:")
        print(df['category'].value_counts())

    return df


def main():
    parser = argparse.ArgumentParser(description="Download govbrnews dataset")
    parser.add_argument(
        "--sample",
        type=int,
        metavar="N",
        help="Download N sample documents (recommended: start with 1000)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Download full dataset (~300k docs)"
    )

    args = parser.parse_args()

    if args.sample:
        download_sample(args.sample)
    elif args.full:
        download_full()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
