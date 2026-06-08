#!/usr/bin/env python3
"""
RAG API Server - FastAPI REST endpoint for question answering.

Provides /query endpoint for real-time Q&A over government news corpus.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from sentence_transformers import SentenceTransformer
import time

from src.retrieval import Retriever, RetrieverConfig
from src.generation import Generator, PromptLibrary
from src.llm_providers import create_llm_provider
from src.reranking import create_reranker

# ============================================================================
# Configuration
# ============================================================================

# Database connection
CONN_STRING = "host=localhost port=5433 dbname=news_db user=rag_user"

# Default LLM provider (can be overridden per request)
DEFAULT_PROVIDER = "bedrock"
DEFAULT_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"  # Fast and cheap

# ============================================================================
# Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for /query endpoint."""

    query: str = Field(..., description="User question", min_length=3, max_length=500)

    # Retrieval config
    top_k: int = Field(5, description="Number of chunks to retrieve", ge=1, le=20)
    use_reranking: bool = Field(True, description="Enable re-ranking")

    # LLM config
    provider: str = Field(DEFAULT_PROVIDER, description="LLM provider: bedrock or ollama")
    model: Optional[str] = Field(None, description="Model ID/name (defaults to provider's default)")
    max_tokens: int = Field(2000, description="Max tokens for LLM response", ge=100, le=4000)
    temperature: float = Field(0.0, description="LLM temperature", ge=0.0, le=2.0)

    # Prompt template
    prompt_template: str = Field("default", description="Prompt template: default, factual, summary")

    # Source filtering
    min_source_score: float = Field(0.0, description="Minimum score for sources (0.0 = filter negatives)", ge=-1.0, le=1.0)

    # Filters (optional)
    category: Optional[str] = Field(None, description="Filter by category")
    agency: Optional[str] = Field(None, description="Filter by agency")
    date_from: Optional[str] = Field(None, description="Filter by date from (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Filter by date to (YYYY-MM-DD)")


class Source(BaseModel):
    """Source document metadata."""
    index: int
    title: str
    url: str
    category: str
    agency: str
    published_at: Optional[str] = None  # Publication date (DD/MM/YYYY)
    chunk_text: str
    score: float


class QueryResponse(BaseModel):
    """Response model for /query endpoint."""

    # Main output
    answer: str = Field(..., description="Generated answer with citations")
    sources: List[Source] = Field(..., description="Source documents used")

    # Metadata
    query: str

    # Metrics
    latency_ms: Dict[str, float] = Field(..., description="Latency breakdown")
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_usd: Optional[float] = None

    # Model info
    llm_model: str
    llm_provider: str
    retrieval_config: Dict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    embedder: str
    database: str
    llm_providers: List[str]


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="RAG Q&A API",
    description="Question answering system for Brazilian government news using RAG",
    version="1.0.0"
)

# CORS (allow frontend to call API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Global state (lazy initialization)
# ============================================================================

_embedder = None
_retriever = None
_reranker = None
_llm_cache = {}  # Cache LLM providers by (provider, model) key


def get_embedder():
    """Lazy load embedder (heavy operation)."""
    global _embedder
    if _embedder is None:
        print("Loading BGE-M3 embedder...")
        _embedder = SentenceTransformer('BAAI/bge-m3', device='cpu')
        print("✓ Embedder loaded")
    return _embedder


def get_retriever():
    """Lazy load retriever."""
    global _retriever
    if _retriever is None:
        print("Initializing retriever...")
        embedder = get_embedder()

        # Note: config will be overridden per request
        # This is just for initialization
        config = RetrieverConfig(
            final_top_k=5,
            use_reranking=True,
            rerank_top_k=5
        )

        _retriever = Retriever(CONN_STRING, embedder, config, None)
        print("✓ Retriever initialized")

    return _retriever


def get_reranker():
    """Lazy load reranker."""
    global _reranker
    if _reranker is None:
        print("Loading reranker...")
        _reranker = create_reranker('local', device='cpu')
        print("✓ Reranker loaded")
    return _reranker


def get_llm_provider(provider: str, model: Optional[str] = None):
    """Get or create LLM provider (with caching)."""
    global _llm_cache

    # Determine model
    if model is None:
        if provider == "bedrock":
            model = DEFAULT_MODEL
        elif provider == "ollama":
            model = "qwen2.5:7b"
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # Check cache
    cache_key = (provider, model)
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    # Create provider
    print(f"Initializing LLM provider: {provider} ({model})...")

    if provider == "bedrock":
        llm = create_llm_provider('bedrock', model_id=model)
    elif provider == "ollama":
        llm = create_llm_provider('ollama', model=model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Cache
    _llm_cache[cache_key] = llm
    print(f"✓ LLM provider initialized and cached")

    return llm


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", response_model=Dict)
async def root():
    """Root endpoint with API info."""
    return {
        "name": "RAG Q&A API",
        "version": "1.0.0",
        "endpoints": {
            "query": "/query (POST)",
            "health": "/health (GET)",
            "docs": "/docs (GET)"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""

    # Check components
    try:
        embedder = get_embedder()
        embedder_status = "ok"
    except Exception as e:
        embedder_status = f"error: {e}"

    try:
        retriever = get_retriever()
        # Quick test query
        retriever.retrieve("teste", filters=None)
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return HealthResponse(
        status="ok" if embedder_status == "ok" and db_status == "ok" else "degraded",
        embedder=embedder_status,
        database=db_status,
        llm_providers=["bedrock", "ollama"]
    )


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Main Q&A endpoint.

    Example:
        POST /query
        {
            "query": "Qual foi o valor do Plano Safra?",
            "top_k": 5,
            "use_reranking": true,
            "provider": "bedrock",
            "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        }
    """

    start_time = time.time()

    try:
        # Get components
        retriever = get_retriever()

        # Override retriever config for this request
        reranker = get_reranker() if request.use_reranking else None

        retriever.config = RetrieverConfig(
            final_top_k=request.top_k,
            use_vector=True,
            use_fulltext=False,  # Disable RRF fusion to preserve vector scores
            use_reranking=request.use_reranking,
            rerank_top_k=request.top_k
        )
        retriever.reranker = reranker

        # Get LLM provider
        llm = get_llm_provider(request.provider, request.model)

        # Get prompt template
        prompt_template = PromptLibrary.get(request.prompt_template)

        # Create generator
        generator = Generator(
            retriever,
            llm,
            prompt_template=prompt_template,
            min_source_score=request.min_source_score
        )

        # Build filters
        filters = {}
        if request.category:
            filters['category'] = request.category
        if request.agency:
            filters['agency'] = request.agency
        if request.date_from:
            filters['date_from'] = request.date_from
        if request.date_to:
            filters['date_to'] = request.date_to

        # Generate answer
        rag_response = generator.generate(
            query=request.query,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            filters=filters if filters else None
        )

        # Convert to API response
        response = QueryResponse(
            answer=rag_response.answer,
            sources=[
                Source(
                    index=src['index'],
                    title=src['title'],
                    url=src['url'],
                    category=src['category'],
                    agency=src['agency'],
                    published_at=src.get('published_at'),
                    chunk_text=src['chunk_text'],
                    score=src['score']
                )
                for src in rag_response.sources
            ],
            query=rag_response.query,
            latency_ms=rag_response.latency_breakdown,
            tokens_input=rag_response.tokens_input,
            tokens_output=rag_response.tokens_output,
            cost_usd=rag_response.cost_usd,
            llm_model=rag_response.llm_model,
            llm_provider=rag_response.llm_provider,
            retrieval_config=rag_response.retrieval_config
        )

        total_time = (time.time() - start_time) * 1000
        print(f"✓ Query processed in {total_time:.0f}ms")

        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Run server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    RAG Q&A API Server                        ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Endpoints:                                                  ║
    ║    GET  /           - API info                               ║
    ║    GET  /health     - Health check                           ║
    ║    POST /query      - Q&A endpoint                           ║
    ║    GET  /docs       - Interactive API docs (Swagger UI)      ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
