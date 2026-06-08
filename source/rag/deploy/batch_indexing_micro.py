#!/usr/bin/env python3
"""
Micro-batch indexing - Ultra-safe mode

Indexes ONE document at a time with checkpoints.
Prevents system crashes by minimizing memory usage.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg
from sentence_transformers import SentenceTransformer
from rich.console import Console
from rich.progress import Progress

console = Console()

CONN_STRING = "host=localhost port=5432 dbname=news_db user=rag_user password=rag_pass"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

def chunk_text(text: str) -> list:
    """Split text into chunks."""
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end].strip())
        start = end - CHUNK_OVERLAP
    return chunks

def get_indexed_urls():
    """Get URLs of already indexed documents."""
    with psycopg.connect(CONN_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT url FROM news_documents WHERE url IS NOT NULL")
            return {row[0] for row in cur.fetchall()}

def index_document(doc, embedder, conn):
    """Index a single document."""
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

        # Generate embeddings ONE at a time
        for chunk_idx, chunk in enumerate(chunks):
            embedding = embedder.encode(
                [chunk],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False
            )[0]

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_chunks
                        (document_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (doc_id, chunk_idx, chunk, embedding.tolist())
                )

        conn.commit()
        return len(chunks)

    except Exception as e:
        conn.rollback()
        console.print(f"[red]✗ Error: {e}[/red]")
        return 0

def main():
    console.print("\n[bold cyan]Micro-Batch Indexing (Ultra-Safe Mode)[/bold cyan]\n")

    # Load corpus
    corpus_file = Path("data/corpus_consolidated.json")
    with open(corpus_file) as f:
        data = json.load(f)
    documents = data['documents']

    console.print(f"[cyan]📂 Total documents: {len(documents)}[/cyan]")

    # Check existing
    indexed_urls = get_indexed_urls()
    console.print(f"[cyan]✓ Already indexed: {len(indexed_urls)}[/cyan]")

    to_index = [d for d in documents if d.get('url') not in indexed_urls]
    console.print(f"[cyan]📝 To index: {len(to_index)}[/cyan]\n")

    if not to_index:
        console.print("[green]✓ All documents already indexed![/green]")
        return

    # Load embedder
    console.print("[cyan]Loading BGE-M3...[/cyan]")
    embedder = SentenceTransformer('BAAI/bge-m3', device='cuda')
    console.print("[green]✓ Loaded[/green]\n")

    # Index one by one
    total_chunks = 0
    with psycopg.connect(CONN_STRING) as conn:
        with Progress() as progress:
            task = progress.add_task("Indexing...", total=len(to_index))

            for i, doc in enumerate(to_index, 1):
                chunks = index_document(doc, embedder, conn)
                total_chunks += chunks
                progress.update(task, advance=1)

                # Progress checkpoint every 10 docs
                if i % 10 == 0:
                    console.print(f"[dim]Checkpoint: {i}/{len(to_index)} docs, {total_chunks} chunks[/dim]")

    console.print(f"\n[green]✓ Indexed {len(to_index)} documents, {total_chunks} chunks[/green]")

if __name__ == "__main__":
    main()
