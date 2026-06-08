# Anexo: Estratégia de Migração Gradual de Embeddings

**Documento complementar à Issue #6**  
**GPU disponível:** EC2 com NVIDIA L4 (24GB VRAM)  
**Situação:** Sistema legado já tem embeddings - migração pode ser gradual

---

## Contexto

Diferente de uma implementação do zero, temos:
- **Sistema legado funcionando** com embeddings antigos
- **GPU L4 disponível** (24GB VRAM) na EC2
- **Não há urgência** de migrar tudo de uma vez
- **Prioridade:** Novos documentos usam modelo melhor

**Estratégia:** Coexistência dual durante transição (30 dias)

---

## Capacidade da GPU L4

### Especificações Técnicas

| Aspecto | L4 | A10G (ref) | A100 (ref) |
|---------|-----|-----------|-----------|
| **VRAM** | 24GB | 24GB | 40/80GB |
| **Throughput estimado** | 10-15 docs/seg | 5-8 docs/seg | 15-20 docs/seg |
| **Batch size (BGE-M3)** | 64 | 32 | 128 |
| **Custo/hora** | ~$0.70 | ~$1.00 | ~$4.00 |

### Capacidade Diária

```python
# L4 rodando 3-4 horas/dia em background
throughput = 12 docs/seg  # Média
horas_disponiveis = 3.5
segundos_disponiveis = horas_disponiveis * 3600

capacidade_diaria = throughput * segundos_disponiveis
# = 12 × 12,600 = 151,200 docs/dia (!!)

# Na prática, com overhead, checkpoints, etc:
capacidade_real = 10_000 docs/dia  # Conservador
```

**Conclusão:** 300k docs ÷ 10k/dia = **30 dias** para migração completa

---

## Arquitetura Dual Index

### Componentes

```
┌──────────────────────────────────────────────────┐
│  DualIndexManager                                │
│                                                  │
│  ┌────────────────────┐  ┌────────────────────┐ │
│  │  NEW INDEX         │  │  LEGACY INDEX      │ │
│  │  (BGE-M3)          │  │  (modelo antigo)   │ │
│  │                    │  │                    │ │
│  │  Docs migrados:    │  │  Docs não migrados:│ │
│  │  - Novos (100%)    │  │  - Antigos pending │ │
│  │  - Antigos (N%)    │  │                    │ │
│  └────────────────────┘  └────────────────────┘ │
│                                                  │
│  migration_status.json:                          │
│  {                                               │
│    "doc_123": true,   # Já migrado              │
│    "doc_456": false,  # Ainda no legado         │
│    ...                                           │
│  }                                               │
└──────────────────────────────────────────────────┘
```

### Fluxo de Busca

```python
def search_with_dual_index(query, top_k=10):
    """
    1. Busca no NEW index primeiro
    2. Filtra apenas docs já migrados
    3. Se faltarem resultados, busca no LEGACY
    4. Retorna top_k mesclado
    """
    
    query_emb_new = new_model.encode(query)
    query_emb_legacy = legacy_model.encode(query)  # Se modelos diferentes
    
    # Buscar em ambos
    results_new = new_index.search(query_emb_new, top_k * 2)
    results_legacy = legacy_index.search(query_emb_legacy, top_k * 2)
    
    # Separar por status de migração
    migrated = [r for r in results_new if migration_status[r['doc_id']]]
    not_migrated = [r for r in results_legacy if not migration_status[r['doc_id']]]
    
    # Combinar e rerankar
    combined = migrated + not_migrated
    combined.sort(key=lambda x: x['score'], reverse=True)
    
    return combined[:top_k]
```

---

## Pipeline de Migração Gradual

### Priorização Inteligente

```python
def calculate_migration_priority(doc):
    """
    Determina prioridade de migração de cada documento.
    
    Prioridade 1 (URGENT): Novos documentos
    Prioridade 2 (HIGH): Docs acessados recentemente
    Prioridade 3 (MEDIUM): Categorias importantes
    Prioridade 4 (LOW): Long tail
    """
    
    # Documento novo (sem embedding antigo)
    if not doc.get('has_legacy_embedding'):
        return 1, doc
    
    # Documento hot (acessado nos últimos 30 dias)
    if doc.get('access_count_30d', 0) > 10:
        return 2, doc
    
    # Categorias prioritárias
    if doc.get('category') in ['Saúde', 'Economia', 'Educação']:
        return 3, doc
    
    # Resto
    return 4, doc

def get_daily_batch(quota=10_000):
    """
    Seleciona próximos docs a migrar (por prioridade).
    """
    
    # Buscar docs pendentes
    pending = fetch_pending_migration()
    
    # Ordenar por prioridade
    prioritized = sorted(pending, key=calculate_migration_priority)
    
    # Retornar quota de hoje
    return prioritized[:quota]
```

### Loop de Migração

```python
import time
from datetime import datetime

def migration_loop(daily_quota=10_000, batch_size=64):
    """
    Roda continuamente em background.
    
    Comportamento:
    - Novos docs: processa imediatamente (prioridade)
    - Antigos: processa daily_quota por dia
    - Para quando migração completa (100%)
    """
    
    model = SentenceTransformer('BAAI/bge-m3')
    model.to('cuda')  # L4
    
    while True:
        # PARTE 1: Novos documentos (prioridade máxima)
        new_docs = fetch_new_documents_without_embedding()
        
        if len(new_docs) > 0:
            print(f"[{datetime.now()}] URGENT: {len(new_docs)} novos docs")
            
            # Processar imediatamente
            for i in range(0, len(new_docs), batch_size):
                batch = new_docs[i:i+batch_size]
                
                embeddings = model.encode(
                    [d['content'] for d in batch],
                    batch_size=batch_size,
                    normalize_embeddings=True,
                )
                
                # Adicionar ao NEW index
                new_index.add(embeddings)
                
                # Marcar como migrados
                for doc in batch:
                    migration_status[doc['id']] = True
            
            save_migration_status()
            print(f"  {len(new_docs)} novos docs processados")
        
        # PARTE 2: Migração gradual de antigos (background)
        old_batch = get_daily_batch(quota=daily_quota)
        
        if len(old_batch) == 0:
            print(f"[{datetime.now()}] MIGRAÇÃO COMPLETA!")
            break
        
        print(f"[{datetime.now()}] Migrando {len(old_batch)} docs antigos...")
        
        for i in range(0, len(old_batch), batch_size):
            batch = old_batch[i:i+batch_size]
            
            embeddings = model.encode(
                [d['content'] for d in batch],
                batch_size=batch_size,
                normalize_embeddings=True,
            )
            
            new_index.add(embeddings)
            
            for doc in batch:
                migration_status[doc['id']] = True
        
        save_migration_status()
        
        # Calcular progresso
        total_docs = count_total_documents()
        migrated_docs = sum(migration_status.values())
        progress_pct = (migrated_docs / total_docs) * 100
        
        print(f"  Progresso: {progress_pct:.1f}% ({migrated_docs}/{total_docs})")
        
        # Dormir até amanhã (ou próxima janela)
        # Ajustar conforme disponibilidade da GPU
        time.sleep(3600)  # 1 hora (ajustar)
```

### Dashboard de Migração

```python
def migration_dashboard():
    """
    Dashboard para acompanhar progresso.
    """
    
    status = load_migration_status()
    total = count_total_documents()
    migrated = sum(status.values())
    pending = total - migrated
    
    # Por prioridade
    p1_pending = count_pending_by_priority(1)
    p2_pending = count_pending_by_priority(2)
    p3_pending = count_pending_by_priority(3)
    p4_pending = count_pending_by_priority(4)
    
    # Estimativa de conclusão
    daily_rate = 10_000
    days_remaining = pending / daily_rate
    
    print(f"""
    ╔══════════════════════════════════════════╗
    ║     MIGRAÇÃO DE EMBEDDINGS - STATUS      ║
    ╠══════════════════════════════════════════╣
    ║                                          ║
    ║  Progresso: {migrated:,}/{total:,} ({migrated/total*100:.1f}%)  ║
    ║  Pendentes: {pending:,}                         ║
    ║                                          ║
    ║  Por prioridade:                         ║
    ║    P1 (Urgent):  {p1_pending:>6,} docs         ║
    ║    P2 (High):    {p2_pending:>6,} docs         ║
    ║    P3 (Medium):  {p3_pending:>6,} docs         ║
    ║    P4 (Low):     {p4_pending:>6,} docs         ║
    ║                                          ║
    ║  Taxa: {daily_rate:,} docs/dia                  ║
    ║  ETA: {days_remaining:.0f} dias                         ║
    ║                                          ║
    ╚══════════════════════════════════════════╝
    """)
    
    # Gráfico de progresso ao longo do tempo
    plot_migration_progress()
```

---

## Otimizações para L4

### 1. Batch Size Maior

```python
# L4 tem 24GB VRAM - pode usar batch maior que GPUs menores
# BGE-M3 (1024 dim): ~400MB VRAM por batch de 64

BATCH_SIZE_L4 = 64  # vs 32 em A10G/T4
```

### 2. Precision FP16

```python
# Usar FP16 (mixed precision) para 2x speedup
model = SentenceTransformer('BAAI/bge-m3')
model.to('cuda')
model.half()  # FP16

# Atenção: verificar se não degrada qualidade (testar sample)
```

### 3. Modelo Persistente em VRAM

```python
# Não recarregar modelo entre batches
# Manter em VRAM durante todo o dia

# RUIM (recarga constante):
for batch in batches:
    model = SentenceTransformer('BAAI/bge-m3')  # ❌ Lento
    model.to('cuda')
    embeddings = model.encode(batch)

# BOM (carrega uma vez):
model = SentenceTransformer('BAAI/bge-m3')
model.to('cuda')

for batch in batches:
    embeddings = model.encode(batch)  # ✅ Rápido
```

---

## Cronograma Revisado

### Fase 1: Setup (Semana 1)
**Objetivo:** Sistema dual funcionando

- [ ] Implementar `DualIndexManager`
- [ ] Carregar index legado
- [ ] Criar index novo (vazio)
- [ ] Migrar primeiros 10k docs (PoC)
- [ ] Testar busca híbrida

**Entrega:** Sistema funcionando com dual index

### Fase 2: Pipeline de Migração (Semana 2)
**Objetivo:** Automação completa

- [ ] Implementar priorização
- [ ] Loop de migração contínua
- [ ] Dashboard de progresso
- [ ] Alertas (se migração travar)

**Entrega:** Pipeline rodando automaticamente

### Fase 3: API e Monitoramento (Semanas 3-4)
**Objetivo:** Produção-ready

- [ ] API REST com busca dual
- [ ] Métricas de qualidade
- [ ] Comparação NEW vs LEGACY (A/B test em sample)
- [ ] Documentação

**Entrega:** API em produção

### Fase 4: Migração Completa (30 dias em background)
**Objetivo:** 100% migrado

- Pipeline roda automaticamente (10k/dia)
- Monitoramento diário
- Ajustes se necessário

**Resultado:** Após 30 dias:
- [ ] 100% docs migrados
- [ ] Remover index legado
- [ ] Simplificar código (remover dual logic)

---

## Benefícios da Abordagem Gradual

### 1. **Zero Downtime**
Sistema nunca para  
Busca funciona 100% do tempo  
Usuário não percebe transição  

### 2. **Priorização Inteligente**
Novos docs: embedding melhor desde dia 1  
Docs populares: migrados primeiro  
Long tail: migrado sem urgência  

### 3. **Flexibilidade**
Pode pausar/retomar migração  
Ajustar quota diária conforme disponibilidade GPU  
Rollback possível (manter legado)  

### 4. **Custo Controlado**
GPU usada apenas 3-4h/dia  
Não precisa de GPU dedicada 24/7  
Custo total: ~$70 (30 dias × 3.5h/dia × $0.70/h)  

---

## Checklist de Implementação

### Setup Inicial
- [ ] Configurar EC2 com L4
- [ ] Instalar sentence-transformers + FAISS
- [ ] Carregar modelo BGE-M3 (ou resultado Issue #1)
- [ ] Testar throughput (batch_size 64)

### Dual Index
- [ ] Implementar `DualIndexManager`
- [ ] Carregar index legado
- [ ] Criar index novo (HNSW)
- [ ] Implementar busca híbrida

### Migração
- [ ] Função de priorização
- [ ] Loop de migração contínua
- [ ] Checkpoints (a cada 1k docs)
- [ ] Dashboard de progresso

### Monitoramento
- [ ] Métricas: docs migrados/dia
- [ ] Alertas: se migração travar > 24h
- [ ] Comparação qualidade: NEW vs LEGACY (sample)

### Produção
- [ ] API REST funcionando com dual index
- [ ] Documentação para equipe
- [ ] Plano de remoção do legado (após 100%)

---

## FAQ

### Q: E se a GPU L4 não estiver disponível 24/7?
**A:** Pipeline é pausável. Roda quando GPU disponível. Progresso salvo em checkpoints.

### Q: Quanto custa a migração total?
**A:** ~$70 (30 dias × 3.5h/dia × $0.70/h). Mas GPU já está provisionada, então custo incremental pode ser zero.

### Q: E se quisermos acelerar?
**A:** Aumentar daily_quota para 20k ou 30k. L4 aguenta ~150k/dia se rodar full-time.

### Q: Precisamos manter index legado para sempre?
**A:** Não. Após 100% migrado (30 dias), remover legado e simplificar código.

### Q: E se precisarmos reverter?
**A:** Index legado fica intacto até 100%. Rollback é trivial (trocar default para legado).

---

**Estimativa:** 4 semanas para sistema completo + 30 dias de migração automática em background
