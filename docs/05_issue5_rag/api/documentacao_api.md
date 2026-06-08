# RAG API - REST Interface

FastAPI REST server for RAG question answering system.

## Quick Start

### 1. Start the API Server

```bash
cd /l/disk0/lpmoraes/environments/data-science/source/rag
python api/server.py
```

Server will start on `http://localhost:8000`

### 2. Use Interactive Client

In another terminal:

```bash
cd /l/disk0/lpmoraes/environments/data-science/source/rag
python api/client.py
```

Then just type your questions!

## API Endpoints

### GET /
Basic API info

### GET /health
Health check - verifies embedder and database connectivity

### POST /query
Main Q&A endpoint

**Request:**
```json
{
  "query": "Qual foi o valor do Plano Safra?",
  "top_k": 5,
  "use_reranking": true,
  "provider": "bedrock",
  "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "max_tokens": 2000,
  "temperature": 0.0,
  "prompt_template": "default"
}
```

**Response:**
```json
{
  "answer": "O Plano Safra 2025/2026 conta com R$ 113,4 bilhões...",
  "sources": [
    {
      "index": 1,
      "title": "Plano Safra 2025/2026...",
      "url": "https://...",
      "category": "Agricultura",
      "agency": "secom",
      "chunk_text": "...",
      "score": 3.664
    }
  ],
  "query": "Qual foi o valor do Plano Safra?",
  "latency_ms": {
    "retrieval_ms": 1200,
    "generation_ms": 5500,
    "total_ms": 6700
  },
  "tokens_input": 749,
  "tokens_output": 213,
  "cost_usd": 0.0054,
  "llm_model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "llm_provider": "bedrock",
  "retrieval_config": {...}
}
```

### GET /docs
Interactive API documentation (Swagger UI)

## Using curl

```bash
# Health check
curl http://localhost:8000/health

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual foi o valor do Plano Safra?",
    "top_k": 5,
    "use_reranking": true
  }'
```

## Configuration Options

### Providers
- `bedrock` - AWS Bedrock (Claude, etc.)
- `ollama` - Local models

### Bedrock Models
- `us.anthropic.claude-sonnet-4-6` - Best quality
- `us.anthropic.claude-haiku-4-5-20251001-v1:0` - Fast (default)
- `us.anthropic.claude-sonnet-4-5-20250929-v1:0` - Balanced

### Ollama Models
- `qwen2.5:7b` - Good multilingual (default)
- `llama3.1:8b` - Fast, good quality
- `mistral:7b` - Fast

### Prompt Templates
- `default` - Balanced instructions
- `factual` - Focus on facts only
- `summary` - Create summaries
- `comparison` - Compare policies

## Interactive Client Commands

- `/help` - Show help
- `/config` - Change settings (model, top-k, etc.)
- `/show` - Show current config
- `/exit` - Quit

Just type questions normally to query the system.

## Architecture

```
Client (client.py)
    ↓ HTTP POST
API Server (server.py)
    ↓
Generator (generation.py)
    ↓
Retriever (retrieval.py) → PostgreSQL/pgvector
    ↓
LLM Provider (llm_providers.py) → Bedrock/Ollama
    ↓
Response with answer + sources + metrics
```

## Performance

Typical latency (Bedrock Haiku 4.5):
- Retrieval: 0.3-1.5s
- Generation: 2-6s
- **Total: 3-7s**

Cost (Bedrock Haiku 4.5):
- ~$0.007/query

## Development

Run with auto-reload:
```bash
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

## Dependencies

Required packages (already in environment):
- fastapi
- uvicorn
- pydantic
- requests
- rich
- sentence-transformers
- psycopg (for PostgreSQL)
- boto3 (for Bedrock)

## Troubleshooting

**"Cannot connect to API"**
- Make sure server is running: `python api/server.py`

**"Cannot connect to Ollama"**
- Make sure Ollama is running: `ollama serve`

**"AWS credentials not found"**
- Run `aws sso login` to authenticate

**"Database connection failed"**
- Verify PostgreSQL is running
- Check connection string in server.py
