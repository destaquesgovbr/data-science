# Scripts de Avaliação de Embeddings

Scripts para avaliação completa de modelos de embedding para notícias governamentais brasileiras.

## 📋 Visão Geral

Pipeline completo de avaliação:

```
1. setup_models.py          → Valida os 8 modelos
2. generate_embeddings.py   → Gera embeddings do corpus (250 docs)
3. semantic_search.py       → Executa busca semântica (259 queries expandidas)
4. evaluate_consistency.py  → Avalia consistência entre variantes
5. create_ground_truth.py   → Cria anotações de relevância
6. evaluate_metrics.py      → Calcula NDCG, MAP, MRR
7. benchmark_performance.py → Mede throughput, latência, memória
```

**Nota:** As 259 queries são expandidas de 85 documentos âncora × ~3 variantes cada.

## 🚀 Quick Start

### Opção 1: Pipeline Automático (Recomendado)

```bash
# Executar avaliação completa
python run_evaluation.py

# Avaliar apenas modelos específicos
python run_evaluation.py --models bge-m3 serafim bertimbau

# Pular etapas já concluídas
python run_evaluation.py --skip-setup --skip-embeddings
```

### Opção 2: Execução Manual (Passo a Passo)

```bash
# 1. Setup e validação
python setup_models.py

# 2. Gerar embeddings
python generate_embeddings.py

# 3. Busca semântica
python semantic_search.py

# 4. Criar ground truth
python create_ground_truth.py --mode anchor-only

# 5. Avaliar métricas (requer ground truth)
python evaluate_metrics.py

# 6. Benchmark de performance
python benchmark_performance.py
```

---

## 📚 Detalhes dos Scripts

### 1. `setup_models.py` - Setup e Validação

Baixa e valida os 8 modelos definidos no ROTEIRO.

**Uso:**
```bash
# Testar todos os modelos
python setup_models.py

# Testar modelos específicos
python setup_models.py --models bge-m3 serafim

# Especificar device
python setup_models.py --device cuda
```

**O que faz:**
- ✅ Baixa modelos do HuggingFace
- ✅ Valida dimensões dos embeddings
- ✅ Testa compreensão semântica PT-BR
- ✅ Mede tempo de carregamento

**Output:**
- `results/models_setup.json` - Status de cada modelo

---

### 2. `generate_embeddings.py` - Geração de Embeddings

Gera embeddings para todos os 250 documentos do corpus.

**Uso:**
```bash
# Gerar embeddings para todos os modelos
python generate_embeddings.py

# Apenas alguns modelos
python generate_embeddings.py --models bge-m3 serafim

# Ajustar batch size
python generate_embeddings.py --batch-size 64
```

**O que faz:**
- ✅ Carrega corpus (250 docs)
- ✅ Gera embeddings normalizados
- ✅ Salva como .npy (eficiente)
- ✅ Mede throughput

**Output:**
```
results/embeddings/
├── bge-m3_corpus.npy           # Embeddings
├── bge-m3_doc_ids.json         # Mapeamento doc_id
├── bge-m3_stats.json           # Estatísticas
├── serafim_corpus.npy
├── ...
└── generation_summary.json     # Resumo geral
```

**⏱️ Tempo estimado:** ~5-10 min por modelo (GPU)

---

### 3. `semantic_search.py` - Busca Semântica

Executa busca por similaridade para todas as queries.

**Queries expandidas:** Usa TODAS as variantes (259 queries de 85 documentos âncora).

**Uso:**
```bash
# Buscar com todos os modelos
python semantic_search.py

# Modelos específicos
python semantic_search.py --models bge-m3

# Ajustar top-K
python semantic_search.py --top-k 50
```

**O que faz:**
- ✅ Carrega embeddings do corpus
- ✅ Gera embeddings das queries
- ✅ Calcula similaridade cosseno
- ✅ Rankeia top-K documentos

**Output:**
```
results/search_results/
├── bge-m3_results.json         # Resultados rankeados
├── serafim_results.json
└── ...
```

**Formato do resultado:**
```json
{
  "q001": {
    "query_text": "tilápia açude ema",
    "results": [
      {"doc_id": "doc_01_08", "score": 0.876, "rank": 1},
      {"doc_id": "doc_01_02", "score": 0.654, "rank": 2},
      ...
    ]
  }
}
```

---

### 4. `evaluate_consistency.py` - Consistência Entre Variantes

Avalia quão consistentemente um modelo retorna o documento âncora para diferentes formulações da mesma query.

**⚠️ Requer:** Resultados de busca (semantic_search.py)

**Uso:**
```bash
# Avaliar todos os modelos
python evaluate_consistency.py

# Modelos específicos
python evaluate_consistency.py --models bge-m3 serafim

# Ajustar K
python evaluate_consistency.py --k 20
```

**Métrica Chave: Consistency@K**

Para cada base query (ex: q001):
- Verifica se documento âncora está no top-K da variante 1
- Verifica se documento âncora está no top-K da variante 2
- Verifica se documento âncora está no top-K da variante 3
- **Consistency@K** = (variantes com âncora no top-K) / (total variantes)

**Interpretação:**
```
Consistência alta (>0.8)  → Modelo robusto a reformulações
Consistência média (0.5-0.8) → Sensível a palavras exatas
Consistência baixa (<0.5) → Frágil, depende muito da formulação
```

**Exemplo:**
```
Query q001 (3 variantes):
  v1: "tilápia açude ema"
  v2: "alevinos dnocs iracema"
  v3: "piscicultura alevinos tilápia Iracema"

Modelo A:
  v1: doc_01_08 em posição 1  ✓
  v2: doc_01_08 em posição 3  ✓
  v3: doc_01_08 em posição 1  ✓
  Consistency@10 = 3/3 = 1.0  (perfeito!)

Modelo B:
  v1: doc_01_08 em posição 2  ✓
  v2: doc_01_08 NÃO aparece   ✗
  v3: doc_01_08 em posição 15 ✗
  Consistency@10 = 1/3 = 0.33 (frágil)
```

**Output:**
```
results/consistency/
├── consistency_results.json  # Resultados detalhados
└── consistency_summary.csv   # Ranking por modelo
```

**⏱️ Tempo estimado:** ~1-2 min

**💡 Por que isso importa:**

Em produção, usuários formulam queries de formas diferentes:
- Público geral: "tilápia açude"
- Profissional: "alevinos dnocs"
- Técnico: "piscicultura tilápia"

Um bom modelo deve retornar **resultados similares** independente da formulação!

---

### 5. `create_ground_truth.py` - Anotação de Relevância

Cria ground truth para avaliação de métricas.

**Modos de operação:**

#### Modo 1: Apenas Âncoras (Automático) ⚡
```bash
python create_ground_truth.py --mode anchor-only
```
- Marca apenas documento âncora como relevante (score=3)
- Rápido, bom ponto de partida
- **Limitação:** Não captura outros docs relevantes

#### Modo 2: Interativo (Semi-automático) 🤝
```bash
# Anotar top-20 de um modelo
python create_ground_truth.py --mode interactive --model bge-m3 --top-k 20
```
- Mostra query + documento
- Usuário avalia relevância (0-3)
- Salva conforme anota (pode interromper com Ctrl+C)

#### Modo 3: Mesclar com Existente 🔄
```bash
python create_ground_truth.py --mode interactive --merge
```

**Escala de Relevância:**
```
0 = Irrelevante (não responde à query)
1 = Pouco relevante (menciona tema)
2 = Relevante (responde parcialmente)
3 = Muito relevante (responde completamente)
```

**Output:**
```
data/annotations/
└── ground_truth.json
```

**Formato:**
```json
{
  "q001": {
    "doc_01_08": 3,
    "doc_01_02": 2,
    "doc_03_04": 1
  }
}
```

**⏱️ Tempo estimado:**
- Anchor-only: ~1 minuto
- Interactive (top-20, 85 queries): ~20-25 horas

**💡 Estratégia Recomendada:**
1. Criar anchor-only primeiro
2. Anotar interativamente top-10 de 20-30 queries críticas
3. Usar para comparação inicial de modelos

---

### 6. `evaluate_metrics.py` - Cálculo de Métricas

Calcula métricas de retrieval (NDCG, MAP, MRR, Recall).

**⚠️ Requer:** Ground truth criado

**Uso:**
```bash
# Avaliar todos os modelos
python evaluate_metrics.py

# Modelos específicos
python evaluate_metrics.py --models bge-m3 serafim

# Valores de K customizados
python evaluate_metrics.py --k 5 10 20 50
```

**Métricas Calculadas:**

- **NDCG@K** (Normalized Discounted Cumulative Gain)
  - Considera posição do resultado
  - Aceita relevância graduada (0-3)
  - **Meta:** >0.85

- **MAP** (Mean Average Precision)
  - Precisão média em todos os recall points
  - **Meta:** >0.80

- **MRR** (Mean Reciprocal Rank)
  - Posição do primeiro resultado relevante
  - **Meta:** >0.85

- **Recall@K**
  - Proporção de docs relevantes no top-K
  - **Meta:** >0.75

**Output:**
```
results/metrics/
├── evaluation_results.json     # Resultados completos
└── metrics_summary.csv         # Resumo em tabela
```

**Análises Incluídas:**
- ✅ Métricas gerais (média, mediana, desvio)
- ✅ Métricas por categoria (Saúde, Educação, etc)
- ✅ Métricas por tipo de query (jargão, geral, docs longos)
- ✅ Comparação estatística (teste t pareado)

**Output no Terminal:**
```
📊 RANKING DOS MODELOS (por NDCG@10)
================================================
   model              ndcg@10    map     mrr
   bge-m3             0.8762   0.8234  0.8901
   serafim            0.8654   0.8156  0.8823
   ...
```

---

### 7. `benchmark_performance.py` - Performance

Mede throughput, latência e uso de memória.

**Uso:**
```bash
# Benchmark de todos os modelos
python benchmark_performance.py

# Modelos específicos
python benchmark_performance.py --models bge-m3 serafim

# CPU vs GPU
python benchmark_performance.py --device cpu
```

**Métricas Medidas:**

1. **Throughput** (docs/segundo)
   - Batch encoding (batch_size=32)
   - 3 runs para estabilidade
   - **Meta:** >100 docs/s

2. **Latência** (ms por documento)
   - Encoding individual
   - Estatísticas: P50, P95, P99
   - **Meta P99:** <500ms

3. **Memória** (MB)
   - CPU RAM
   - GPU VRAM
   - Medido antes/depois do loading

4. **Batch Size Scaling**
   - Testa 1, 4, 8, 16, 32, 64
   - Identifica batch size ótimo

**Output:**
```
results/benchmarks/
└── benchmark_results.json
```

**Output no Terminal:**
```
📊 RESUMO DE PERFORMANCE
================================================
Modelo                    Throughput  Latência P99  Mem GPU
-------------------------  ----------  ------------  -------
bge-m3                      145.2/s       320.5ms   2340MB
serafim                     98.7/s        450.3ms   3560MB
...
```

---

### 8. `run_evaluation.py` - Pipeline Completo

Orquestra todo o workflow de avaliação.

**Uso Básico:**
```bash
# Executar tudo
python run_evaluation.py

# Apenas modelos específicos
python run_evaluation.py --models bge-m3 serafim

# Device específico
python run_evaluation.py --device cuda
```

**Controle Fino:**
```bash
# Pular setup (já feito antes)
python run_evaluation.py --skip-setup

# Pular embeddings (já gerados)
python run_evaluation.py --skip-embeddings

# Apenas busca e métricas
python run_evaluation.py --skip-setup --skip-embeddings --skip-bench

# Sem benchmarks (foco em retrieval)
python run_evaluation.py --skip-bench

# Sem métricas (não tem ground truth ainda)
python run_evaluation.py --skip-metrics
```

**O que faz:**
1. ✅ Verifica pré-requisitos (corpus, queries)
2. ✅ Executa cada script em ordem
3. ✅ Captura erros e continua quando possível
4. ✅ Gera resumo final
5. ✅ Sugere próximos passos

**Output:**
```
🏁 PIPELINE COMPLETO!
================================================
Tempo total: 45.3 minutos
Passos executados: Setup, Embeddings, Search, Metrics, Benchmark

📊 PRÓXIMOS PASSOS
================================================
✅ Métricas disponíveis em: results/metrics/metrics_summary.csv
✅ Benchmarks disponíveis em: results/benchmarks/benchmark_results.json
```

---

## 📊 Estrutura de Resultados

Após execução completa:

```
results/
├── embeddings/
│   ├── bge-m3_corpus.npy           # Embeddings (1024 dims × 250 docs)
│   ├── bge-m3_doc_ids.json
│   ├── bge-m3_stats.json
│   └── generation_summary.json
│
├── search_results/
│   ├── bge-m3_results.json         # Top-100 por query
│   ├── serafim_results.json
│   └── ...
│
├── metrics/
│   ├── evaluation_results.json     # Métricas detalhadas
│   └── metrics_summary.csv         # Tabela resumo
│
└── benchmarks/
    └── benchmark_results.json      # Performance de cada modelo
```

---

## 🎯 Workflow Recomendado

### Fase 1: Setup Inicial (1 dia)

```bash
# 1. Validar modelos
python setup_models.py

# 2. Gerar embeddings (mais demorado)
python generate_embeddings.py
```

**✅ Checkpoint:** Embeddings salvos em `results/embeddings/`

---

### Fase 2: Busca e Ground Truth (2-3 dias)

```bash
# 3. Executar buscas
python semantic_search.py

# 4. Criar ground truth base
python create_ground_truth.py --mode anchor-only

# 5. Anotar interativamente (subset crítico)
# Sugestão: Top-10 de 20-30 queries
python create_ground_truth.py --mode interactive --model bge-m3 --top-k 10 --merge
```

**✅ Checkpoint:** Ground truth em `data/annotations/ground_truth.json`

---

### Fase 3: Avaliação Final (1 dia)

```bash
# 6. Calcular métricas
python evaluate_metrics.py

# 7. Benchmark de performance
python benchmark_performance.py
```

**✅ Resultado:** Modelo vencedor identificado!

---

## 🔧 Troubleshooting

### Erro: "CUDA out of memory"

```bash
# Reduzir batch size
python generate_embeddings.py --batch-size 16

# Ou usar CPU
python generate_embeddings.py --device cpu
```

### Erro: "Ground truth not found"

```bash
# Criar ground truth primeiro
python create_ground_truth.py --mode anchor-only
```

### Erro: "No search results found"

```bash
# Executar busca primeiro
python semantic_search.py
```

### Queries não encontradas

Certifique-se de que `data/query_template_85.json` tem queries preenchidas:
- Campo `query_text` OU
- Campo `recommended_query`

---

## 📝 Dependências

```bash
pip install sentence-transformers
pip install torch torchvision torchaudio  # GPU support
pip install numpy pandas scikit-learn scipy
pip install tqdm psutil
```

---

## 🎓 Referências

Ver `ROTEIRO_TESTES_EMBEDDINGS.md` para:
- Detalhes das métricas
- Definição dos modelos
- Critérios de decisão
- Papers fundamentais

---

## 🆘 Ajuda

Para dúvidas ou problemas:

1. Verificar logs de erro
2. Consultar `ROTEIRO_TESTES_EMBEDDINGS.md`
3. Abrir issue no repositório

---

**Última atualização:** 2026-03-31
