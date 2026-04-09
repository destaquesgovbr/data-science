# Issue #2 - Fine-Tuning de Embedding Models

**Status:** 🔜 Planejamento (aguardando Issue #1)  
**Dependência:** Issue #1 (baseline estabelecido)  
**Timeline estimada:** 2-3 semanas  
**Responsável:** Luis Felipe de Moraes

---

## Contexto

A Issue #2 será executada **se e quando** a Issue #1 indicar necessidade:

### Cenário A: Fine-tuning OBRIGATÓRIO
```
Baseline NDCG@10 < 0.80
→ Performance insuficiente para produção
→ Fine-tuning necessário para atingir meta (>0.85)
```

### Cenário B: Fine-tuning OPCIONAL
```
Baseline NDCG@10 = 0.80-0.85
→ Razoável, mas pode melhorar
→ Fine-tuning para otimização (target >0.88)
```

### Cenário C: Fine-tuning NÃO NECESSÁRIO
```
Baseline NDCG@10 > 0.85
→ Performance já adequada
→ Issue #2 fica como melhoria futura (opcional)
```

---

## Objetivos

### Meta Principal
```
Aumentar NDCG@10 em pelo menos 5-10% sobre baseline
```

### Metas Específicas
1. **Jargão BR:** Se baseline NDCG jargão < 0.80, subir para >0.85
2. **Consistência:** Se Consistency@10 < 0.70, subir para >0.80
3. **Geografia:** Se NDCG geografia < 0.75, subir para >0.80

### Critério de Sucesso
```
✅ NDCG@10 geral > 0.85 (mínimo aceitável)
✅ NDCG@10 jargão BR > 0.80 (crítico)
✅ Gap jargão-geral < 8% (robustez)
✅ Consistency@10 > 0.75 (estabilidade)
```

---

## Abordagens de Fine-Tuning

### 1. Contrastive Learning (Recomendado)

**Técnica:** Triplet Loss ou Multiple Negatives Ranking Loss

**Formato dos dados:**
```python
triplas = [
    (query, doc_positivo, doc_negativo),
    ("tilápia açude ema", "doc_01_08", "doc_15_03"),
    ("alevinos dnocs iracema", "doc_01_08", "doc_07_12"),
    ...
]
```

**Loss function:**
```python
# Multiple Negatives Ranking Loss (state-of-the-art)
# Para cada batch:
#   - 1 query
#   - 1 positivo
#   - N-1 negativos (in-batch negatives)
# 
# Model aprende a aproximar query do positivo
# e afastar dos negativos
```

**Vantagens:**
- Estado da arte para embeddings
- Funciona bem com poucos dados (5k-10k exemplos)
- Usado no treino original de BGE-M3, E5, etc.

**Referências:**
- Karpukhin et al. (2020): "Dense Passage Retrieval"
- Reimers & Gurevych (2019): "Sentence-BERT"
- Gao et al. (2021): "SimCSE"

---

### 2. Hard Negative Mining

**Problema:** Negativos aleatórios são fáceis demais

**Solução:** Usar negativos difíceis (docs similares mas irrelevantes)

**Estratégia:**
```python
# Para cada query:
negativos_dificeis = docs no top-20 mas com relevância = 0

# Exemplo:
query = "tilápia açude ema"
positivo = "doc_01_08" (âncora)
negativo_facil = "doc_15_23" (categoria diferente, distante)
negativo_dificil = "doc_01_03" (mesma categoria, mas tema diferente)

# Fine-tuning com negativos difíceis = modelo mais robusto
```

**Referências:**
- Xiong et al. (2021): "Approximate Nearest Neighbor Negative Contrastive Learning"
- Zhan et al. (2021): "Learning Dense Representations for Entity Retrieval"

---

### 3. Domain-Specific Pre-training

**Técnica:** Continuar pré-treino com corpus gov.br antes do fine-tuning

**Estratégia:**
```python
# Fase 1: Continuar pré-treino (MLM - Masked Language Modeling)
# Corpus: 300k notícias gov.br
# Objetivo: Modelo aprende vocabulário específico (jargões, siglas)

# Fase 2: Fine-tuning contrastivo
# Dados: Triplas (query, pos, neg)
# Objetivo: Modelo aprende relevância para queries
```

**Quando usar:**
- Se modelo multilíngue não conhece jargão BR
- Se NDCG jargão < 0.70 (muito baixo)

**Custo:**
- Mais demorado (1-2 semanas só fase 1)
- Requer mais recursos computacionais

**Referências:**
- Gururangan et al. (2020): "Don't Stop Pretraining"
- Lee et al. (2020): "BioBERT"

---

### 4. Multi-Task Learning

**Técnica:** Fine-tuning com múltiplos objetivos simultaneamente

**Tarefas:**
```python
# Tarefa 1: Relevância (principal)
loss_relevance = contrastive_loss(query, doc_pos, doc_neg)

# Tarefa 2: Classificação de categoria
loss_category = cross_entropy(doc_embedding, category_label)

# Tarefa 3: Detecção de jargão (auxiliar)
loss_jargon = binary_cross_entropy(has_jargon(doc))

# Loss total
loss = 0.7 * loss_relevance + 0.2 * loss_category + 0.1 * loss_jargon
```

**Vantagens:**
- Modelo aprende estrutura do domínio
- Melhora generalização

**Desvantagens:**
- Mais complexo de implementar
- Requer anotações adicionais (categorias)

---

## Preparação de Dados

### Fonte 1: Resultados da Issue #1 (Bootstrap)

**Usando as 259 queries testadas:**

```python
# Para cada query:
positivos = [
    doc for doc in top_20_results
    if ground_truth[doc] >= 2  # Relevância alta
]

negativos_faceis = [
    doc for doc in corpus
    if doc not in top_100_results  # Muito distantes
]

negativos_dificeis = [
    doc for doc in top_20_results
    if ground_truth[doc] == 0  # Perto mas irrelevante
]

# Gerar triplas:
for query in queries:
    for pos in positivos:
        for neg in negativos_dificeis[:5]:  # 5 negativos por positivo
            yield (query, pos, neg)
```

**Quantidade estimada:**
- 259 queries × 3 positivos × 5 negativos = ~3,900 triplas
- Pode aumentar com data augmentation

---

### Fonte 2: Data Augmentation

**Técnica 1: Paráfrase de queries**
```python
# Usar LLM para parafrasear queries
original = "tilápia açude ema"
parafrase = [
    "peixamento açude iracema",
    "criação tilápia ceará",
    "alevinos reservatório nordeste"
]
# Mesmo documento positivo/negativo
```

**Técnica 2: Query expansion**
```python
# Adicionar termos relacionados
original = "microcrédito pescadores"
expandida = [
    "microcrédito pescadores artesanais",
    "crédito pescadores calçoene",
    "financiamento pesca artesanal"
]
```

**Técnica 3: Back-translation**
```python
# PT → EN → PT (gera variações)
original = "tilápia açude ema"
en = "tilapia reservoir ema"
back_pt = "tilápia reservatório ema"  # Variação
```

**Ganho estimado:** 3,900 → 15,000+ triplas

---

### Fonte 3: Dados Externos (Opcional)

**Se disponível:**
- Logs de busca reais de portais gov.br
- Datasets de PT-BR (ASSIN, HAREM, etc.)
- Notícias anotadas com relevância

**Fontes públicas:**
- MS MARCO Portuguese (se existir)
- mMARCO (multilingual)
- Adaptação de datasets em inglês

---

## Implementação Técnica

### Modelo Base a Fine-Tunar

**Escolher o melhor da Issue #1:**
- Se BGE-M3 venceu → Fine-tunar BGE-M3
- Se Serafim venceu → Fine-tunar Serafim
- **Ou** testar ambos e comparar

### Framework Recomendado

```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

# 1. Carregar modelo base
model = SentenceTransformer('BAAI/bge-m3')  # Ou vencedor da Issue #1

# 2. Preparar dados
train_examples = [
    InputExample(texts=[query, doc_pos, doc_neg])
    for query, doc_pos, doc_neg in triplas
]

train_dataloader = DataLoader(train_examples, batch_size=16, shuffle=True)

# 3. Definir loss
train_loss = losses.MultipleNegativesRankingLoss(model)

# 4. Fine-tuning
model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=3,
    warmup_steps=100,
    output_path='./models/bge-m3-govbr-finetuned'
)
```

### Hiperparâmetros Sugeridos

```python
learning_rate = 2e-5  # Baixo para não destruir pré-treino
batch_size = 16       # Depende de GPU (A100: 32-64, V100: 16-32)
epochs = 3-5          # Poucas épocas (evitar overfitting)
warmup_steps = 10% do total
weight_decay = 0.01
```

### Validação

```python
# Split de dados:
train_queries = 70% (180 queries)
val_queries = 15% (40 queries)
test_queries = 15% (39 queries)  # Mesmo test set da Issue #1

# Validação a cada época:
# - Calcular NDCG@10 no val set
# - Early stopping se não melhorar
```

---

## Timeline Detalhada

### Semana 1: Preparação (5 dias)

**Dia 1-2:**
- Analisar resultados da Issue #1
- Identificar fraquezas (jargão? geografia? consistência?)
- Decidir estratégia de fine-tuning

**Dia 3-4:**
- Gerar triplas (query, pos, neg) dos resultados da Issue #1
- Aplicar data augmentation
- Criar splits (train/val/test)

**Dia 5:**
- Setup de ambiente (GPU, bibliotecas)
- Testes iniciais com subset pequeno
- Validar pipeline de fine-tuning

**Entregável:** Dataset de fine-tuning pronto (15k+ triplas)

---

### Semana 2: Fine-Tuning e Experimentos (5 dias)

**Dia 6-7:**
- Fine-tuning do modelo vencedor da Issue #1
- Monitorar loss e NDCG@10 no val set
- Ajustar hiperparâmetros se necessário

**Dia 8:**
- Experimento com hard negative mining
- Comparar com fine-tuning baseline

**Dia 9:**
- Se multilíngue: Testar domain-specific pre-training
- Se PT-BR: Testar multi-task learning

**Dia 10:**
- Selecionar melhor configuração
- Fine-tuning final com todos os dados

**Entregável:** Modelo fine-tunado salvo

---

### Semana 3: Avaliação e Comparação (5 dias)

**Dia 11-12:**
- Rodar evaluate_metrics.py com modelo fine-tunado
- Calcular NDCG@10, MAP, MRR, Consistency
- Comparar com baseline (Issue #1)

**Dia 13:**
- Análise qualitativa (casos específicos)
- Onde melhorou? Onde piorou?
- Vale a pena o fine-tuning?

**Dia 14:**
- Escrever relatório de fine-tuning
- Atualizar RESEARCH_EMBEDDING_MODELS.md

**Dia 15:**
- Apresentação de resultados
- Decisão: Deploy do fine-tuned ou continuar com baseline?

**Entregável:** Relatório + Modelo final

---

## Métricas de Sucesso

### Mínimo Aceitável

```
NDCG@10 geral:     Baseline + 5%
NDCG@10 jargão BR: > 0.80
Consistency@10:    > 0.75
```

### Target Ideal

```
NDCG@10 geral:     Baseline + 10%
NDCG@10 jargão BR: > 0.85
Consistency@10:    > 0.80
Gap jargão-geral:  < 5%
```

### Comparação

**Tabela de decisão:**

| Métrica | Baseline | Fine-tuned | Melhoria | Status |
|---------|----------|------------|----------|--------|
| NDCG@10 geral | 0.82 | 0.88 | +7.3% | ✅ |
| NDCG@10 jargão | 0.76 | 0.84 | +10.5% | ✅ |
| Consistency@10 | 0.68 | 0.79 | +16.2% | ✅ |
| Throughput (docs/s) | 145 | 145 | 0% | ✅ |

**Decisão:** Deploy do modelo fine-tunado

---

## Riscos e Mitigações

### Risco 1: Overfitting

**Sintoma:** NDCG@10 val > 0.90, mas test < 0.80

**Mitigação:**
- Usar regularização (dropout, weight decay)
- Poucas épocas (3-5)
- Data augmentation
- Early stopping

---

### Risco 2: Catastrophic Forgetting

**Sintoma:** NDCG melhora em jargão mas piora no geral

**Mitigação:**
- Learning rate baixo (2e-5)
- Replay: Incluir dados gerais no fine-tuning
- Multi-task learning

---

### Risco 3: Dados insuficientes

**Sintoma:** Performance não melhora significativamente

**Mitigação:**
- Data augmentation agressivo
- Usar datasets externos
- Few-shot learning com prompts

---

### Risco 4: Custo computacional

**Sintoma:** Fine-tuning leva muito tempo/recursos

**Mitigação:**
- LoRA (Low-Rank Adaptation) - fine-tuning eficiente
- Usar modelo menor (E5-small, BERTimbau)
- Treino distribuído se disponível

---

## Custos Estimados

### Computação

**GPU necessária:** A100 (40GB) ou V100 (32GB)

**Tempo de treino:**
- Modelo 500M parâmetros: ~3-6h (3 epochs)
- Modelo 900M parâmetros: ~6-12h (3 epochs)

**Custo (se cloud):**
- A100 (~$2/h): $6-24
- V100 (~$1/h): $6-12

**Alternativa:** Usar GPU local (se disponível)

---

### Humano

**Tempo estimado:** 60-80 horas
- 20h preparação de dados
- 20h experimentação
- 20h avaliação e análise
- 10-20h documentação

---

## Referências Técnicas

### Papers Fundamentais

1. **Karpukhin et al. (2020)**
   "Dense Passage Retrieval for Open-Domain Question Answering"
   - Base do contrastive learning para retrieval

2. **Reimers & Gurevych (2019)**
   "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks"
   - Framework de fine-tuning usado

3. **Gao et al. (2021)**
   "SimCSE: Simple Contrastive Learning of Sentence Embeddings"
   - Contrastive learning simplificado

4. **Xiong et al. (2021)**
   "Approximate Nearest Neighbor Negative Contrastive Learning"
   - Hard negative mining

5. **Gururangan et al. (2020)**
   "Don't Stop Pretraining: Adapt Language Models to Domains and Tasks"
   - Domain-specific pre-training

### Tutoriais e Código

- Sentence-Transformers Docs: https://www.sbert.net/docs/training/overview.html
- HuggingFace Training Guide
- BGE Fine-tuning Example (FlagEmbedding repo)

---

## Checklist de Execução

Quando iniciar Issue #2:

### Preparação
- [ ] Analisar resultados Issue #1
- [ ] Identificar gaps (jargão? geografia?)
- [ ] Decidir estratégia (contrastive? hard negatives? domain-specific?)
- [ ] Gerar triplas de treino
- [ ] Aplicar data augmentation
- [ ] Criar splits train/val/test

### Fine-Tuning
- [ ] Setup ambiente GPU
- [ ] Testar pipeline com subset
- [ ] Fine-tuning com validação
- [ ] Experimentos com variações
- [ ] Selecionar melhor configuração

### Avaliação
- [ ] Rodar evaluate_metrics.py
- [ ] Calcular todas as métricas
- [ ] Comparar com baseline
- [ ] Análise qualitativa
- [ ] Decidir deploy

### Documentação
- [ ] Escrever relatório
- [ ] Atualizar RESEARCH_EMBEDDING_MODELS.md
- [ ] Documentar código
- [ ] Preparar apresentação

---

**Status:** 📋 Planejamento completo  
**Próximo passo:** Aguardar Issue #1 e decidir se Issue #2 é necessária  
**Última atualização:** 2026-04-02
