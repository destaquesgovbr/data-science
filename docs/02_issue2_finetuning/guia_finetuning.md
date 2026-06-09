# Guia de Fine-tuning de Modelos de Embedding

## Issue #2: Fine-tuning vs Transfer Learning vs Zero-shot

Este documento explica o processo completo de fine-tuning de modelos de embedding para o domínio de notícias governamentais brasileiras.

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Processo Completo](#processo-completo)
3. [Scripts Criados](#scripts-criados)
4. [Como Executar](#como-executar)
5. [Interpretação de Resultados](#interpretação-de-resultados)
6. [Decisões e Trade-offs](#decisões-e-trade-offs)

---

## Visão Geral

### Objetivo

Avaliar SE e QUANTO fine-tuning melhora a performance de modelos de embedding para nosso domínio específico (notícias gov.br).

### Hipótese

Fine-tuning com dataset governamental brasileiro pode melhorar performance em retrieval semântico, especialmente para:
- Jargões governamentais: LGPD, PPA, LOA, INPA, MCTI
- Siglas específicas: SUS, AGU, BNDES
- Contexto brasileiro vs português europeu

### Dataset

- **Origem:** 2.591 anotações manuais (Issue #1)
- **Triplas extraídas:** 2.367 (query, positive, negative)
- **Splits:**
  - Train: 1.668 (70%)
  - Validation: 329 (15%)
  - Test: 370 (15%)
- **Few-shot subset:** 500 triplas (para teste rápido)

---

## Processo Completo

### Fase 1: Preparação de Dataset ✅ (Concluída)

**Script:** `generate_triplets.py`

**O que faz:**
1. Carrega ground truth (2.591 anotações)
2. Extrai triplas: (query, doc_positivo, doc_negativo)
   - Positivo: relevância ≥ 2 (relevante + muito relevante)
   - Negativo: relevância = 0 (irrelevante)
3. Cria splits estratificados por categoria
4. Gera subset few-shot (500 triplas)

**Output:**
```
data/finetuning/
├── train.csv              (1.668 triplas)
├── train_fewshot.csv      (500 triplas)
├── val.csv                (329 triplas)
└── test.csv               (370 triplas)
```

---

### Fase 2: Fine-tuning (Em andamento)

**Script:** `finetune_model.py`

**O que faz:**

#### 2.1 Carrega Modelo Base

```python
model = SentenceTransformer('BAAI/bge-m3')
```

Modelo pré-treinado que já sabe português geral, mas não conhece jargões governamentais.

#### 2.2 Carrega Triplas de Treino

```python
train_examples = [
    InputExample(texts=[query, positive, negative]),
    ...
]
```

Cada tripla ensina ao modelo:
- Query e positive devem ter embeddings próximos
- Query e negative devem ter embeddings distantes

#### 2.3 Define Loss Function

```python
train_loss = MultipleNegativesRankingLoss(model)
```

**Como funciona:**

```
Loss = max(0, margin + sim(query, negative) - sim(query, positive))
```

- Se `sim(query, positive) > sim(query, negative)`: Loss baixo ✅
- Se negative está próximo de query: Loss alto ❌ → ajusta pesos

**Intuição:**
- O modelo gera embeddings
- Calcula similaridade (cosseno)
- Se errou (negative próximo), backpropagation ajusta pesos
- Repete por todas triplas, múltiplas épocas

#### 2.4 Treinamento

```python
model.fit(
    train_objectives=[(dataloader, train_loss)],
    epochs=2,
    warmup_steps=100,
    evaluator=val_evaluator,
    evaluation_steps=50
)
```

**O que acontece:**

1. **Época 1:**
   - Passa por todas 500 (fewshot) ou 1.668 (full) triplas
   - A cada 50 steps: avalia no validation set
   - Salva checkpoint se melhorou

2. **Época 2:**
   - Repete processo
   - Modelo já conhece melhor o domínio
   - Ajustes mais finos

3. **Early stopping:**
   - Se validation não melhorar, para
   - Evita overfitting

**Tempo estimado:**
- Few-shot (500 triplas, 2 épocas): 1-2 horas (GPU T4)
- Full (1.668 triplas, 3 épocas): 4-8 horas (GPU A100)

#### 2.5 O Que Muda no Modelo?

**Antes (zero-shot):**
```
"INPA" → embedding genérico (nunca viu essa sigla)
"bambu" → embedding genérico
```

**Depois (fine-tuned):**
```
"INPA" → embedding próximo de "Instituto Nacional de Pesquisas"
"bambu" → embedding próximo de "sustentabilidade", "pesquisa ambiental"
"projeto Natal com Bambu" → embedding muito próximo do doc correto
```

**Camadas afetadas:**
- Últimas camadas do transformer (mais específicas do domínio)
- Pooling layer (como agregar tokens)
- Camadas base mantêm conhecimento geral (gramática, sintaxe)

---

### Fase 3: Avaliação

**Script:** `evaluate_finetuned.py`

**O que faz:**

#### 3.1 Carrega Modelo Fine-tuned

```python
model_ft = SentenceTransformer('models/bge-m3-fewshot')
```

#### 3.2 Gera Embeddings do Test Set

```python
# Encode corpus (250 documentos)
corpus_embeddings = model_ft.encode(corpus)

# Para cada query do test set
for query in test_queries:
    query_emb = model_ft.encode([query])
    
    # Calcula similaridade com todos docs
    similarities = cosine_similarity(query_emb, corpus_embeddings)
    
    # Ranking
    ranking = argsort(similarities, descending=True)
```

#### 3.3 Calcula Métricas

Compara ranking do modelo com ground truth:

**NDCG@10:**
```
DCG = Σ (relevância_i / log2(posição_i + 1))
NDCG = DCG / IDCG
```

**MAP, MRR, Recall@10:** (mesmo processo Issue #1)

#### 3.4 Compara com Baseline

Repete processo com `BAAI/bge-m3` zero-shot e compara:

```
Metric       Baseline    Fine-tuned    Δ Abs      Δ %
ndcg@10      0.9673      0.9812       +0.0139    +1.44%  ✅
map          0.9598      0.9720       +0.0122    +1.27%  ✅
```

---

## Scripts Criados

### 1. `finetune_model.py`

**Propósito:** Treinar modelo de embedding com triplas.

**Parâmetros principais:**
- `--dataset`: `fewshot` (500) ou `full` (1668)
- `--epochs`: Número de épocas (default: 2)
- `--batch-size`: Tamanho do batch (default: 16)
- `--learning-rate`: Taxa de aprendizado (default: 2e-5)
- `--output`: Onde salvar modelo

**Exemplo:**
```bash
python finetune_model.py \
    --dataset fewshot \
    --epochs 2 \
    --output models/bge-m3-fewshot
```

**Output:**
- Modelo fine-tuned em `models/bge-m3-fewshot/`
- `training_config.json` com configuração
- Checkpoints durante treino

---

### 2. `evaluate_finetuned.py`

**Propósito:** Avaliar modelo fine-tuned e comparar com baseline.

**Parâmetros principais:**
- `--model`: Path do modelo fine-tuned
- `--compare-baseline`: Modelo baseline (ex: `BAAI/bge-m3`)
- `--output`: Arquivo JSON com resultados

**Exemplo:**
```bash
python evaluate_finetuned.py \
    --model models/bge-m3-fewshot \
    --compare-baseline BAAI/bge-m3 \
    --output results/fewshot_results.json
```

**Output:**
```json
{
  "model": "models/bge-m3-fewshot",
  "baseline": "BAAI/bge-m3",
  "metrics_finetuned": {
    "ndcg@10": {"mean": 0.9812, "std": 0.0234},
    "map": {"mean": 0.9720, "std": 0.0198}
  },
  "metrics_baseline": {
    "ndcg@10": {"mean": 0.9673, "std": 0.0251}
  }
}
```

---

### 3. `run_finetuning_experiment.sh`

**Propósito:** Executar pipeline completo (treino + avaliação).

**Exemplo:**
```bash
./run_finetuning_experiment.sh fewshot
```

**Etapas:**
1. Fine-tuning com dataset especificado
2. Avaliação no test set
3. Comparação com baseline
4. Salva resultados

---

## Como Executar

### Pré-requisitos

```bash
# GPU recomendada (mas funciona em CPU)
# Memória: 16GB RAM, 8GB VRAM

# Instalar dependências
pip install sentence-transformers torch scikit-learn pandas tqdm
```

### Experimento Quick (Few-shot)

**Objetivo:** Validar pipeline rapidamente (1-2 horas)

```bash
# Opção 1: Script individual
python source/embeddings/scripts/finetune_model.py \
    --dataset fewshot \
    --epochs 2 \
    --output models/bge-m3-fewshot-test

# Opção 2: Pipeline completo
cd /l/disk0/lpmoraes/environments/data-science
chmod +x source/embeddings/scripts/run_finetuning_experiment.sh
./source/embeddings/scripts/run_finetuning_experiment.sh fewshot
```

**Esperado:**
- Treino: ~1-2 horas
- Modelo salvo em `models/bge-m3-fewshot-<timestamp>/`
- Resultados em `results/finetuning/fewshot_<timestamp>_results.json`

---

### Experimento Full (1.668 triplas)

**Quando executar:** SE few-shot mostrar ganhos > 2%

```bash
./source/embeddings/scripts/run_finetuning_experiment.sh full
```

**Esperado:**
- Treino: ~4-8 horas
- Maior adaptação ao domínio
- Risco de overfitting se dataset for pequeno

---

## Interpretação de Resultados

### Cenário 1: Ganho Significativo (+2-5%)

```
Metric       Baseline    Fine-tuned    Δ Abs      Δ %
ndcg@10      0.9673      0.9873       +0.0200    +2.07%  ✅✅
map          0.9598      0.9798       +0.0200    +2.08%  ✅✅
```

**Interpretação:**
- ✅ Fine-tuning funcionou!
- ✅ Modelo aprendeu jargões específicos
- ✅ Vale investir em mais dados

**Próximos passos:**
1. Escalar para full dataset (1.668 triplas)
2. Considerar LoRA para eficiência
3. Expandir dataset (4k-10k triplas) via semi-automático

---

### Cenário 2: Ganho Modesto (+0.5-2%)

```
Metric       Baseline    Fine-tuned    Δ Abs      Δ %
ndcg@10      0.9673      0.9732       +0.0059    +0.61%  ➖
map          0.9598      0.9648       +0.0050    +0.52%  ➖
```

**Interpretação:**
- ➖ Ganho existe mas pequeno
- ➖ ROI questionável (custo > benefício?)
- ➖ Baseline já muito bom (96.7%)

**Próximos passos:**
1. Análise qualitativa: onde melhorou?
2. Testar em modelos mais fracos (BERTimbau)
3. Considerar hybrid search (BM25 + embeddings)

---

### Cenário 3: Sem Ganho ou Piora (0% ou negativo)

```
Metric       Baseline    Fine-tuned    Δ Abs      Δ %
ndcg@10      0.9673      0.9621       -0.0052    -0.54%  ❌
map          0.9598      0.9542       -0.0056    -0.58%  ❌
```

**Interpretação:**
- ❌ Overfitting no dataset pequeno
- ❌ Modelo perdeu conhecimento geral
- ❌ Fine-tuning não vale a pena

**Próximos passos:**
1. Zero-shot continua sendo melhor
2. Focar em Issue #3 (hybrid search)
3. Considerar RAG ao invés de fine-tuning

---

## Decisões e Trade-offs

### Por Que Few-shot Primeiro?

**Vantagens:**
- ✅ Rápido (1-2h vs 4-8h)
- ✅ Valida pipeline
- ✅ Baixo custo
- ✅ Decisão rápida: vale escalar?

**Desvantagens:**
- ❌ Ganhos limitados
- ❌ Pode não capturar complexidade total

**Decisão:** Sempre começar com few-shot para validar SE vale continuar.

---

### Learning Rate (2e-5)

**Por que baixo?**
- Modelo já é pré-treinado e bom
- Queremos ajuste fino, não re-treino completo
- Evita "esquecer" conhecimento geral

**Alternativas:**
- 5e-5: Se modelo base é fraco (BERTimbau)
- 1e-5: Mais conservador ainda

---

### Batch Size (16)

**Trade-off:**
- Maior (32): Mais rápido, mais VRAM
- Menor (8): Mais lento, menos VRAM, gradientes mais ruidosos

**Escolha:** 16 é bom compromisso para GPU T4/V100.

---

### Épocas (2 few-shot, 3 full)

**Risco:**
- Muitas épocas: Overfitting (especialmente com dataset pequeno)
- Poucas épocas: Underfitting (não aprende)

**Solução:** Early stopping + validation set.

---

### Warmup Steps

**O que é:**
- Primeiros N steps com learning rate crescendo gradualmente
- Evita grandes mudanças iniciais que desestabilizam modelo

**Valores:**
- Few-shot: 50-100 steps
- Full: 100-200 steps

---

## Próximos Passos (Após Resultados)

### Se ganhos > 2%:

1. **Escalar dataset**
   - Gerar 10k-20k triplas via semi-automático
   - LLM-assisted (GPT-4 gera queries sintéticas)
   - Validação humana

2. **Testar LoRA**
   - Treina apenas 1-5% dos parâmetros
   - 10x mais rápido
   - Adapters pequenos (~10MB)

3. **Fine-tunar modelos fracos**
   - BERTimbau: 68.2% → potencial de 80%+
   - Maior margem de melhoria

### Se ganhos < 2%:

1. **Hybrid Search (Issue #3)**
   - Combinar BM25 (lexical) + embeddings (semantic)
   - Reranking strategies

2. **RAG (Issue #5)**
   - Não treina modelo
   - Usa embeddings zero-shot para retrieval
   - LLM gera resposta baseado em contexto

3. **Análise qualitativa**
   - Onde fine-tuning ajudou?
   - Tipos de query que se beneficiam
   - Documentar padrões

---

## Referências

### Papers

1. **Sentence-BERT** (Reimers & Gurevych, 2019)
   - https://arxiv.org/abs/1908.10084
   - Base do sentence-transformers

2. **BGE M3-Embedding** (BAAI, 2024)
   - https://arxiv.org/abs/2402.03216
   - Modelo que usamos como base

3. **Multiple Negatives Ranking Loss**
   - Henderson et al. (2017) - Efficient Natural Language Response Suggestion
   - Loss function que usamos

### Tutoriais

- [Sentence-Transformers Training](https://www.sbert.net/docs/training/overview.html)
- [Multiple Negatives Ranking Loss](https://www.sbert.net/examples/training/mnrl/README.html)

---

**Última atualização:** 2026-04-14  
**Responsável:** Luis Felipe de Moraes
