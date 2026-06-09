"""
Indexing pipeline for RAG system.

Handles:
- Document ingestion
- Chunking
- Embedding generation
- PostgreSQL + pgvector insertion
- Contextual enrichment (Anthropic pattern)
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Iterator
from dataclasses import dataclass
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import numpy as np
from tqdm import tqdm
import time
from datetime import datetime

from .chunking import Chunk, create_chunker


@dataclass
class Document:
    """Represents a news document."""

    title: str
    content: str
    url: Optional[str] = None
    source_agency: Optional[str] = None
    category: Optional[str] = None
    published_at: Optional[datetime] = None
    metadata: Optional[Dict] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IndexingPipeline:
    """
    Complete indexing pipeline for RAG system.

    Workflow:
    1. Load documents
    2. Chunk each document
    3. (Optional) Enrich chunks with context
    4. Generate embeddings
    5. Insert into PostgreSQL + pgvector

    Example:
        pipeline = IndexingPipeline(
            conn_string="host=localhost dbname=news_db ...",
            embedder=embedder,
            chunker_strategy='semantic'
        )

        documents = load_documents()
        pipeline.index_documents(documents)
    """

    def __init__(
        self,
        conn_string: str,
        embedder,
        chunker_strategy: str = 'semantic',
        chunker_kwargs: Optional[Dict] = None,
        enable_enrichment: bool = False,
        enrichment_llm=None,
        batch_size: int = 32,
    ):
        """
        Initialize indexing pipeline.

        Args:
            conn_string: PostgreSQL connection string
            embedder: Embedding model (e.g., BGE-M3)
            chunker_strategy: 'fixed', 'semantic', 'paragraph', 'recursive'
            chunker_kwargs: Arguments for chunker
            enable_enrichment: Enable contextual enrichment (Anthropic pattern)
            enrichment_llm: LLM for enrichment (if enabled)
            batch_size: Batch size for embeddings
        """

        self.conn_string = conn_string
        self.embedder = embedder
        self.batch_size = batch_size

        # Create chunker
        chunker_kwargs = chunker_kwargs or {}
        if chunker_strategy == 'semantic' and 'embedder' not in chunker_kwargs:
            chunker_kwargs['embedder'] = embedder

        self.chunker = create_chunker(chunker_strategy, **chunker_kwargs)

        # Enrichment
        self.enable_enrichment = enable_enrichment
        self.enrichment_llm = enrichment_llm

        if enable_enrichment and enrichment_llm is None:
            print("Warning: Enrichment enabled but no LLM provided. Skipping enrichment.")
            self.enable_enrichment = False

    def index_documents(
        self,
        documents: List[Document],
        skip_existing: bool = True,
        show_progress: bool = True
    ) -> Dict[str, int]:
        """
        Index multiple documents.

        Args:
            documents: List of Document objects
            skip_existing: Skip documents that already exist (by URL)
            show_progress: Show progress bar

        Returns:
            Statistics dict
        """

        stats = {
            'total': len(documents),
            'indexed': 0,
            'skipped': 0,
            'failed': 0,
            'chunks_created': 0,
        }

        iterator = tqdm(documents, desc="Indexing documents") if show_progress else documents

        for doc in iterator:
            try:
                result = self.index_document(doc, skip_existing=skip_existing)

                if result['status'] == 'indexed':
                    stats['indexed'] += 1
                    stats['chunks_created'] += result['chunks_created']
                elif result['status'] == 'skipped':
                    stats['skipped'] += 1
                else:
                    stats['failed'] += 1

            except Exception as e:
                print(f"\nError indexing document '{doc.title}': {e}")
                stats['failed'] += 1
                continue

        return stats

    def index_document(
        self,
        document: Document,
        skip_existing: bool = True
    ) -> Dict:
        """
        Index a single document.

        Uses transaction to ensure atomicity:
        - Insert document
        - Chunk document
        - Enrich chunks (optional)
        - Generate embeddings
        - Insert chunks

        If any step fails, rollback everything.
        """

        with psycopg.connect(self.conn_string) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("BEGIN;")

                    # Check if document exists
                    if skip_existing and document.url:
                        cur.execute(
                            "SELECT id FROM news_documents WHERE url = %s;",
                            (document.url,)
                        )

                        existing = cur.fetchone()
                        if existing:
                            cur.execute("ROLLBACK;")
                            return {'status': 'skipped', 'reason': 'already_exists'}

                    # Insert document
                    cur.execute("""
                        INSERT INTO news_documents
                        (title, content, url, source_agency, category, published_at, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO UPDATE
                        SET content = EXCLUDED.content,
                            title = EXCLUDED.title,
                            updated_at = NOW()
                        RETURNING id;
                    """, (
                        document.title,
                        document.content,
                        document.url,
                        document.source_agency,
                        document.category,
                        document.published_at,
                        psycopg.types.json.Jsonb(document.metadata or {})
                    ))

                    doc_id = cur.fetchone()[0]

                    # Chunk document
                    chunks = self.chunker.chunk(document.content)

                    if len(chunks) == 0:
                        print(f"Warning: No chunks created for document '{document.title}'")
                        cur.execute("ROLLBACK;")
                        return {'status': 'failed', 'reason': 'no_chunks'}

                    # Enrich chunks (optional)
                    if self.enable_enrichment:
                        chunks = self._enrich_chunks(chunks, document)

                    # Generate embeddings in batches
                    all_embeddings = []

                    for i in range(0, len(chunks), self.batch_size):
                        batch = chunks[i:i+self.batch_size]
                        texts = [c.content for c in batch]

                        embeddings = self.embedder.encode(
                            texts,
                            batch_size=len(texts),
                            normalize_embeddings=True,
                            convert_to_numpy=True,
                            show_progress_bar=False
                        )

                        all_embeddings.extend(embeddings)

                    # Insert chunks
                    chunk_data = []
                    for chunk, embedding in zip(chunks, all_embeddings):
                        # Get enriched content if available
                        enriched_content = chunk.metadata.get('enriched_content') if chunk.metadata else None

                        chunk_data.append((
                            doc_id,
                            chunk.chunk_index,
                            chunk.content,
                            enriched_content,
                            embedding.tolist(),  # pgvector accepts Python lists
                            chunk.chunk_type,
                            chunk.char_start,
                            chunk.char_end,
                            None,  # tokens (optional)
                        ))

                    # Bulk insert chunks
                    with cur.copy("""
                        COPY document_chunks
                        (document_id, chunk_index, content, enriched_content,
                         embedding, chunk_type, char_start, char_end, tokens)
                        FROM STDIN WITH (FORMAT BINARY)
                    """) as copy:
                        # Note: COPY requires proper formatting
                        # For simplicity, using execute_batch instead
                        pass

                    # Fallback: executemany (works reliably with psycopg3)
                    cur.executemany("""
                        INSERT INTO document_chunks
                        (document_id, chunk_index, content, enriched_content,
                         embedding, chunk_type, char_start, char_end, tokens)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, chunk_data)

                    cur.execute("COMMIT;")

                    return {
                        'status': 'indexed',
                        'document_id': doc_id,
                        'chunks_created': len(chunks)
                    }

                except Exception as e:
                    cur.execute("ROLLBACK;")
                    raise e

    def _enrich_chunks(
        self,
        chunks: List[Chunk],
        document: Document
    ) -> List[Chunk]:
        """
        Enrich chunks with contextual information.

        Anthropic Contextual Retrieval pattern:
        Add document-level context to each chunk to improve retrieval.

        Example:
            Original chunk: "A taxa subiu 0.5 pontos"

            Enriched: "Contexto: Decisão do Banco Central sobre taxa Selic em março 2024.
                       A taxa subiu 0.5 pontos"

        This context helps retrieval match queries like "decisão banco central selic"
        even if those words don't appear in the original chunk.
        """

        if not self.enable_enrichment or not self.enrichment_llm:
            return chunks

        # Build context from document
        doc_context = {
            'title': document.title,
            'category': document.category or 'Não especificado',
            'agency': document.source_agency or 'Não especificado',
            'date': document.published_at.strftime('%d/%m/%Y') if document.published_at else 'Não especificado'
        }

        # Enrich each chunk
        enriched_chunks = []

        for chunk in chunks:
            try:
                # Call LLM to generate contextual summary
                # (Simplified - in production, use async batching)
                enriched_content = self._generate_enrichment(chunk.content, doc_context)

                # Add to metadata
                if chunk.metadata is None:
                    chunk.metadata = {}
                chunk.metadata['enriched_content'] = enriched_content

                enriched_chunks.append(chunk)

            except Exception as e:
                print(f"Warning: Failed to enrich chunk {chunk.chunk_index}: {e}")
                enriched_chunks.append(chunk)  # Keep original

        return enriched_chunks

    def _generate_enrichment(self, chunk_text: str, doc_context: Dict) -> str:
        """
        Generate enrichment text for a chunk.

        Calls LLM with prompt to generate 1-2 sentence context.
        """

        prompt = f"""Você receberá um trecho de uma notícia governamental.
Gere uma breve contextualização (1-2 sentenças) que situe esse trecho no documento maior.

Documento:
- Título: {doc_context['title']}
- Categoria: {doc_context['category']}
- Órgão: {doc_context['agency']}
- Data: {doc_context['date']}

Trecho:
{chunk_text[:500]}

Contextualização (seja factual e conciso):"""

        # Call LLM (placeholder - implement based on your LLM client)
        try:
            enrichment = self.enrichment_llm.generate(prompt, max_tokens=100)
            return enrichment.strip()
        except Exception as e:
            print(f"LLM enrichment failed: {e}")
            return ""

    def get_index_stats(self) -> Dict:
        """Get indexing statistics from database."""

        with psycopg.connect(self.conn_string) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Total documents
                cur.execute("SELECT COUNT(*) as count FROM news_documents;")
                total_docs = cur.fetchone()['count']

                # Total chunks
                cur.execute("SELECT COUNT(*) as count FROM document_chunks;")
                total_chunks = cur.fetchone()['count']

                # Chunks per document (avg)
                cur.execute("""
                    SELECT AVG(chunk_count) as avg_chunks
                    FROM (
                        SELECT document_id, COUNT(*) as chunk_count
                        FROM document_chunks
                        GROUP BY document_id
                    ) as counts;
                """)
                avg_chunks = cur.fetchone()['avg_chunks']

                # Documents by category
                cur.execute("""
                    SELECT category, COUNT(*) as count
                    FROM news_documents
                    WHERE category IS NOT NULL
                    GROUP BY category
                    ORDER BY count DESC;
                """)
                by_category = cur.fetchall()

                # Latest indexed
                cur.execute("""
                    SELECT created_at
                    FROM news_documents
                    ORDER BY created_at DESC
                    LIMIT 1;
                """)
                latest = cur.fetchone()

                return {
                    'total_documents': total_docs,
                    'total_chunks': total_chunks,
                    'avg_chunks_per_doc': float(avg_chunks) if avg_chunks else 0,
                    'documents_by_category': by_category,
                    'latest_indexed': latest['created_at'] if latest else None
                }

    def delete_document(self, doc_id: int) -> bool:
        """
        Delete document and all its chunks.

        Uses CASCADE, so chunks are automatically deleted.
        """

        with psycopg.connect(self.conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM news_documents WHERE id = %s RETURNING id;",
                    (doc_id,)
                )
                deleted = cur.fetchone()
                conn.commit()

                return deleted is not None

    def reindex_document(self, doc_id: int) -> Dict:
        """
        Reindex existing document.

        Useful if chunking strategy or embeddings changed.
        """

        with psycopg.connect(self.conn_string) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Fetch document
                cur.execute("""
                    SELECT title, content, url, source_agency, category, published_at, metadata
                    FROM news_documents
                    WHERE id = %s;
                """, (doc_id,))

                row = cur.fetchone()

                if not row:
                    raise ValueError(f"Document {doc_id} not found")

                # Reconstruct Document object
                document = Document(
                    title=row['title'],
                    content=row['content'],
                    url=row['url'],
                    source_agency=row['source_agency'],
                    category=row['category'],
                    published_at=row['published_at'],
                    metadata=row['metadata']
                )

                # Delete old chunks
                cur.execute("DELETE FROM document_chunks WHERE document_id = %s;", (doc_id,))
                conn.commit()

        # Reindex (will skip document insert due to existing URL)
        return self.index_document(document, skip_existing=False)


def load_documents_from_json(file_path: str) -> List[Document]:
    """
    Load documents from JSON file.

    Expected format:
    [
        {
            "title": "...",
            "content": "...",
            "url": "...",
            "source_agency": "...",
            "category": "...",
            "published_at": "2024-01-15T10:30:00",
            "metadata": {}
        },
        ...
    ]
    """

    import json
    from datetime import datetime

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = []

    for item in data:
        # Parse date
        published_at = None
        if item.get('published_at'):
            try:
                published_at = datetime.fromisoformat(item['published_at'].replace('Z', '+00:00'))
            except:
                pass

        documents.append(Document(
            title=item['title'],
            content=item['content'],
            url=item.get('url'),
            source_agency=item.get('source_agency'),
            category=item.get('category'),
            published_at=published_at,
            metadata=item.get('metadata', {})
        ))

    return documents


def load_documents_from_csv(file_path: str) -> List[Document]:
    """
    Load documents from CSV file.

    Expected columns: title, content, url, source_agency, category, published_at
    """

    import pandas as pd
    from datetime import datetime

    df = pd.read_csv(file_path)

    documents = []

    for _, row in df.iterrows():
        # Parse date
        published_at = None
        if pd.notna(row.get('published_at')):
            try:
                published_at = pd.to_datetime(row['published_at']).to_pydatetime()
            except:
                pass

        documents.append(Document(
            title=row['title'],
            content=row['content'],
            url=row.get('url') if pd.notna(row.get('url')) else None,
            source_agency=row.get('source_agency') if pd.notna(row.get('source_agency')) else None,
            category=row.get('category') if pd.notna(row.get('category')) else None,
            published_at=published_at,
            metadata={}
        ))

    return documents
