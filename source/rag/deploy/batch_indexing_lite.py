#!/usr/bin/env python3
"""
Lite Batch Indexing - Uses lighter embedding model

Uses all-MiniLM-L6-v2 (80MB) instead of BGE-M3 (1GB)
- Much lighter on RAM
- Faster inference
- Still good quality (0.85 vs 0.88 on benchmarks)
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

# Lighter model (384 dimensions vs 1024)
MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
EMBEDDING_DIM = 384

CONN_STRING = "host=localhost port=5433 dbname=news_db user=rag_user password=rag_pass"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

def chunk_text(text: str):
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end].strip())
        start = end - CHUNK_OVERLAP
    return chunks

def main():
    console.print("\n[bold cyan]Lite Indexing (all-MiniLM-L6-v2)[/bold cyan]\n")

    # Load corpus
    with open('data/corpus_consolidated.json') as f:
        data = json.load(f)
    docs = data['documents']

    console.print(f"[cyan]Documents: {len(docs)}[/cyan]")

    # Load lite model
    console.print("[cyan]Loading all-MiniLM-L6-v2 (80MB)...[/cyan]")
    embedder = SentenceTransformer(MODEL, device='cpu')
    console.print("[green]✓ Loaded[/green]\n")

    # Clean database
    console.print("[yellow]Cleaning database...[/yellow]")
    with psycopg.connect(CONN_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE document_chunks CASCADE")
            cur.execute("TRUNCATE news_documents CASCADE")
            conn.commit()
    console.print("[green]✓ Cleaned[/green]\n")

    # Index
    total_chunks = 0
    with psycopg.connect(CONN_STRING) as conn:
        with Progress() as progress:
            task = progress.add_task("Indexing...", total=len(docs))

            for doc in docs:
                try:
                    # Insert doc
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO news_documents
                                (title, content, url, source_agency, category, published_at, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (
                                doc['title'], doc['content'], doc.get('url'),
                                doc.get('source_agency'), doc.get('category'),
                                doc.get('published_at'), json.dumps(doc.get('metadata', {}))
                            )
                        )
                        doc_id = cur.fetchone()[0]

                    # Chunk and embed
                    chunks = chunk_text(doc['content'])
                    embeddings = embedder.encode(chunks, show_progress_bar=False, batch_size=1)

                    # Insert chunks
                    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO document_chunks
                                    (document_id, chunk_index, content, embedding)
                                VALUES (%s, %s, %s, %s)
                                """,
                                (doc_id, idx, chunk, emb.tolist())
                            )

                    conn.commit()
                    total_chunks += len(chunks)
                    progress.update(task, advance=1)

                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    conn.rollback()

    console.print(f"\n[green]✓ Indexed {len(docs)} docs, {total_chunks} chunks[/green]")

    # Create index
    console.print("\n[cyan]Creating vector index...[/cyan]")
    with psycopg.connect(CONN_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
            cur.execute(f"""
                CREATE INDEX idx_chunks_embedding
                ON document_chunks
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 50)
            """)
            conn.commit()
    console.print("[green]✓ Index created[/green]")

if __name__ == "__main__":
    main()
