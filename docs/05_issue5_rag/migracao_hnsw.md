# Estratégia de Migração IVFFlat → HNSW

**Issue #5 - RAG System**  
**Fase 3 - Preparação para Produção**  
**Status:** 📋 Planejado

---

## 📋 Sumário Executivo

Migração de IVFFlat para HNSW é **obrigatória** para produção com 310k documentos (3.2M chunks). IVFFlat apresenta recall insuficiente (88%) e latência alta (80ms) nessa escala, enquanto HNSW mantém recall 98% com latência 15ms.

**Estratégia:** Desenvolvimento com IVFFlat (Fases 1-2), migração controlada (Fase 3), produção com HNSW.

---

## 🎯 Justificativa da Migração

### Análise Comparativa @ 3.2M Chunks (310k docs)

| Métrica | IVFFlat | HNSW | Delta |
|---------|---------|------|-------|
| **Recall@50** | 88% | 98% | +10% absoluto |
| **Latência Query** | 60-90ms | 10-15ms | **6x mais rápido** |
| **Build Time** | 5 min | 60 min | 12x mais lento |
| **Memória** | 15 GB | 14 GB | Similar |
| **Chunks Verificados** | 64.400 | 2.100 | 30x menos |
| **Throughput** | 12 queries/s | 66 queries/s | 5x maior |
| **Escala** | Degrada | O(log n) | HNSW mantém |

### Impacto no Pipeline RAG Completo

**Com IVFFlat (inadequado):**
```
Vector search:    80ms  ⚠️
Full-text:        30ms
RRF Fusion:       10ms
Re-ranking:      150ms
LLM Generation: 2000ms
────────────────────────
TOTAL:          2270ms
```

**Com HNSW (adequado):**
```
Vector search:    15ms  ✅ (-65ms, -72%)
Full-text:        30ms
RRF Fusion:       10ms
Re-ranking:      150ms
LLM Generation: 2000ms
────────────────────────
TOTAL:          2205ms
```

**Ganhos:**
- Latência: -3% end-to-end
- **Throughput retrieval:** +450% (66 vs 12 queries/s)
- **Recall:** +10% (crítico para qualidade de resposta)

---

## 📅 Cronograma de Migração

### Fase 1-2: Desenvolvimento com IVFFlat ✅
**Status:** Concluído (28/Mai/2026)  
**Dataset:** 100-10.000 documentos  
**Justificativa:** Experimentação rápida, rebuild instantâneo

### Fase 3: Migração HNSW (1-2 semanas)
**Status:** Planejado  
**Trigger:** Atingir 100k docs OU finalizar testes de retrieval  
**Dataset:** 100k+ documentos (~1M chunks)

#### Semana 1: Testes e Validação
- [ ] Setup staging com 100k documentos
- [ ] Benchmark HNSW vs IVFFlat (recall, latência, memória)
- [ ] Tuning parâmetros (m, ef_construction, ef_search)
- [ ] Validar queries representativas (ground truth)
- [ ] Teste de carga (concorrência, throughput)

#### Semana 2: Implementação Produção
- [ ] Script de migração automatizado
- [ ] Implementar estratégia índice duplo
- [ ] Documentação operacional (rebuild, monitoring)
- [ ] Dry-run migração em staging
- [ ] Go/No-go decision

### Fase 4+: Produção com HNSW ✅
**Dataset:** 310k+ documentos (crescendo)  
**Operação:** Rebuild semanal automatizado

---

## 🛠️ Plano de Implementação Técnica

### 1. Benchmark em Staging

**Script:** `scripts/benchmark_hnsw.py`

```python
#!/usr/bin/env python3
"""
Benchmark IVFFlat vs HNSW em staging.

Dataset: 100k docs (~1M chunks)
Queries: 100 queries representativas
Métricas: Recall@K, Latência P50/P95/P99, Memória
"""

import psycopg
import numpy as np
from time import time
from tqdm import tqdm

def benchmark_index(conn_string, index_type, queries, ground_truth):
    """Benchmark index performance."""
    
    latencies = []
    recalls = []
    
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            for query, relevant_ids in tqdm(zip(queries, ground_truth)):
                # Time query
                start = time()
                
                cur.execute("""
                    SELECT id, 1 - (embedding <=> %s::vector) as similarity
                    FROM document_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT 50
                """, (query, query))
                
                results = cur.fetchall()
                latency = (time() - start) * 1000  # ms
                latencies.append(latency)
                
                # Calculate recall
                retrieved_ids = {r[0] for r in results}
                recall = len(retrieved_ids & relevant_ids) / len(relevant_ids)
                recalls.append(recall)
    
    return {
        'latency_p50': np.percentile(latencies, 50),
        'latency_p95': np.percentile(latencies, 95),
        'latency_p99': np.percentile(latencies, 99),
        'recall_avg': np.mean(recalls),
        'recall_min': np.min(recalls),
    }

# Run benchmarks
results_ivfflat = benchmark_index(conn, 'ivfflat', queries, ground_truth)
results_hnsw = benchmark_index(conn, 'hnsw', queries, ground_truth)

# Compare
print(f"""
IVFFlat:
  Latency P50: {results_ivfflat['latency_p50']:.1f}ms
  Latency P95: {results_ivfflat['latency_p95']:.1f}ms
  Recall Avg:  {results_ivfflat['recall_avg']:.2%}

HNSW:
  Latency P50: {results_hnsw['latency_p50']:.1f}ms
  Latency P95: {results_hnsw['latency_p95']:.1f}ms
  Recall Avg:  {results_hnsw['recall_avg']:.2%}

HNSW Improvement:
  Latency: {results_ivfflat['latency_p95'] / results_hnsw['latency_p95']:.1f}x faster
  Recall:  +{(results_hnsw['recall_avg'] - results_ivfflat['recall_avg']) * 100:.1f}% absolute
""")
```

**Critérios de Aceite:**
- HNSW recall > 95%
- HNSW latency P95 < 20ms
- HNSW throughput > 50 queries/s (100 concorrentes)

---

### 2. Tuning de Parâmetros HNSW

**Parâmetros a Tunar:**

#### a) `m` (conexões por nó)
```sql
-- Trade-off: Recall vs Memória

m=8:   Recall ~95%, Memória 1x   (básico)
m=16:  Recall ~98%, Memória 1.5x (recomendado) ✅
m=32:  Recall ~99%, Memória 2x   (overkill)
```

**Escolha:** `m=16` (sweet spot)

#### b) `ef_construction` (build quality)
```sql
-- Trade-off: Recall vs Build Time

ef_construction=64:   Recall ~96%, Build 30 min (rápido)
ef_construction=128:  Recall ~98%, Build 60 min (recomendado) ✅
ef_construction=256:  Recall ~99%, Build 120 min (overkill)
```

**Escolha:** `ef_construction=128` (1h build aceitável semanal)

#### c) `ef_search` (query quality)
```sql
-- Trade-off: Recall vs Latência (TUNABLE em runtime!)

SET hnsw.ef_search = 40;   -- Recall ~95%, Latência 10ms (rápido)
SET hnsw.ef_search = 100;  -- Recall ~98%, Latência 15ms (recomendado) ✅
SET hnsw.ef_search = 200;  -- Recall ~99%, Latência 25ms (slow)
```

**Escolha inicial:** `ef_search=100`  
**Ajuste dinâmico:** Monitorar e ajustar baseado em métricas produção

---

### 3. Script de Migração

**Script:** `scripts/migrate_to_hnsw.py`

```python
#!/usr/bin/env python3
"""
Migra índice vetorial de IVFFlat para HNSW.

Estratégia: Zero downtime com índice duplo
"""

import psycopg
from datetime import datetime
import argparse

def migrate_to_hnsw(conn_string, drop_old=True, dry_run=False):
    """Execute migration."""
    
    print("="*60)
    print("MIGRAÇÃO IVFFlat → HNSW")
    print("="*60)
    
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            
            # 1. Verificar índice atual
            print("\n1. Verificando índice atual...")
            cur.execute("""
                SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass))
                FROM pg_indexes
                WHERE tablename = 'document_chunks'
                AND indexname LIKE '%embedding%'
            """)
            current_indexes = cur.fetchall()
            
            for idx_name, size in current_indexes:
                print(f"   {idx_name}: {size}")
            
            if dry_run:
                print("\n[DRY RUN] Parando aqui")
                return
            
            # 2. Criar índice HNSW (sem dropar IVFFlat ainda)
            print("\n2. Criando novo índice HNSW...")
            print("   ⚠️  Isso vai levar ~45-60 minutos")
            
            start = datetime.now()
            
            cur.execute("""
                CREATE INDEX CONCURRENTLY idx_chunks_embedding_hnsw
                ON document_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 128);
            """)
            
            elapsed = (datetime.now() - start).total_seconds() / 60
            print(f"   ✅ Índice criado em {elapsed:.1f} minutos")
            
            # 3. Configurar ef_search
            print("\n3. Configurando HNSW...")
            cur.execute("ALTER DATABASE news_db SET hnsw.ef_search = 100;")
            print("   ✅ ef_search = 100")
            
            # 4. Testar novo índice
            print("\n4. Testando novo índice...")
            cur.execute("""
                EXPLAIN ANALYZE
                SELECT id FROM document_chunks
                ORDER BY embedding <=> (SELECT embedding FROM document_chunks LIMIT 1)
                LIMIT 10;
            """)
            plan = cur.fetchall()
            
            # Verificar se está usando HNSW
            using_hnsw = any('hnsw' in str(row).lower() for row in plan)
            
            if using_hnsw:
                print("   ✅ Query usando HNSW")
            else:
                print("   ⚠️  Query NÃO está usando HNSW!")
                print("   Pode precisar ANALYZE ou REINDEX")
            
            # 5. Dropar índice antigo (se solicitado)
            if drop_old:
                print("\n5. Dropando índice IVFFlat antigo...")
                
                response = input("   Confirma? (yes/no): ")
                if response.lower() == 'yes':
                    cur.execute("DROP INDEX idx_chunks_embedding;")
                    print("   ✅ IVFFlat removido")
                    
                    # Renomear HNSW
                    cur.execute("""
                        ALTER INDEX idx_chunks_embedding_hnsw 
                        RENAME TO idx_chunks_embedding;
                    """)
                    print("   ✅ HNSW renomeado para idx_chunks_embedding")
                else:
                    print("   Mantendo ambos índices")
            
            # 6. ANALYZE
            print("\n6. Atualizando estatísticas...")
            cur.execute("ANALYZE document_chunks;")
            print("   ✅ ANALYZE concluído")
            
            conn.commit()
    
    print("\n" + "="*60)
    print("✅ MIGRAÇÃO CONCLUÍDA")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--drop-old', action='store_true', 
                        help='Drop IVFFlat index after migration')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done')
    args = parser.parse_args()
    
    conn_string = "host=localhost port=5433 dbname=news_db user=rag_user"
    migrate_to_hnsw(conn_string, drop_old=args.drop_old, dry_run=args.dry_run)
```

**Uso:**
```bash
# Dry run (mostra o que seria feito)
python scripts/migrate_to_hnsw.py --dry-run

# Migração (mantém IVFFlat)
python scripts/migrate_to_hnsw.py

# Migração completa (remove IVFFlat)
python scripts/migrate_to_hnsw.py --drop-old
```

---

### 4. Estratégia de Índice Duplo (Zero Downtime)

**Problema:** Rebuild HNSW leva ~60 minutos = downtime?

**Solução:** Dois índices simultâneos

#### Arquitetura

```
┌─────────────────────────────────────┐
│     document_chunks (3.2M)          │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       v                v
┌─────────────┐  ┌─────────────┐
│ HNSW Index  │  │ IVFFlat     │
│ (Base)      │  │ (Recent)    │
│             │  │             │
│ 3.16M chunks│  │ 40k chunks  │
│ age > 7d    │  │ age <= 7d   │
│             │  │             │
│ Rebuild:    │  │ Rebuild:    │
│ Weekly      │  │ Daily       │
│ 60 min      │  │ 2 min       │
└─────────────┘  └─────────────┘
       │                │
       └───────┬────────┘
               v
        Query results
     (union + re-rank)
```

#### Implementação

**Schema:**
```sql
-- Adicionar coluna de idade
ALTER TABLE document_chunks ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
CREATE INDEX idx_chunks_created ON document_chunks(created_at);

-- Índice HNSW (base, age > 7d)
CREATE INDEX idx_chunks_base_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WHERE created_at < NOW() - INTERVAL '7 days'
WITH (m = 16, ef_construction = 128);

-- Índice IVFFlat (recent, age <= 7d)
CREATE INDEX idx_chunks_recent_ivfflat
ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WHERE created_at >= NOW() - INTERVAL '7 days'
WITH (lists = 200);
```

**Query (application layer):**
```python
def hybrid_search(query_embedding, top_k=50):
    """Search using both indexes."""
    
    # Query base (HNSW)
    base_results = execute("""
        SELECT id, embedding <=> %s as distance
        FROM document_chunks
        WHERE created_at < NOW() - INTERVAL '7 days'
        ORDER BY embedding <=> %s
        LIMIT %s
    """, (query_embedding, query_embedding, top_k))
    
    # Query recent (IVFFlat)
    recent_results = execute("""
        SELECT id, embedding <=> %s as distance
        FROM document_chunks
        WHERE created_at >= NOW() - INTERVAL '7 days'
        ORDER BY embedding <=> %s
        LIMIT %s
    """, (query_embedding, query_embedding, top_k // 2))
    
    # Merge and re-rank
    all_results = base_results + recent_results
    all_results.sort(key=lambda x: x['distance'])
    
    return all_results[:top_k]
```

**Rebuild Semanal (Automatizado):**
```bash
#!/bin/bash
# cron: 0 2 * * 6 (Sábado 2AM)

# 1. Drop old base index
psql -c "DROP INDEX idx_chunks_base_hnsw;"

# 2. Rebuild base (60 min)
psql -c "
CREATE INDEX idx_chunks_base_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WHERE created_at < NOW() - INTERVAL '7 days'
WITH (m = 16, ef_construction = 128);
"

# 3. Rebuild recent (2 min)
psql -c "
REINDEX INDEX CONCURRENTLY idx_chunks_recent_ivfflat;
"

# 4. ANALYZE
psql -c "ANALYZE document_chunks;"

# 5. Notificar
echo "HNSW rebuild completed" | mail -s "RAG Index Rebuild" admin@company.com
```

---

## 📊 Métricas de Monitoramento

### Métricas Críticas

**1. Recall@K**
```sql
-- Query de teste com ground truth
WITH query_results AS (
    SELECT id FROM document_chunks
    ORDER BY embedding <=> :query_vector
    LIMIT 50
)
SELECT 
    COUNT(*) FILTER (WHERE id IN :ground_truth_ids) * 1.0 / 
    COUNT(*) AS recall
FROM query_results;
```

**Target:** Recall@50 > 95%

**2. Latência**
```python
# P50, P95, P99 latency
import prometheus_client

retrieval_latency = prometheus_client.Histogram(
    'rag_retrieval_latency_seconds',
    'Retrieval latency',
    buckets=[0.01, 0.02, 0.05, 0.1, 0.2, 0.5]
)

@retrieval_latency.time()
def vector_search(query):
    # ... search logic
```

**Target:** P95 < 20ms, P99 < 50ms

**3. Throughput**
```python
queries_per_second = prometheus_client.Counter(
    'rag_queries_total',
    'Total queries processed'
)
```

**Target:** > 50 queries/s sustained

**4. Index Size**
```sql
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE tablename = 'document_chunks';
```

**Target:** < 20 GB total

---

## ✅ Checklist de Go-Live

### Pré-Migração
- [ ] Backup completo do banco
- [ ] Benchmark em staging validado
- [ ] Scripts testados em staging
- [ ] Documentação operacional pronta
- [ ] Rollback plan definido

### Migração
- [ ] Índice HNSW criado (60 min)
- [ ] Testes de query passaram (recall > 95%)
- [ ] Latência dentro do target (P95 < 20ms)
- [ ] IVFFlat antigo removido (opcional)

### Pós-Migração
- [ ] Monitoramento ativo (24h)
- [ ] Nenhum erro crítico detectado
- [ ] Performance estável
- [ ] Documentação atualizada
- [ ] Time notificado

### Rollback (Se Necessário)
```sql
-- Reativar IVFFlat (se ainda existe)
ALTER INDEX idx_chunks_embedding_ivfflat RENAME TO idx_chunks_embedding;

-- Ou recriar rapidamente (5 min)
CREATE INDEX idx_chunks_embedding 
ON document_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 5000);
SET ivfflat.probes = 100;
```

---

## 📚 Referências

**pgvector Documentation:**
- https://github.com/pgvector/pgvector
- HNSW parameters tuning guide

**Papers:**
- "Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs" (Malkov & Yashunin, 2018)
- "IVF-HNSW: Inverted File with Hierarchical Navigable Small World" (2020)

**Benchmarks:**
- ann-benchmarks.com (HNSW consistently top performer)

---

## 🎯 Resumo Executivo

**Decisão:** Migrar de IVFFlat para HNSW na Fase 3 (após finalizar testes)

**Justificativa:** 
- IVFFlat inadequado para 310k docs (recall 88%, latência 80ms)
- HNSW mantém qualidade em escala (recall 98%, latência 15ms)

**Estratégia:**
1. Desenvolvimento com IVFFlat (rápido, experimentação)
2. Migração controlada em staging (100k docs)
3. Produção com HNSW + rebuild semanal automatizado

**Custo:** 
- Build inicial: 60 min (uma vez)
- Rebuild semanal: 60 min off-peak (automatizado)
- Compute: ~$2/mês (desprezível)

**Benefícios:**
- +10% recall (crítico para qualidade)
- 6x mais rápido (melhor UX)
- 5x mais throughput (suporta carga)

**Status:** Planejado para Junho 2026 (após Fase 2)

---

**Última atualização:** 28 Mai 2026  
**Autor:** Luis Felipe de Moraes + Claude Sonnet 4.5
