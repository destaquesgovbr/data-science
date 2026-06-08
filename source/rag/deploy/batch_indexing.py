#!/usr/bin/env python3
"""
Batch Indexing Script with GPU Support

Indexes documents into PostgreSQL with BGE-M3 embeddings.
Optimized for GPU processing with batching.

Usage:
    # GPU mode (recommended for EC2 with L4)
    python batch_indexing.py --gpu --batch-size 32

    # CPU mode (fallback)
    python batch_indexing.py --cpu --batch-size 8

    # Incremental (skip existing docs)
    python batch_indexing.py --gpu --incremental

    # Clean start (drops existing data)
    python batch_indexing.py --gpu --clean
"""

import json
import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg
from psycopg.rows import dict_row
from sentence_transformers import SentenceTransformer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.table import Table

console = Console()

# Config
import os
CONN_STRING = os.environ.get('RAG_CONN_STRING', "host=localhost port=5433 dbname=news_db user=rag_user password=rag_pass")
CHUNK_SIZE = 500  # Characters per chunk
CHUNK_OVERLAP = 50


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence boundary
        if end < len(text):
            # Look for period, question mark, or exclamation
            for punct in ['. ', '? ', '! ', '\n']:
                last_punct = text[start:end].rfind(punct)
                if last_punct != -1:
                    end = start + last_punct + 1
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def clean_database(conn_string: str):
    """Drop all documents and chunks."""

    console.print("\n[yellow]⚠️  Cleaning database...[/yellow]")

    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE document_chunks CASCADE")
            cur.execute("TRUNCATE news_documents CASCADE")
            conn.commit()

    console.print("[green]✓ Database cleaned[/green]")


def get_existing_doc_ids(conn_string: str) -> set:
    """Get IDs of already indexed documents."""

    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT url FROM news_documents WHERE url IS NOT NULL")
            urls = {row[0] for row in cur.fetchall()}

    return urls


def index_documents(
    corpus_file: Path,
    embedder: SentenceTransformer,
    conn_string: str,
    batch_size: int = 32,
    incremental: bool = False
) -> Tuple[int, int, float]:
    """
    Index documents in batch mode.

    Returns:
        (docs_indexed, chunks_created, time_elapsed)
    """

    # Load corpus
    console.print(f"\n[cyan]📂 Loading corpus from {corpus_file}...[/cyan]")

    with open(corpus_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = data['documents']
    console.print(f"[green]✓ Loaded {len(documents)} documents[/green]")

    # Check existing documents if incremental
    existing_urls = set()
    if incremental:
        console.print("[cyan]🔍 Checking existing documents...[/cyan]")
        existing_urls = get_existing_doc_ids(conn_string)
        console.print(f"[green]✓ Found {len(existing_urls)} existing documents[/green]")

    # Filter documents
    docs_to_index = []
    for doc in documents:
        url = doc.get('url')
        if incremental and url and url in existing_urls:
            continue
        docs_to_index.append(doc)

    if len(docs_to_index) == 0:
        console.print("[yellow]ℹ No new documents to index[/yellow]")
        return 0, 0, 0.0

    console.print(f"\n[cyan]📝 Indexing {len(docs_to_index)} documents...[/cyan]")

    start_time = time.time()
    total_docs = 0
    total_chunks = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:

        task = progress.add_task("Indexing...", total=len(docs_to_index))

        with psycopg.connect(conn_string) as conn:
            for i in range(0, len(docs_to_index), batch_size):
                batch = docs_to_index[i:i + batch_size]

                # Process batch
                for doc in batch:
                    try:
                        # Insert document
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO news_documents
                                    (title, content, url, source_agency, category, published_at, metadata)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                                """,
                                (
                                    doc['title'],
                                    doc['content'],
                                    doc.get('url'),
                                    doc.get('source_agency'),
                                    doc.get('category'),
                                    doc.get('published_at'),
                                    json.dumps(doc.get('metadata', {}))
                                )
                            )
                            doc_id = cur.fetchone()[0]

                        # Chunk text
                        chunks = chunk_text(doc['content'])

                        # Generate embeddings for all chunks in batch
                        embeddings = embedder.encode(
                            chunks,
                            normalize_embeddings=True,
                            convert_to_numpy=True,
                            show_progress_bar=False,
                            batch_size=batch_size
                        )

                        # Insert chunks with embeddings
                        with conn.cursor() as cur:
                            for chunk_idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                                cur.execute(
                                    """
                                    INSERT INTO document_chunks
                                        (document_id, chunk_index, content, embedding)
                                    VALUES (%s, %s, %s, %s)
                                    """,
                                    (doc_id, chunk_idx, chunk, embedding.tolist())
                                )

                        total_chunks += len(chunks)
                        total_docs += 1

                        conn.commit()

                    except Exception as e:
                        console.print(f"\n[red]✗ Error indexing {doc.get('title', 'unknown')}: {e}[/red]")
                        conn.rollback()
                        continue

                    progress.update(task, advance=1)

    elapsed = time.time() - start_time

    return total_docs, total_chunks, elapsed


def create_ivfflat_index(conn_string: str, lists: int = 100):
    """Create IVFFlat index for vector search."""

    console.print("\n[cyan]🔨 Creating IVFFlat index...[/cyan]")

    start = time.time()

    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            # Drop existing index if any
            cur.execute("DROP INDEX IF EXISTS idx_chunks_embedding")

            # Create IVFFlat index
            cur.execute(
                f"""
                CREATE INDEX idx_chunks_embedding
                ON document_chunks
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = {lists})
                """
            )

            conn.commit()

    elapsed = time.time() - start

    console.print(f"[green]✓ IVFFlat index created ({elapsed:.1f}s)[/green]")


def print_statistics(conn_string: str):
    """Print database statistics."""

    console.print("\n" + "="*64)
    console.print("[bold cyan]Database Statistics[/bold cyan]")
    console.print("="*64)

    with psycopg.connect(conn_string) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Count documents
            cur.execute("SELECT COUNT(*) as count FROM news_documents")
            doc_count = cur.fetchone()['count']

            # Count chunks
            cur.execute("SELECT COUNT(*) as count FROM document_chunks")
            chunk_count = cur.fetchone()['count']

            # Category breakdown
            cur.execute("""
                SELECT category, COUNT(*) as count
                FROM news_documents
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            """)
            categories = cur.fetchall()

            # Date range
            cur.execute("""
                SELECT
                    MIN(published_at) as earliest,
                    MAX(published_at) as latest
                FROM news_documents
                WHERE published_at IS NOT NULL
            """)
            dates = cur.fetchone()

    # Print summary
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="white")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total Documents", f"{doc_count:,}")
    table.add_row("Total Chunks", f"{chunk_count:,}")
    table.add_row("Avg Chunks/Doc", f"{chunk_count/doc_count:.1f}" if doc_count > 0 else "0")

    if dates['earliest'] and dates['latest']:
        table.add_row("Date Range", f"{dates['earliest'].date()} → {dates['latest'].date()}")

    console.print(table)

    # Categories
    if categories:
        console.print("\n[bold cyan]Top Categories:[/bold cyan]")
        cat_table = Table(show_header=True)
        cat_table.add_column("Category", style="yellow")
        cat_table.add_column("Count", justify="right", style="green")

        for cat in categories[:10]:
            cat_table.add_row(cat['category'], f"{cat['count']:,}")

        console.print(cat_table)


def main():
    parser = argparse.ArgumentParser(description='Batch indexing with GPU support')

    # Mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--gpu', action='store_true', help='Use GPU (default)')
    mode_group.add_argument('--cpu', action='store_true', help='Use CPU')

    # Options
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size (default: 32 for GPU, 8 for CPU)')
    parser.add_argument('--corpus', type=str, default='data/corpus_consolidated.json', help='Corpus file')
    parser.add_argument('--clean', action='store_true', help='Clean database before indexing')
    parser.add_argument('--incremental', action='store_true', help='Skip existing documents')
    parser.add_argument('--skip-index', action='store_true', help='Skip IVFFlat index creation')

    args = parser.parse_args()

    # Determine device
    device = 'cpu' if args.cpu else 'cuda'

    # Auto-adjust batch size
    if args.batch_size == 32 and args.cpu:
        args.batch_size = 8
        console.print("[yellow]ℹ Using CPU: reducing batch size to 8[/yellow]")

    # Print header
    console.print("\n╔══════════════════════════════════════════════════════════════╗")
    console.print("║            Batch Indexing Script                            ║")
    console.print("╚══════════════════════════════════════════════════════════════╝\n")

    console.print(f"[cyan]Device:[/cyan]      {device.upper()}")
    console.print(f"[cyan]Batch size:[/cyan]  {args.batch_size}")
    console.print(f"[cyan]Corpus:[/cyan]      {args.corpus}")
    console.print(f"[cyan]Mode:[/cyan]        {'Clean' if args.clean else 'Incremental' if args.incremental else 'Standard'}")

    # Check corpus exists
    corpus_file = Path(args.corpus)
    if not corpus_file.exists():
        console.print(f"\n[red]✗ Corpus file not found: {corpus_file}[/red]")
        console.print("[yellow]Run consolidate_corpus.py first![/yellow]")
        sys.exit(1)

    # Clean database if requested
    if args.clean:
        clean_database(CONN_STRING)

    # Load embedder
    console.print(f"\n[cyan]🤖 Loading BGE-M3 embedder on {device}...[/cyan]")
    start = time.time()

    # Use safetensors to avoid torch.load vulnerability
    import os
    os.environ['SAFETENSORS_FAST_GPU'] = '1'

    embedder = SentenceTransformer('BAAI/bge-m3', device=device, model_kwargs={'use_safetensors': True})
    elapsed = time.time() - start
    console.print(f"[green]✓ Embedder loaded ({elapsed:.1f}s)[/green]")

    # Index documents
    docs_indexed, chunks_created, index_time = index_documents(
        corpus_file=corpus_file,
        embedder=embedder,
        conn_string=CONN_STRING,
        batch_size=args.batch_size,
        incremental=args.incremental
    )

    if docs_indexed == 0:
        console.print("\n[yellow]ℹ No documents indexed[/yellow]")
        sys.exit(0)

    # Create IVFFlat index
    if not args.skip_index:
        # Auto-determine lists parameter (rule of thumb: sqrt(rows) * 4)
        lists = max(10, min(1000, int((chunks_created ** 0.5) * 4)))
        create_ivfflat_index(CONN_STRING, lists=lists)

    # Print statistics
    print_statistics(CONN_STRING)

    # Summary
    console.print("\n" + "="*64)
    console.print("[bold green]✅ Indexing Complete![/bold green]")
    console.print("="*64)

    console.print(f"\n[cyan]Documents indexed:[/cyan]  {docs_indexed:,}")
    console.print(f"[cyan]Chunks created:[/cyan]     {chunks_created:,}")
    console.print(f"[cyan]Time elapsed:[/cyan]       {index_time/60:.1f} minutes")
    console.print(f"[cyan]Throughput:[/cyan]         {docs_indexed/(index_time/60):.1f} docs/min")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Start API:    sudo systemctl start rag-api")
    console.print("  2. Test:         curl http://localhost:8000/health")
    console.print("  3. Benchmark:    python deploy/benchmark_qwen.py")
    console.print("")


if __name__ == "__main__":
    main()
