#!/usr/bin/env python3
"""
Download most recent news from govbrnews dataset.

Usage:
    python download_recent.py --top 10000
"""

import argparse
from datasets import load_dataset
import pandas as pd
from pathlib import Path


def download_recent(n=10000):
    """Download n most recent documents."""
    print(f"📥 Downloading most recent {n} documents from govbrnews...")
    print("⚠️  Step 1/3: Loading dataset (may take 5-10 minutes)...")

    # Load full dataset
    dataset = load_dataset("nitaibezerra/govbrnews", split="train")

    print(f"✅ Loaded {len(dataset)} total documents")
    print(f"⚠️  Step 2/3: Converting to pandas and sorting by date...")

    # Convert to pandas
    df = dataset.to_pandas()

    # Sort by published_at (most recent first)
    df = df.sort_values('published_at', ascending=False)

    # Take top n
    df_recent = df.head(n).copy()

    print(f"✅ Selected {len(df_recent)} most recent documents")
    print(f"📅 Date range:")
    print(f"   Most recent: {df_recent['published_at'].max()}")
    print(f"   Oldest: {df_recent['published_at'].min()}")

    # Show stats
    print(f"\n📊 Dataset shape: {df_recent.shape}")

    # Themes
    if 'theme_1_level_1' in df_recent.columns:
        print(f"\n🎯 Themes level 1 (top 15):")
        print(df_recent['theme_1_level_1'].value_counts().head(15))

    # Text length
    if 'content' in df_recent.columns:
        df_recent['content_length'] = df_recent['content'].str.len()
        print(f"\n📏 Content length statistics:")
        print(df_recent['content_length'].describe())

    # Save
    print(f"\n⚠️  Step 3/3: Saving to parquet...")
    output_dir = Path(__file__).parent.parent / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"govbrnews_recent_{n}.parquet"
    df_recent.to_parquet(output_file, index=False)

    print(f"\n💾 Saved to: {output_file}")
    print(f"📊 Total documents: {len(df_recent)}")

    # File size
    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"💾 File size: {file_size_mb:.1f} MB")

    return df_recent


def main():
    parser = argparse.ArgumentParser(
        description="Download most recent govbrnews documents"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10000,
        help="Number of most recent documents to download (default: 10000)"
    )

    args = parser.parse_args()
    download_recent(args.top)


if __name__ == "__main__":
    main()
