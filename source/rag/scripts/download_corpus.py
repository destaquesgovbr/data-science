#!/usr/bin/env python3
"""
Download GovBR News Corpus from HuggingFace

Downloads 50k news documents from nitaibezerra/govbrnews dataset
and stores in local PostgreSQL as source repository for testing.

Usage:
    python scripts/download_corpus.py [--limit 50000]
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg
from psycopg.types.json import Jsonb
from datasets import load_dataset
from datetime import datetime
from tqdm import tqdm
import argparse
import json

# Database connection
CONN_STRING = "host=localhost port=5433 dbname=news_db user=rag_user password=rag_password_2024"

def create_corpus_table(conn):
    """Create corpus repository table (identical to news_documents)."""

    with conn.cursor() as cur:
        # Drop if exists
        cur.execute("DROP TABLE IF EXISTS news_corpus_repository CASCADE")

        # Create table (same structure as news_documents)
        cur.execute("""
            CREATE TABLE news_corpus_repository (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                url TEXT,
                source_agency TEXT,
                category TEXT,
                published_at TIMESTAMP,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),

                -- Additional fields from HuggingFace dataset
                unique_id TEXT UNIQUE,
                subtitle TEXT,
                editorial_lead TEXT,
                summary TEXT,
                tags TEXT[],
                updated_at TIMESTAMP
            )
        """)

        # Create indexes
        cur.execute("CREATE INDEX idx_corpus_published ON news_corpus_repository(published_at DESC)")
        cur.execute("CREATE INDEX idx_corpus_category ON news_corpus_repository(category)")
        cur.execute("CREATE INDEX idx_corpus_agency ON news_corpus_repository(source_agency)")
        cur.execute("CREATE INDEX idx_corpus_unique_id ON news_corpus_repository(unique_id)")

        conn.commit()

    print("Table news_corpus_repository created")


def parse_datetime(date_str):
    """Parse datetime from various formats."""
    if not date_str:
        return None

    try:
        # Try ISO format first
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except:
        try:
            # Try common formats
            for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
        except:
            pass

    return None


def download_and_insert(conn, limit=50000):
    """Download dataset and insert into PostgreSQL."""

    print(f"\nDownloading dataset from HuggingFace (limit: {limit:,})...")
    print("Note: Will download first {limit:,} documents from dataset")
    print("This may take a few minutes...\n")

    # Load dataset (streaming mode for memory efficiency)
    dataset = load_dataset("nitaibezerra/govbrnews", split="train", streaming=True)

    inserted = 0
    skipped = 0
    batch = []
    batch_size = 100
    processed = 0

    with tqdm(total=limit, desc="Downloading & inserting") as pbar:
        for item in dataset:
            processed += 1

            if inserted >= limit:
                break

            # Extract fields
            try:
                title = item.get('title', '').strip()
                content = item.get('content', '').strip()

                # Skip if missing essential fields
                if not title or not content:
                    skipped += 1
                    continue

                # Parse datetime
                published_at = parse_datetime(item.get('published_at'))
                updated_at = parse_datetime(item.get('updated_datetime'))

                # Extract category from theme hierarchy
                category = (
                    item.get('theme_level_1') or
                    item.get('category') or
                    'Uncategorized'
                )

                # Build metadata
                metadata = {
                    'subtitle': item.get('subtitle'),
                    'editorial_lead': item.get('editorial_lead'),
                    'image': item.get('image'),
                    'theme_level_2': item.get('theme_level_2'),
                    'theme_level_3': item.get('theme_level_3'),
                }

                # Remove None values
                metadata = {k: v for k, v in metadata.items() if v}

                # Tags (convert to array)
                tags = item.get('tags', [])
                if isinstance(tags, str):
                    tags = [tags]

                # Add to batch
                batch.append({
                    'unique_id': item.get('unique_id'),
                    'title': title,
                    'content': content,
                    'url': item.get('url'),
                    'source_agency': item.get('agency'),
                    'category': category,
                    'published_at': published_at,
                    'updated_at': updated_at,
                    'subtitle': item.get('subtitle'),
                    'editorial_lead': item.get('editorial_lead'),
                    'summary': item.get('summary'),
                    'tags': tags,
                    'metadata': metadata
                })

                # Insert batch
                if len(batch) >= batch_size:
                    count = insert_batch(conn, batch)
                    inserted += count
                    pbar.update(count)
                    batch = []

            except Exception as e:
                skipped += 1
                if skipped % 100 == 0:
                    print(f"\nWarning: Skipped {skipped} documents due to errors")
                continue

    # Insert remaining
    if batch:
        count = insert_batch(conn, batch)
        inserted += count
        pbar.update(count)

    print(f"\n\nInserted: {inserted:,} documents")
    print(f"Skipped:  {skipped:,} documents")

    return inserted


def insert_batch(conn, batch):
    """Insert batch of documents."""

    inserted_count = 0
    with conn.cursor() as cur:
        for doc in batch:
            try:
                cur.execute("""
                    INSERT INTO news_corpus_repository
                    (unique_id, title, content, url, source_agency, category,
                     published_at, updated_at, subtitle, editorial_lead,
                     summary, tags, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (unique_id) DO NOTHING
                """, (
                    doc['unique_id'],
                    doc['title'],
                    doc['content'],
                    doc['url'],
                    doc['source_agency'],
                    doc['category'],
                    doc['published_at'],
                    doc['updated_at'],
                    doc['subtitle'],
                    doc['editorial_lead'],
                    doc['summary'],
                    doc['tags'],
                    Jsonb(doc['metadata'])  # Convert dict to JSONB
                ))
                if cur.rowcount > 0:
                    inserted_count += 1
            except Exception as e:
                # Log first error for debugging
                if inserted_count == 0:
                    print(f"\nError inserting document: {e}")
                    print(f"Document unique_id: {doc.get('unique_id')}")
                continue

        conn.commit()

    return inserted_count


def show_statistics(conn):
    """Show corpus statistics."""

    with conn.cursor() as cur:
        # Total count
        cur.execute("SELECT COUNT(*) FROM news_corpus_repository")
        total = cur.fetchone()[0]

        # By category
        cur.execute("""
            SELECT category, COUNT(*) as count
            FROM news_corpus_repository
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10
        """)
        categories = cur.fetchall()

        # By agency
        cur.execute("""
            SELECT source_agency, COUNT(*) as count
            FROM news_corpus_repository
            GROUP BY source_agency
            ORDER BY count DESC
            LIMIT 10
        """)
        agencies = cur.fetchall()

        # Date range
        cur.execute("""
            SELECT
                MIN(published_at) as oldest,
                MAX(published_at) as newest
            FROM news_corpus_repository
            WHERE published_at IS NOT NULL
        """)
        date_range = cur.fetchone()

        print("\n" + "="*60)
        print("CORPUS STATISTICS")
        print("="*60)
        print(f"\nTotal documents: {total:,}")

        if date_range[0]:
            print(f"\nDate range: {date_range[0].strftime('%Y-%m-%d')} to {date_range[1].strftime('%Y-%m-%d')}")

        print("\nTop 10 categories:")
        for cat, count in categories:
            print(f"  {cat:40} {count:6,} docs")

        print("\nTop 10 agencies:")
        for agency, count in agencies:
            agency_name = agency or 'Unknown'
            print(f"  {agency_name:40} {count:6,} docs")

        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description='Download GovBR News corpus')
    parser.add_argument(
        '--limit',
        type=int,
        default=50000,
        help='Number of documents to download (default: 50000)'
    )
    parser.add_argument(
        '--skip-create',
        action='store_true',
        help='Skip table creation (append to existing table)'
    )

    args = parser.parse_args()

    print("="*60)
    print("GovBR News Corpus Download")
    print("="*60)
    print(f"\nDataset: nitaibezerra/govbrnews")
    print(f"Limit:   {args.limit:,} documents")
    print(f"Target:  PostgreSQL (localhost:5433/news_db)")
    print(f"Table:   news_corpus_repository")
    print()

    try:
        # Connect to database
        with psycopg.connect(CONN_STRING) as conn:
            # Create table
            if not args.skip_create:
                print("Creating table...")
                create_corpus_table(conn)
            else:
                print("Using existing table...")

            # Download and insert
            total = download_and_insert(conn, limit=args.limit)

            # Show statistics
            show_statistics(conn)

            print("\nCorpus download complete!")
            print(f"\nQuery examples:")
            print(f"  SELECT COUNT(*) FROM news_corpus_repository;")
            print(f"  SELECT category, COUNT(*) FROM news_corpus_repository GROUP BY category;")
            print()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
