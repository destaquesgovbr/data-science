"""
Retrieval pipeline for RAG system.

Implements multi-stage retrieval:
1. Vector search (semantic similarity with BGE-M3)
2. Full-text search (PostgreSQL tsvector - Portuguese)
3. RRF fusion (Reciprocal Rank Fusion)
4. Optional re-ranking (cross-encoder)

Based on best practices from:
- Cohere: "Hybrid Search with Reranking"
- Pinecone: "Retrieval Augmented Generation"
- LangChain: Multi-query retrieval
"""

import psycopg
from psycopg.rows import dict_row
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from collections import defaultdict


@dataclass
class RetrievalResult:
    """Single retrieval result with metadata."""

    chunk_id: int
    document_id: int
    content: str
    score: float
    chunk_index: int

    # Document metadata
    doc_title: Optional[str] = None
    doc_url: Optional[str] = None
    doc_category: Optional[str] = None
    doc_agency: Optional[str] = None
    doc_published_at: Optional[str] = None  # Publication date (ISO format)

    # Retrieval metadata
    retrieval_method: Optional[str] = None  # 'vector', 'fulltext', 'hybrid'
    rank: Optional[int] = None

    def __repr__(self):
        return f"RetrievalResult(id={self.chunk_id}, score={self.score:.3f}, method={self.retrieval_method})"


class RetrieverConfig:
    """Configuration for retrieval pipeline."""

    def __init__(
        self,
        vector_top_k: int = 50,
        fulltext_top_k: int = 50,
        rrf_k: int = 60,
        final_top_k: int = 10,
        use_vector: bool = True,
        use_fulltext: bool = True,
        use_reranking: bool = False,
        rerank_top_k: int = 10,
    ):
        self.vector_top_k = vector_top_k
        self.fulltext_top_k = fulltext_top_k
        self.rrf_k = rrf_k
        self.final_top_k = final_top_k
        self.use_vector = use_vector
        self.use_fulltext = use_fulltext
        self.use_reranking = use_reranking
        self.rerank_top_k = rerank_top_k


class Retriever:
    """
    Multi-stage retrieval pipeline.

    Example:
        retriever = Retriever(
            conn_string="host=localhost ...",
            embedder=embedder,
            config=RetrieverConfig(final_top_k=5)
        )

        results = retriever.retrieve("Qual a decisão sobre Selic?")

        for result in results:
            print(f"{result.score:.3f}: {result.content[:100]}...")
    """

    def __init__(
        self,
        conn_string: str,
        embedder,
        config: Optional[RetrieverConfig] = None,
        reranker = None,
    ):
        """
        Initialize retriever.

        Args:
            conn_string: PostgreSQL connection string
            embedder: Embedding model (BGE-M3)
            config: Retrieval configuration
            reranker: Re-ranking model (optional)
        """
        self.conn_string = conn_string
        self.embedder = embedder
        self.config = config or RetrieverConfig()
        self.reranker = reranker

    def retrieve(
        self,
        query: str,
        filters: Optional[Dict] = None,
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks for query.

        Args:
            query: User query
            filters: Optional filters (category, agency, date_range)

        Returns:
            List of RetrievalResult objects, sorted by score (descending)
        """

        # Stage 1: Vector search
        vector_results = []
        if self.config.use_vector:
            vector_results = self._vector_search(query, self.config.vector_top_k, filters)

        # Stage 2: Full-text search
        fulltext_results = []
        if self.config.use_fulltext:
            fulltext_results = self._fulltext_search(query, self.config.fulltext_top_k, filters)

        # Stage 3: Fusion (if both methods used)
        if self.config.use_vector and self.config.use_fulltext:
            fused_results = self._rrf_fusion(
                vector_results,
                fulltext_results,
                k=self.config.rrf_k
            )
        elif self.config.use_vector:
            fused_results = vector_results
        else:
            fused_results = fulltext_results

        # Limit to final_top_k
        fused_results = fused_results[:self.config.final_top_k]

        # Stage 4: Re-ranking (optional)
        if self.config.use_reranking and self.reranker:
            fused_results = self._rerank(query, fused_results, self.config.rerank_top_k)

        return fused_results

    def _vector_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict] = None
    ) -> List[RetrievalResult]:
        """
        Vector similarity search using embeddings.

        Uses cosine similarity (<=> operator in pgvector).
        """

        # Generate query embedding
        query_embedding = self.embedder.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False
        )[0]

        # Build SQL query
        sql = """
            SELECT
                dc.id as chunk_id,
                dc.document_id,
                dc.content,
                dc.chunk_index,
                1 - (dc.embedding <=> %s::vector) as score,
                nd.title as doc_title,
                nd.url as doc_url,
                nd.category as doc_category,
                nd.source_agency as doc_agency,
                nd.published_at as doc_published_at
            FROM document_chunks dc
            JOIN news_documents nd ON dc.document_id = nd.id
        """

        # Add filters
        where_clauses = []
        # Convert embedding to list once
        embedding_list = query_embedding.tolist()
        params = [embedding_list]

        if filters:
            if 'category' in filters:
                where_clauses.append("nd.category = %s")
                params.append(filters['category'])

            if 'agency' in filters:
                where_clauses.append("nd.source_agency = %s")
                params.append(filters['agency'])

            if 'date_from' in filters:
                where_clauses.append("nd.published_at >= %s")
                params.append(filters['date_from'])

            if 'date_to' in filters:
                where_clauses.append("nd.published_at <= %s")
                params.append(filters['date_to'])

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += """
            ORDER BY score DESC
            LIMIT %s
        """

        params.append(top_k)

        # Execute query
        with psycopg.connect(self.conn_string) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        # Convert to RetrievalResult objects
        results = []
        for rank, row in enumerate(rows, 1):
            # Format published_at to ISO string if available
            published_at = None
            if row.get('doc_published_at'):
                published_at = row['doc_published_at'].isoformat() if hasattr(row['doc_published_at'], 'isoformat') else str(row['doc_published_at'])

            results.append(RetrievalResult(
                chunk_id=row['chunk_id'],
                document_id=row['document_id'],
                content=row['content'],
                score=float(row['score']),
                chunk_index=row['chunk_index'],
                doc_title=row['doc_title'],
                doc_url=row['doc_url'],
                doc_category=row['doc_category'],
                doc_agency=row['doc_agency'],
                doc_published_at=published_at,
                retrieval_method='vector',
                rank=rank
            ))

        return results

    def _fulltext_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict] = None
    ) -> List[RetrievalResult]:
        """
        Full-text search using PostgreSQL tsvector.

        Uses Portuguese language configuration for stemming/stopwords.
        """

        # Build SQL query with ts_rank for scoring
        sql = """
            SELECT
                dc.id as chunk_id,
                dc.document_id,
                dc.content,
                dc.chunk_index,
                ts_rank(
                    to_tsvector('portuguese', dc.content),
                    plainto_tsquery('portuguese', %s)
                ) as score,
                nd.title as doc_title,
                nd.url as doc_url,
                nd.category as doc_category,
                nd.source_agency as doc_agency,
                nd.published_at as doc_published_at
            FROM document_chunks dc
            JOIN news_documents nd ON dc.document_id = nd.id
            WHERE to_tsvector('portuguese', dc.content) @@ plainto_tsquery('portuguese', %s)
        """

        # Add filters
        params = [query, query]

        if filters:
            if 'category' in filters:
                sql += " AND nd.category = %s"
                params.append(filters['category'])

            if 'agency' in filters:
                sql += " AND nd.source_agency = %s"
                params.append(filters['agency'])

            if 'date_from' in filters:
                sql += " AND nd.published_at >= %s"
                params.append(filters['date_from'])

            if 'date_to' in filters:
                sql += " AND nd.published_at <= %s"
                params.append(filters['date_to'])

        sql += """
            ORDER BY score DESC
            LIMIT %s
        """
        params.append(top_k)

        # Execute query
        with psycopg.connect(self.conn_string) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        # Convert to RetrievalResult objects
        results = []
        for rank, row in enumerate(rows, 1):
            # Format published_at to ISO string if available
            published_at = None
            if row.get('doc_published_at'):
                published_at = row['doc_published_at'].isoformat() if hasattr(row['doc_published_at'], 'isoformat') else str(row['doc_published_at'])

            results.append(RetrievalResult(
                chunk_id=row['chunk_id'],
                document_id=row['document_id'],
                content=row['content'],
                score=float(row['score']),
                chunk_index=row['chunk_index'],
                doc_title=row['doc_title'],
                doc_url=row['doc_url'],
                doc_category=row['doc_category'],
                doc_agency=row['doc_agency'],
                doc_published_at=published_at,
                retrieval_method='fulltext',
                rank=rank
            ))

        return results

    def _rrf_fusion(
        self,
        vector_results: List[RetrievalResult],
        fulltext_results: List[RetrievalResult],
        k: int = 60
    ) -> List[RetrievalResult]:
        """
        Reciprocal Rank Fusion (RRF).

        Formula: RRF(d) = Σ 1 / (k + rank(d))

        where:
        - d is a document (chunk)
        - rank(d) is the rank in a specific ranking
        - k is a constant (typically 60)

        Reference:
        "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning"
        (Cormack et al., 2009)

        Args:
            vector_results: Results from vector search
            fulltext_results: Results from full-text search
            k: RRF constant (default: 60)

        Returns:
            Fused results sorted by RRF score
        """

        # Calculate RRF scores
        rrf_scores = defaultdict(float)
        chunk_map = {}  # chunk_id -> RetrievalResult

        # Add vector results
        for rank, result in enumerate(vector_results, 1):
            rrf_scores[result.chunk_id] += 1.0 / (k + rank)
            chunk_map[result.chunk_id] = result

        # Add fulltext results
        for rank, result in enumerate(fulltext_results, 1):
            rrf_scores[result.chunk_id] += 1.0 / (k + rank)
            if result.chunk_id not in chunk_map:
                chunk_map[result.chunk_id] = result

        # Sort by RRF score
        sorted_chunks = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Build fused results
        fused_results = []
        for rank, (chunk_id, rrf_score) in enumerate(sorted_chunks, 1):
            result = chunk_map[chunk_id]
            # Update with RRF score
            result.score = rrf_score
            result.retrieval_method = 'hybrid'
            result.rank = rank
            fused_results.append(result)

        return fused_results

    def _rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Re-rank results using cross-encoder.

        Cross-encoders are more accurate than bi-encoders but slower.
        Use after initial retrieval to refine top results.

        Args:
            query: Original query
            results: Initial retrieval results
            top_k: How many to return after re-ranking

        Returns:
            Re-ranked results
        """

        if not self.reranker:
            return results[:top_k]

        # Prepare pairs (query, chunk)
        pairs = [(query, result.content) for result in results]

        # Get reranker scores
        scores = self.reranker.predict(pairs)

        # Update scores and sort
        for result, score in zip(results, scores):
            result.score = float(score)
            result.retrieval_method = 'reranked'

        results.sort(key=lambda x: x.score, reverse=True)

        # Update ranks
        for rank, result in enumerate(results[:top_k], 1):
            result.rank = rank

        return results[:top_k]

    def get_context_window(
        self,
        results: List[RetrievalResult],
        max_tokens: int = 8000,
        chars_per_token: float = 4.0
    ) -> str:
        """
        Build context window from retrieval results.

        Concatenates chunks with metadata, respecting token limit.

        Args:
            results: Retrieval results
            max_tokens: Maximum tokens for context
            chars_per_token: Approximation (4 chars ≈ 1 token for Portuguese)

        Returns:
            Formatted context string
        """

        max_chars = int(max_tokens * chars_per_token)

        context_parts = []
        current_length = 0

        for i, result in enumerate(results, 1):
            # Format chunk with metadata
            chunk_text = f"""
[Chunk {i}]
Fonte: {result.doc_title}
Categoria: {result.doc_category}
Órgão: {result.doc_agency}

{result.content}

---
"""

            chunk_length = len(chunk_text)

            if current_length + chunk_length > max_chars:
                break

            context_parts.append(chunk_text)
            current_length += chunk_length

        return "\n".join(context_parts)
