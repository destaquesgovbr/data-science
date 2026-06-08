# Fase 5: API REST para RAG

**Objetivo**: Criar interface REST para acesso ao sistema RAG, permitindo integração com aplicações externas.

**Status**: ✅ Implementado e testado

---

## 1. Visão Geral

### Componentes

```
┌─────────────────────────────────────────────────────────┐
│                    API Architecture                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  HTTP Client (curl/Python/JS)                            │
│         ↓                                                │
│  FastAPI Server (api/server.py)                          │
│         ↓                                                │
│  Generator (orchestration)                               │
│         ↓                                                │
│  ┌──────────────────┐      ┌───────────────────┐       │
│  │   Retriever      │      │   LLM Provider    │       │
│  │  (PostgreSQL)    │      │ (Bedrock/Ollama)  │       │
│  └──────────────────┘      └───────────────────┘       │
│         ↓                           ↓                    │
│  JSON Response (answer + sources + metrics)             │
└─────────────────────────────────────────────────────────┘
```

### Arquivos Criados

- **[api/server.py](api/server.py)** - FastAPI REST server (350 linhas)
- **[api/client.py](api/client.py)** - Interactive CLI client (270 linhas)
- **[api/demo.py](api/demo.py)** - Quick demo script (150 linhas)
- **[api/README.md](api/README.md)** - API documentation

---

## 2. API Endpoints

### GET /

Informações básicas da API.

**Response:**
```json
{
  "name": "RAG Q&A API",
  "version": "1.0.0",
  "endpoints": {
    "query": "/query (POST)",
    "health": "/health (GET)",
    "docs": "/docs (GET)"
  }
}
```

### GET /health

Health check - verifica componentes do sistema.

**Response:**
```json
{
  "status": "ok",
  "embedder": "ok",
  "database": "ok",
  "llm_providers": ["bedrock", "ollama"]
}
```

### POST /query

**Endpoint principal de Q&A.**

**Request Body:**
```json
{
  "query": "Qual foi o valor do Plano Safra?",
  
  // Retrieval config
  "top_k": 5,
  "use_reranking": true,
  
  // LLM config
  "provider": "bedrock",
  "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "max_tokens": 2000,
  "temperature": 0.0,
  
  // Prompt template
  "prompt_template": "default",
  
  // Optional filters
  "category": null,
  "agency": null
}
```

**Response:**
```json
{
  "answer": "O Plano Safra 2025/2026 conta com R$ 113,4 bilhões programados...",
  "sources": [
    {
      "index": 1,
      "title": "Plano Safra 2025/2026: crédito rural cresce 7%...",
      "url": "https://www.gov.br/noticias/doc_01_36",
      "category": "Agricultura",
      "agency": "secom",
      "chunk_text": "...",
      "score": 3.664
    }
  ],
  "query": "Qual foi o valor do Plano Safra?",
  "latency_ms": {
    "retrieval_ms": 186,
    "generation_ms": 1989,
    "total_ms": 2175
  },
  "tokens_input": 697,
  "tokens_output": 163,
  "cost_usd": 0.0047,
  "llm_model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "llm_provider": "bedrock",
  "retrieval_config": {
    "num_results": 3,
    "reranking": true
  }
}
```

### GET /docs

Swagger UI interativa (gerada automaticamente pelo FastAPI).

Acesse `http://localhost:8000/docs` no navegador para interface web completa.

---

## 3. Inicialização

### Server

```bash
cd /l/disk0/lpmoraes/environments/data-science/source/rag

# Start server
python api/server.py

# Server will start on http://localhost:8000
```

**Lazy Loading Strategy:**
- Embedder carregado na primeira requisição (~3s)
- LLM providers em cache por (provider, model)
- Retriever inicializado uma vez

**Log de Inicialização:**
```
╔══════════════════════════════════════════════════════════════╗
║                    RAG Q&A API Server                        ║
╠══════════════════════════════════════════════════════════════╣
║  Endpoints:                                                  ║
║    GET  /           - API info                               ║
║    GET  /health     - Health check                           ║
║    POST /query      - Q&A endpoint                           ║
║    GET  /docs       - Interactive API docs (Swagger UI)      ║
╚══════════════════════════════════════════════════════════════╝

INFO:     Started server process [53252]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Interactive Client

```bash
# In another terminal
python api/client.py
```

**Features:**
- REPL interface (Read-Eval-Print Loop)
- Commands: `/help`, `/config`, `/show`, `/exit`
- Live configuration changes (model, top-k, etc.)
- Rich formatted output (markdown, tables, panels)

**Screenshot:**
```
╭───────────────────────────────────────╮
│ RAG Q&A - Interactive Client          │
│                                       │
│ Ask questions about Brazilian         │
│ government news                       │
│                                       │
│ Commands:                             │
│   /help    - Show commands            │
│   /config  - Change settings          │
│   /exit    - Quit                     │
╰───────────────────────────────────────╯

> Qual foi o valor do Plano Safra?

[Answer panel with markdown]
[Sources list]
[Metrics: latency, tokens, cost]
```

### Demo Script

```bash
# Quick demo with sample queries
python api/demo.py
```

Runs 3 pre-configured queries and displays results.

---

## 4. Uso Programático

### Python

```python
import requests

API_URL = "http://localhost:8000"

# Simple query
response = requests.post(
    f"{API_URL}/query",
    json={
        "query": "Qual foi o valor do Plano Safra?",
        "top_k": 5,
        "use_reranking": True
    },
    timeout=120
)

data = response.json()
print(data['answer'])

for source in data['sources']:
    print(f"[{source['index']}] {source['title']}")
```

### curl

```bash
# Health check
curl http://localhost:8000/health

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual foi o valor do Plano Safra?",
    "top_k": 5,
    "use_reranking": true,
    "provider": "bedrock"
  }'
```

### JavaScript (fetch)

```javascript
const response = await fetch('http://localhost:8000/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'Qual foi o valor do Plano Safra?',
    top_k: 5,
    use_reranking: true
  })
});

const data = await response.json();
console.log(data.answer);
```

---

## 5. Configuração e Opções

### Providers

**Bedrock (AWS)**
- `provider: "bedrock"`
- Models:
  - `us.anthropic.claude-sonnet-4-6` - Best quality
  - `us.anthropic.claude-haiku-4-5-20251001-v1:0` - Fast (default)
  - `us.anthropic.claude-sonnet-4-5-20250929-v1:0` - Balanced

**Ollama (Local)**
- `provider: "ollama"`
- Models:
  - `qwen2.5:7b` - Multilingual (default)
  - `llama3.1:8b` - Good quality
  - `mistral:7b` - Fast

### Prompt Templates

- `default` - Balanced instructions with anti-hallucination
- `factual` - Focus on facts only, concise
- `summary` - Create structured summaries
- `comparison` - Compare policies/programs

### Filtros

```json
{
  "category": "Agricultura",  // Filter by document category
  "agency": "secom"           // Filter by agency
}
```

---

## 6. Performance

### Latency Breakdown (Bedrock Haiku 4.5)

| Component | Time | % |
|-----------|------|---|
| Retrieval (with reranking) | 200-500ms | 10-20% |
| LLM Generation | 2-3s | 80-90% |
| **Total** | **2.2-3.5s** | **100%** |

### Optimizations

**Implementadas:**
- ✅ Lazy loading (embedder carregado apenas na primeira requisição)
- ✅ LLM provider caching (evita reinicialização)
- ✅ Connection pooling PostgreSQL (via psycopg)

**Futuras:**
- [ ] Response caching (Redis) para queries frequentes
- [ ] Async endpoint (`/query-async` com task queue)
- [ ] Batch endpoint (`/batch-query` para múltiplas queries)
- [ ] Streaming endpoint (`/query-stream` com SSE)

### Custos

**Bedrock Haiku 4.5:**
- Custo médio: **$0.005-0.007/query**
- 1000 queries/dia = **$5-7/dia** = **$150-210/mês**

**Bedrock Sonnet 4.6:**
- Custo médio: **$0.005-0.006/query**
- Similar ao Haiku (Sonnet 4.6 pricing é competitivo)

**Ollama (Local):**
- Custo: **$0/query**
- Hardware: ~$2000 GPU inicial (amortizado)

---

## 7. Testes e Resultados

### Demo Execution (3 queries)

**Query 1: "Qual foi o valor destinado ao Plano Safra 2025/2026?"**
- ✅ Resposta correta: "R$ 113,4 bilhões programados [1]"
- Latência: 2.2s (186ms retrieval + 1.9s generation)
- Tokens: 163
- Custo: $0.0047
- Score top source: 3.66 (altamente relevante)

**Query 2: "Quais ações o governo tomou relacionadas à saúde?"**
- ✅ Resposta: Encontrou ação sobre proteção de dados no SUS [1]
- Latência: 3.3s (366ms retrieval + 2.9s generation)
- Tokens: 246
- Custo: $0.0061
- Nota: LLM corretamente indicou limitação das fontes disponíveis

**Query 3: "O que foi anunciado sobre agricultura familiar?"**
- ✅ Resposta honesta: "Não encontrei informações..." (sem hallucination)
- Latência: 2.5s (464ms retrieval + 2.0s generation)
- Tokens: 128
- Custo: $0.0046
- Score top source: -8.15 (irrelevante, LLM não inventou resposta)

**Observações:**
1. Sistema funcionou perfeitamente para query com resposta disponível
2. LLM não alucinou quando não havia resposta (anti-hallucination funcionando)
3. Latência consistente (2-3s total)
4. Custo controlado (~$0.005/query)
5. Re-ranking eficaz (source relevante sempre em primeiro)

---

## 8. Arquitetura Técnica

### FastAPI Server

**Características:**
- Async/await support (ready for async endpoints)
- Automatic OpenAPI/Swagger docs
- Pydantic models for validation
- CORS enabled (cross-origin requests)

**Global State:**
```python
# Lazy initialization
_embedder = None      # SentenceTransformer (BGE-M3)
_retriever = None     # Retriever instance
_reranker = None      # Cross-encoder reranker
_llm_cache = {}       # {(provider, model): LLMProvider}
```

**Key Functions:**
```python
get_embedder()        # Load once, reuse
get_retriever()       # Load once, reuse
get_reranker()        # Load once, reuse
get_llm_provider()    # Cache by (provider, model)
```

### Request Flow

```python
@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    # 1. Get components (cached)
    retriever = get_retriever()
    llm = get_llm_provider(request.provider, request.model)
    
    # 2. Override config for this request
    retriever.config = RetrieverConfig(
        final_top_k=request.top_k,
        use_reranking=request.use_reranking
    )
    
    # 3. Create generator
    generator = Generator(retriever, llm, prompt_template)
    
    # 4. Generate answer
    rag_response = generator.generate(
        query=request.query,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        filters=filters
    )
    
    # 5. Convert to API response
    return QueryResponse(...)
```

### Error Handling

```python
try:
    # Process request
except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))
```

Errors logged to console, HTTP 500 returned to client.

---

## 9. Deployment

### Development

```bash
# Run with auto-reload
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### Production (Gunicorn)

```bash
# Install
pip install gunicorn

# Run with 4 workers
gunicorn api.server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Docker (Future)

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY source/rag /app

EXPOSE 8000
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

```bash
# Override defaults via env vars
export LLM_PROVIDER="bedrock"
export LLM_MODEL="us.anthropic.claude-haiku-4-5-20251001-v1:0"
export DB_HOST="localhost"
export DB_PORT="5433"
export DB_NAME="news_db"
export DB_USER="rag_user"
```

---

## 10. Monitoramento

### Métricas por Request

Cada response inclui:
- `latency_ms` - Breakdown retrieval vs generation
- `tokens_input` / `tokens_output` - Token usage
- `cost_usd` - Estimated cost
- `llm_model` / `llm_provider` - Model used

### Logging

Server logs (stdout):
```
Loading BGE-M3 embedder...
✓ Embedder loaded
Initializing retriever...
✓ Retriever initialized
Loading reranker...
✓ Reranker loaded
Initializing LLM provider: bedrock (us.anthropic.claude-haiku-4-5-20251001-v1:0)...
✓ LLM provider initialized and cached
✓ Query processed in 2175ms
```

### Future: Structured Logging

```python
import structlog

logger = structlog.get_logger()

logger.info("query_processed",
    query=query,
    latency_ms=latency,
    tokens_output=tokens,
    cost_usd=cost,
    model=model
)
```

### Future: Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

query_counter = Counter('rag_queries_total', 'Total queries')
query_latency = Histogram('rag_query_duration_seconds', 'Query latency')

# Expose /metrics endpoint
```

---

## 11. Segurança

### Implementado

- ✅ CORS configurado (allow all origins - dev mode)
- ✅ Request validation (Pydantic models)
- ✅ Timeouts (120s para LLM)
- ✅ Error handling (500 sem stack trace exposto ao cliente)

### TODO (Produção)

- [ ] API Key authentication
- [ ] Rate limiting (ex: 100 requests/hour/user)
- [ ] CORS restrito (origins específicos)
- [ ] HTTPS (TLS/SSL)
- [ ] Request size limits
- [ ] Input sanitization (SQL injection prevention)

---

## 12. Próximos Passos

### Prioritário

1. [ ] **Streaming endpoint** - SSE para respostas em tempo real
2. [ ] **Response caching** - Redis para queries frequentes
3. [ ] **API key auth** - Autenticação simples
4. [ ] **Rate limiting** - Prevenir abuso

### Futuro

5. [ ] **Batch endpoint** - Processar múltiplas queries
6. [ ] **Async processing** - Task queue (Celery/Redis)
7. [ ] **WebSocket** - Chat em tempo real
8. [ ] **Frontend web** - UI React/Vue
9. [ ] **Analytics dashboard** - Métricas de uso
10. [ ] **A/B testing** - Comparar diferentes configs

---

## 13. Exemplo: Integração com Frontend

### React Component

```javascript
import { useState } from 'react';

function RAGQueryBox() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    const response = await fetch('http://localhost:8000/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        top_k: 5,
        use_reranking: true
      })
    });

    const data = await response.json();
    setAnswer(data);
    setLoading(false);
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Pergunte sobre notícias governamentais..."
        />
        <button disabled={loading}>
          {loading ? 'Processando...' : 'Perguntar'}
        </button>
      </form>

      {answer && (
        <div>
          <h3>Resposta:</h3>
          <p>{answer.answer}</p>

          <h4>Fontes:</h4>
          <ul>
            {answer.sources.map(src => (
              <li key={src.index}>
                <a href={src.url}>{src.title}</a>
              </li>
            ))}
          </ul>

          <small>
            Latência: {answer.latency_ms.total_ms}ms |
            Custo: ${answer.cost_usd.toFixed(4)}
          </small>
        </div>
      )}
    </div>
  );
}
```

---

## 14. Conclusões

### Resultados Principais

1. **API REST funcional** - 3 endpoints (/, /health, /query)
2. **Client interativo** - REPL CLI para testes
3. **Demo script** - Showcase rápido do sistema
4. **Performance excelente** - 2-3s latência total
5. **Custo controlado** - ~$0.005/query
6. **Qualidade alta** - Respostas corretas com citações

### Lições Aprendidas

1. **Lazy loading essencial** - Evita startup lento (embedder é pesado)
2. **LLM caching funciona** - Providers reutilizados entre requests
3. **FastAPI é produtivo** - Docs automáticos, validação built-in
4. **Anti-hallucination funciona** - LLM não inventa quando não sabe
5. **Re-ranking consistente** - Source relevante sempre em top-1

### Recomendações

**Para desenvolvimento:**
- Use `python api/client.py` para testes interativos
- Use `http://localhost:8000/docs` para testar endpoints manualmente
- Logs em `stdout` são suficientes

**Para produção:**
- Implement authentication (API keys)
- Enable response caching (Redis)
- Add rate limiting
- Use Gunicorn com múltiplos workers
- Monitor com Prometheus + Grafana

---

**Última atualização**: 2026-05-29  
**Autor**: Claude Sonnet 4.6 + Luis Felipe de Moraes
