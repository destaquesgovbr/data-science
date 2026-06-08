# Issues: Implementação do Sistema de Embeddings em Produção

**Base:** Resultados da Issue #1 - Comparativo de Modelos de Embedding PT-BR  
**Status:** Backlog para implementação pós-pesquisa  
**Data:** Maio 2026

---

## Issue #6: Pipeline de Embeddings para Retrieval Semântico

**Tipo:** Implementação / Engenharia de Produção  
**Status:** 🟡 Planejado  
**Prioridade:** Alta  
**Complexidade:** 6-8 semanas  
**Dependências:** Issue #1 (concluída)

### Contexto e Motivação

Com a conclusão da Issue #1, temos:
- **Modelo selecionado:** [A DEFINIR com base nos resultados da Issue #1]
  - Opção esperada: BGE-M3 (multilingual, 1024 dim, 8192 tokens) ou BGE-large-pt
- **Métricas de qualidade:** NDCG@10, MAP, MRR validadas
- **Trade-offs mapeados:** Dimensionalidade, contexto, velocidade, storage

Agora precisamos **implementar sistema de embeddings para produção**, com:
- Indexação de 300k+ documentos (corpus governamental)
- Busca semântica em tempo real (< 100ms)
- Atualização incremental do índice
- Escalabilidade para milhões de documentos

### Objetivo Geral

Implementar pipeline completo de embeddings para retrieval semântico:
- ✅ Gerar embeddings de 300k+ documentos existentes
- ✅ Indexar em vector database escalável (FAISS, Qdrant, ou Milvus)
- ✅ API de busca semântica em tempo real
- ✅ Pipeline de atualização incremental (novos documentos)
- ✅ Monitoramento de qualidade e drift

### Abordagem Técnica

#### 1. Arquitetura do Sistema

```
┌─────────────────────────────────────┐
│  Corpus de Documentos (300k+)      │
│  - Título, conteúdo, metadata       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Batch Encoding Pipeline            │
│  - Chunking (se doc > 8k tokens)    │
│  - Batch processing (GPU)           │
│  - Progress tracking                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Vector Database                    │
│  - FAISS / Qdrant / Milvus          │
│  - Index: HNSW ou IVF-PQ            │
│  - Metadados: categoria, data, etc  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Search API (FastAPI)               │
│  - POST /search/semantic            │
│  - Filters: categoria, data, órgão  │
│  - Hybrid: semântica + keywords     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Incremental Update Pipeline        │
│  - Detectar novos documentos        │
│  - Gerar embeddings                 │
│  - Update index online              │
└─────────────────────────────────────┘
```

#### 2. Stack Tecnológica

**Modelo de Embedding:**
- Modelo: [resultado da Issue #1]
- Framework: sentence-transformers
- Inference: GPU (batch) ou CPU (real-time queries) -> usar instância EC2 disponível

**Vector Database:**
```python
# Opção 1: FAISS (local, rápido, sem servidor)
import faiss

index = faiss.IndexHNSWFlat(dimension, M=32)
index = faiss.IndexIVFPQ(quantizer, dimension, nlist=100, M=8, nbits=8)

# Opção 2: Qdrant (servidor, features avançadas)
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)
client.create_collection(
    collection_name="news",
    vectors_config={"size": 1024, "distance": "Cosine"}
)

# Opção 3: Milvus (cluster, alta escala)
from pymilvus import connections, Collection

connections.connect(host="localhost", port=19530)
```

**Decisão:** FAISS para MVP (simples, sem infra adicional), migrar para Qdrant se precisar de features avançadas (filtros complexos, multi-tenancy).

#### 3. Pipeline de Encoding em Batch

**Desafio:** 300k documentos × 1000 tokens médio = longo tempo de processamento

**Solução:**
```python
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import numpy as np

model = SentenceTransformer('BAAI/bge-m3')
model.to('cuda')  # GPU

def batch_encode_corpus(documents, batch_size=32, output_file='embeddings.npy'):
    """
    Gera embeddings em batches com progress tracking.
    Salva checkpoints para recuperação.
    """
    
    embeddings = []
    
    for i in tqdm(range(0, len(documents), batch_size)):
        batch = documents[i:i+batch_size]
        
        # Encode batch
        batch_embeddings = model.encode(
            batch,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Para cosine similarity
        )
        
        embeddings.append(batch_embeddings)
        
        # Checkpoint a cada 10k docs
        if (i // batch_size) % 312 == 0:  # 10k/32
            np.save(f'embeddings_checkpoint_{i}.npy', np.vstack(embeddings))
    
    # Salvar final
    all_embeddings = np.vstack(embeddings)
    np.save(output_file, all_embeddings)
    
    return all_embeddings

# Estimativa: 300k docs, batch_size=32
# GPU A10G: ~5 docs/segundo → ~16 horas
# GPU A100: ~15 docs/segundo → ~5.5 horas
```

**Otimizações:**
- Usar `encode_multi_process()` se CPU
- Paralelizar em múltiplas GPUs se disponível
- Cachear embeddings (reprocessar só se doc mudou)

#### 4. Indexação com FAISS

**Index Types:**

```python
import faiss

dimension = 1024  # BGE-M3

# Opção 1: Flat (exata, sem aproximação)
# Bom para < 1M vetores
index = faiss.IndexFlatIP(dimension)  # Inner Product (cosine se normalized)
index.add(embeddings)
# Busca: O(n), 100% recall

# Opção 2: HNSW (gráfico hierárquico)
# Melhor para 100k-10M vetores
index = faiss.IndexHNSWFlat(dimension, M=32)
index.hnsw.efConstruction = 200
index.add(embeddings)
# Busca: O(log n), ~99% recall, muito rápido

# Opção 3: IVF + PQ (quantização)
# Para > 10M vetores, reduz storage
quantizer = faiss.IndexFlatIP(dimension)
index = faiss.IndexIVFPQ(quantizer, dimension, nlist=100, M=8, nbits=8)
index.train(embeddings[:100000])  # Treinar com sample
index.add(embeddings)
# Busca: O(1), ~95% recall, storage 8x menor
```

**Decisão para 300k docs:** HNSW (balanço perfeito)

#### 5. Busca Semântica

```python
from sentence_transformers import SentenceTransformer
import faiss

# Carregar modelo e index
model = SentenceTransformer('BAAI/bge-m3')
index = faiss.read_index('news_index.faiss')

def semantic_search(query: str, top_k: int = 10, filters: dict = None):
    """
    Busca semântica com filtros opcionais.
    """
    
    # 1. Gerar embedding da query
    query_embedding = model.encode([query], normalize_embeddings=True)
    
    # 2. Buscar no index
    scores, indices = index.search(query_embedding, top_k * 2)  # 2x para filtros
    
    # 3. Aplicar filtros (se houver)
    if filters:
        results = apply_filters(indices[0], scores[0], filters)
        results = results[:top_k]
    else:
        results = [
            {'doc_id': idx, 'score': score}
            for idx, score in zip(indices[0], scores[0])
        ][:top_k]
    
    # 4. Enriquecer com metadados
    results = enrich_with_metadata(results)
    
    return results

# Exemplo
results = semantic_search(
    query="vacinação contra covid-19",
    top_k=10,
    filters={'category': 'Saúde', 'date_after': '2023-01-01'}
)
```

**Latência esperada:**
- Encoding query: ~50ms (CPU) ou ~10ms (GPU)
- FAISS search: ~5-20ms (300k vetores, HNSW)
- Enrichment: ~5ms
- **Total: ~60-75ms** Dentro do target < 100ms

#### 6. Busca Híbrida (Semantic + Keyword)

**Motivação:** Embeddings capturam semântica, mas podem perder matches exatos (nomes próprios, siglas).

```python
from rank_bff import RankBFF

def hybrid_search(query: str, top_k: int = 10):
    """
    Combina busca semântica (embeddings) + keyword (BM25).
    """
    
    # 1. Semantic search
    semantic_results = semantic_search(query, top_k=50)
    
    # 2. Keyword search (BM25 via Elasticsearch ou local)
    keyword_results = bm25_search(query, top_k=50)
    
    # 3. Rerank com RRF (Reciprocal Rank Fusion)
    combined = reciprocal_rank_fusion([semantic_results, keyword_results])
    
    return combined[:top_k]

def reciprocal_rank_fusion(results_lists, k=60):
    """
    RRF: score = sum(1 / (k + rank_i))
    """
    scores = {}
    
    for results in results_lists:
        for rank, result in enumerate(results, start=1):
            doc_id = result['doc_id']
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    
    # Ordenar por score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    return [{'doc_id': doc_id, 'score': score} for doc_id, score in ranked]
```

**Benefícios:**
- Melhor recall (captura semântica + exato)
- Robust a variações de query
- +10-15% NDCG em benchmarks

#### 7. Atualização Incremental

```python
import time
from datetime import datetime

def incremental_update_pipeline(check_interval=300):  # 5 minutos
    """
    Pipeline que monitora novos documentos e atualiza index.
    """
    
    while True:
        # 1. Buscar novos documentos (desde último update)
        new_docs = fetch_new_documents(since=last_update_time)
        
        if len(new_docs) > 0:
            print(f"[{datetime.now()}] {len(new_docs)} novos documentos")
            
            # 2. Gerar embeddings
            new_embeddings = model.encode(
                [doc['content'] for doc in new_docs],
                batch_size=32,
                normalize_embeddings=True,
            )
            
            # 3. Adicionar ao index
            index.add(new_embeddings)
            
            # 4. Salvar checkpoint
            faiss.write_index(index, 'news_index.faiss')
            
            # 5. Atualizar metadata store
            save_metadata(new_docs)
            
            last_update_time = datetime.now()
        
        time.sleep(check_interval)
```

**Alternativa:** Event-driven (webhook quando novo doc publicado)

#### 8. Monitoramento de Qualidade

**Drift Detection:**
```python
def monthly_quality_check():
    """
    Avalia qualidade do retrieval mensalmente.
    """
    
    # 1. Dataset de teste (50 queries anotadas)
    test_queries = load_test_queries()
    
    # 2. Para cada query, buscar top-10
    results = []
    for query_id, query_text, relevant_docs in test_queries:
        retrieved = semantic_search(query_text, top_k=10)
        retrieved_ids = [r['doc_id'] for r in retrieved]
        
        # Calcular métricas
        ndcg = calculate_ndcg(retrieved_ids, relevant_docs)
        recall = calculate_recall(retrieved_ids, relevant_docs, k=10)
        
        results.append({'query_id': query_id, 'ndcg': ndcg, 'recall': recall})
    
    # 3. Métricas agregadas
    avg_ndcg = np.mean([r['ndcg'] for r in results])
    avg_recall = np.mean([r['recall'] for r in results])
    
    # 4. Comparar com baseline
    baseline_ndcg = 0.72  # Da Issue #1
    
    if avg_ndcg < baseline_ndcg * 0.93:  # Drift > 7%
        alert("NDCG degradou! Investigar.")
    
    return {'ndcg': avg_ndcg, 'recall': avg_recall}
```

### Entregas Planejadas (Deliverables)

#### Core (obrigatório para produção):

1. **`embedding_pipeline.py`** - Pipeline de batch encoding
2. **`vector_store.py`** - Abstração para FAISS/Qdrant
3. **`search_service.py`** - Serviço de busca semântica + híbrida
4. **`api/search.py`** - API REST para busca
5. **`incremental_update.py`** - Pipeline de atualização
6. **`tests/test_search_quality.py`** - Testes de qualidade (NDCG)
7. **`monitoring/search_metrics.py`** - Métricas de busca
8. **`docs/EMBEDDING_SYSTEM.md`** - Documentação técnica
9. **`scripts/initial_indexing.py`** - Script de indexação inicial
10. **Docker setup** - Containers para modelo + vector DB

#### Otimizações (pós-MVP):

11. **Cache de queries frequentes** - Redis para queries populares
12. **Reranking com cross-encoder** - Melhorar top-10 final
13. **Query expansion** - Expandir query com sinônimos
14. **Personalização** - Embeddings personalizados por usuário

### Métricas de Sucesso

**Qualidade:**
- NDCG@10 > [baseline da Issue #1] (validação mensal)
- Recall@10 > 0.80
- Usuários: CTR (click-through rate) > 30%

**Performance:**
- Latência P95 < 100ms
- Throughput > 100 queries/segundo
- Disponibilidade > 99.5%

**Escalabilidade:**
- Suporta 1M+ documentos sem degradação
- Atualização incremental < 1 minuto latência

### Cronograma Estimado

**Sprint 1 (Setup e Indexação Inicial):** 2 semanas
- Pipeline de batch encoding
- Indexação dos 300k documentos
- Testes de qualidade baseline

**Sprint 2 (API de Busca):** 2 semanas
- API REST com FastAPI
- Busca semântica básica
- Busca híbrida (semantic + keyword)

**Sprint 3 (Atualização Incremental):** 1 semana
- Pipeline de detecção de novos docs
- Update automático do index

**Sprint 4 (Monitoramento e Otimização):** 2 semanas
- Métricas de qualidade e performance
- Dashboard
- Otimizações de latência

**Total:** 7 semanas

### Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **Storage de embeddings** | Baixa | Médio | 300k × 1024 × 4 bytes = 1.2GB (gerenciável) |
| **Latência de encoding** | Média | Médio | Cache de queries, GPU para real-time |
| **Degradação de qualidade** | Baixa | Alto | Monitoramento NDCG mensal + alertas |
| **Escalabilidade** | Média | Alto | HNSW escala até 10M, migrar para sharding se necessário |

### Decisões Técnicas Chave

#### 1. Vector Database: FAISS vs Qdrant vs Milvus

| Aspecto | FAISS | Qdrant | Milvus |
|---------|-------|--------|--------|
| **Simplicidade** | +++++ | +++ | ++ |
| **Performance** | +++++ | ++++ | ++++ |
| **Features** | ++ | ++++ | +++++ |
| **Infra** | Local | Docker | Cluster |
| **Filtros** | Manual | Nativo | Nativo |

**Decisão MVP:** FAISS (simples, sem infra adicional)  
**Migração futura:** Qdrant se precisar filtros complexos

#### 2. Index Type: Flat vs HNSW vs IVF-PQ

| Tipo | Recall | Latência | Storage | Ideal para |
|------|--------|----------|---------|------------|
| Flat | 100% | O(n) | 100% | < 100k |
| HNSW | ~99% | O(log n) | 100% | 100k-10M |
| IVF-PQ | ~95% | O(1) | ~10% | > 10M |

**Decisão:** HNSW para 300k (perfeito para escala atual)

#### 3. Busca Híbrida: Sim ou Não?

**Análise:**
- Semantic: Captura sinônimos, paráfrases → Recall alto
- Keyword (BM25): Captura matches exatos → Precisão em nomes próprios

**Decisão:** Implementar híbrido (RRF fusion)  
**Justificativa:** +10-15% NDCG observado em benchmarks

### Referências

- **Documento de pesquisa:** Issue #1 (modelos comparados)
- **Papers:** 
  - FAISS: Efficient Similarity Search (Johnson et al.)
  - HNSW: Efficient and robust approximate nearest neighbor search (Malkov & Yashunin)
- **Código base:** Issue #1 notebooks

### Aprovações Necessárias

- [ ] Acesso a GPU para batch encoding (estimativa: ~10 horas)
- [ ] Storage para embeddings (~2GB) e index (~1.5GB)
- [ ] Infra para vector DB (se Qdrant: 1 container, 2GB RAM)

---

## Sub-Issues Detalhadas

### Issue #6.1: Pipeline de Batch Encoding
**Estimativa:** 1 semana  
**Entrega:** Script que gera embeddings de 300k docs com checkpoints

### Issue #6.2: Indexação FAISS
**Estimativa:** 3 dias  
**Entrega:** Index HNSW otimizado + benchmarks

### Issue #6.3: API de Busca Semântica
**Estimativa:** 1 semana  
**Entrega:** Endpoint `/search/semantic` com filtros

### Issue #6.4: Busca Híbrida
**Estimativa:** 4 dias  
**Entrega:** RRF fusion de semantic + BM25

### Issue #6.5: Atualização Incremental
**Estimativa:** 1 semana  
**Entrega:** Pipeline que atualiza index a cada 5min

### Issue #6.6: Monitoramento de Qualidade
**Estimativa:** 4 dias  
**Entrega:** Pipeline de NDCG mensal + alertas

### Issue #6.7: Otimização de Latência
**Estimativa:** 3 dias  
**Entrega:** Cache de queries + profiling

### Issue #6.8: Documentação
**Estimativa:** 3 dias  
**Entrega:** Docs técnicas + runbooks

---

## Priorização

### P0 - Crítico (MVP)
#6.1, #6.2, #6.3, #6.5

### P1 - Alta
#6.4, #6.6, #6.8

### P2 - Média
#6.7

---

**Estimativa Total:** ~7 semanas (1 dev full-time)
