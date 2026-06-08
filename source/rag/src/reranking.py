"""
Re-ranking models for RAG system.

Implements cross-encoder re-ranking to refine retrieval results.

Cross-encoders are more accurate than bi-encoders (like BGE-M3) because:
- Bi-encoder: Encodes query and document separately, then compares
- Cross-encoder: Encodes query+document together, learns interaction

Trade-off: Cross-encoders are ~10-100x slower, so use after initial retrieval.

Supports:
1. Local cross-encoder (sentence-transformers)
2. Cohere Rerank API (enterprise-grade)
"""

from typing import List, Tuple, Optional
from sentence_transformers import CrossEncoder
import numpy as np


class LocalReranker:
    """
    Local cross-encoder re-ranker.

    Uses sentence-transformers cross-encoder models.
    Runs on CPU/GPU locally (no API calls).

    Example:
        reranker = LocalReranker(model_name='cross-encoder/ms-marco-MiniLM-L-12-v2')
        scores = reranker.predict([
            ("query", "document 1"),
            ("query", "document 2")
        ])
    """

    def __init__(
        self,
        model_name: str = 'cross-encoder/ms-marco-MiniLM-L-12-v2',
        device: str = 'cpu',
        max_length: int = 512
    ):
        """
        Initialize local re-ranker.

        Args:
            model_name: HuggingFace cross-encoder model
            device: 'cpu', 'cuda', or 'cuda:0'
            max_length: Maximum sequence length (query + document)

        Popular models:
        - cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, 80M params)
        - cross-encoder/ms-marco-MiniLM-L-12-v2 (balanced, 120M params) ✅
        - cross-encoder/ms-marco-TinyBERT-L-2-v2 (very fast, 15M params)
        """

        self.model_name = model_name
        self.device = device
        self.max_length = max_length

        print(f"Loading cross-encoder: {model_name}...")
        self.model = CrossEncoder(
            model_name,
            max_length=max_length,
            device=device
        )
        print(f"✓ Loaded on {device}")

    def predict(
        self,
        pairs: List[Tuple[str, str]],
        batch_size: int = 16,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Predict relevance scores for query-document pairs.

        Args:
            pairs: List of (query, document) tuples
            batch_size: Batch size for inference
            show_progress: Show progress bar

        Returns:
            Array of scores (higher = more relevant)
        """

        scores = self.model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )

        return scores

    def rank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """
        Rank documents by relevance to query.

        Args:
            query: Search query
            documents: List of documents to rank
            top_k: Return only top K (None = all)

        Returns:
            List of (index, score) tuples, sorted by score descending
        """

        # Create pairs
        pairs = [(query, doc) for doc in documents]

        # Get scores
        scores = self.predict(pairs)

        # Sort by score
        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True
        )

        if top_k:
            ranked = ranked[:top_k]

        return ranked


class CohereReranker:
    """
    Cohere Rerank API re-ranker.

    Uses Cohere's rerank-english-v2.0 or rerank-multilingual-v2.0 models.
    Requires API key and internet connection.

    Pros:
    - Best-in-class accuracy
    - Hosted (no local compute)
    - Multilingual support

    Cons:
    - Requires API key
    - Costs money (but cheap: ~$1/1M requests)
    - Network latency

    Example:
        reranker = CohereReranker(api_key='your-key')
        scores = reranker.predict([
            ("query", "document 1"),
            ("query", "document 2")
        ])
    """

    def __init__(
        self,
        api_key: str,
        model: str = 'rerank-multilingual-v2.0'
    ):
        """
        Initialize Cohere re-ranker.

        Args:
            api_key: Cohere API key
            model: Model name
                - rerank-english-v2.0 (English only, faster)
                - rerank-multilingual-v2.0 (100+ languages, includes Portuguese) ✅

        Get API key: https://dashboard.cohere.com/api-keys
        """

        try:
            import cohere
        except ImportError:
            raise ImportError(
                "cohere not installed. Install with: pip install cohere"
            )

        self.api_key = api_key
        self.model = model
        self.client = cohere.Client(api_key)

        print(f"✓ Cohere Reranker initialized ({model})")

    def predict(
        self,
        pairs: List[Tuple[str, str]],
        **kwargs
    ) -> np.ndarray:
        """
        Predict relevance scores using Cohere API.

        Args:
            pairs: List of (query, document) tuples

        Returns:
            Array of scores
        """

        # Cohere expects single query with multiple documents
        # Assumes all pairs have same query (typical for re-ranking)
        query = pairs[0][0]
        documents = [doc for _, doc in pairs]

        # Call API
        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=documents,
            top_n=len(documents)  # Return all with scores
        )

        # Extract scores in original order
        scores = np.zeros(len(documents))
        for result in response.results:
            scores[result.index] = result.relevance_score

        return scores

    def rank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """
        Rank documents using Cohere API.

        Args:
            query: Search query
            documents: List of documents
            top_k: Return only top K

        Returns:
            List of (index, score) tuples
        """

        # Call API
        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=documents,
            top_n=top_k or len(documents)
        )

        # Convert to (index, score) tuples
        ranked = [(r.index, r.relevance_score) for r in response.results]

        return ranked


def create_reranker(
    provider: str = 'local',
    **kwargs
) -> Optional[LocalReranker | CohereReranker]:
    """
    Factory function to create re-ranker.

    Args:
        provider: 'local' or 'cohere'
        **kwargs: Provider-specific arguments

    Returns:
        Reranker instance or None

    Examples:
        # Local cross-encoder
        reranker = create_reranker('local', device='cpu')

        # Cohere API
        reranker = create_reranker('cohere', api_key='xxx')

        # No re-ranking
        reranker = create_reranker(None)
    """

    if provider is None or provider.lower() == 'none':
        return None

    if provider.lower() == 'local':
        model_name = kwargs.get('model_name', 'cross-encoder/ms-marco-MiniLM-L-12-v2')
        device = kwargs.get('device', 'cpu')
        return LocalReranker(model_name=model_name, device=device)

    elif provider.lower() == 'cohere':
        api_key = kwargs.get('api_key')
        if not api_key:
            raise ValueError("Cohere reranker requires 'api_key' argument")
        model = kwargs.get('model', 'rerank-multilingual-v2.0')
        return CohereReranker(api_key=api_key, model=model)

    else:
        raise ValueError(f"Unknown reranker provider: {provider}")


# Benchmark data (from MS MARCO dataset)
RERANKER_BENCHMARKS = {
    'cross-encoder/ms-marco-TinyBERT-L-2-v2': {
        'params': '15M',
        'speed': 'very fast (~50ms/query)',
        'accuracy': 'MRR@10: 0.30',
        'use_case': 'High-throughput applications'
    },
    'cross-encoder/ms-marco-MiniLM-L-6-v2': {
        'params': '80M',
        'speed': 'fast (~100ms/query)',
        'accuracy': 'MRR@10: 0.35',
        'use_case': 'Balanced speed/accuracy'
    },
    'cross-encoder/ms-marco-MiniLM-L-12-v2': {
        'params': '120M',
        'speed': 'moderate (~200ms/query)',
        'accuracy': 'MRR@10: 0.38',
        'use_case': 'Good accuracy, reasonable speed (RECOMMENDED)'
    },
    'cohere/rerank-multilingual-v2.0': {
        'params': 'proprietary',
        'speed': 'depends on network (~100-300ms)',
        'accuracy': 'MRR@10: 0.42+ (estimated)',
        'use_case': 'Best accuracy, multilingual, hosted'
    }
}
