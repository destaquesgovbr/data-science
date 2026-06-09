# Comparativo de Modelos de Embedding PT-BR

> Pesquisa para avaliar modelos de embedding para português brasileiro no contexto de notícias governamentais.

**Issue**: [#1 - Comparativo de Modelos de Embedding PT-BR](https://github.com/destaquesgovbr/data-science/issues/1)
**Status**: 🚧 In Progress
**Responsável**: Luis Felipe de Moraes
**Período**: 3 semanas

---

## 🎯 Objetivo

Explorar e comparar modelos de embedding para português brasileiro, avaliando:
- Qualidade de retrieval semântico
- Aplicabilidade a notícias governamentais
- Trade-offs de performance, dimensionalidade e contexto

**Hipótese Central:** Modelos específicos para português (BERTimbau, Serafim) podem superar modelos multilinguais (BGE-M3, E5) em tarefas de retrieval em notícias governamentais brasileiras.

---

## 📂 Estrutura do Projeto

```
embeddings/
├── README.md                          # Este arquivo
├── notebooks/
│   └── embedding_comparison.ipynb     # Notebook principal de análise
├── scripts/
│   ├── load_models.py                 # Carregar todos os modelos
│   ├── generate_embeddings.py         # Gerar embeddings em batch
│   ├── evaluate_metrics.py            # Calcular NDCG, MAP, MRR
│   └── benchmark_speed.py             # Benchmark de velocidade
├── data/
│   ├── queries/                       # Queries de teste
│   ├── documents/                     # Documentos amostrais
│   └── annotations/                   # Ground truth (relevância)
├── results/
│   ├── embeddings/                    # Embeddings salvos (.npy)
│   ├── metrics/                       # Resultados de métricas (.json/.csv)
│   └── visualizations/                # Gráficos e plots (.png)
└── docs/
    ├── RESEARCH_EMBEDDING_MODELS.md   # Documento final de pesquisa
    └── presentation_embedding_models.pdf  # Apresentação executiva
```

---

## 🤖 Modelos a Avaliar

### Multilinguais
- **BAAI/bge-m3** (1024d, 8192 tokens, 568M params)
- **intfloat/multilingual-e5-large** (1024d, 512 tokens, 560M)
- **Alibaba-NLP/gte-multilingual-base** (768d, 8192 tokens, 278M)
- **sentence-transformers/paraphrase-multilingual-mpnet** (768d, 128 tokens)

### PT-BR Específicos
- **BAAI/bge-large-pt** (1024d, 512 tokens, 560M)
- **BAAI/bge-small-pt** (384d, 512 tokens, 33M)
- **PORTULAN/serafim-900m-portuguese-pt** (1536d, 128 tokens, 900M)
- **PORTULAN/serafim-335m-portuguese-pt** (1024d, 128 tokens, 335M)
- **jinaai/jina-embeddings-v2-base-pt** (768d, 8192 tokens, 137M)
- **neuralmind/bert-base-portuguese-cased** (768d, 512 tokens, 110M)

### Candidatos Alternativos
- **PORTULAN/albertina-900m-portuguese-ptbr** (requer mean pooling)
- **rufimelo/Legal-BERTimbau** (domínio legal/governamental)

---

## 📊 Metodologia

### Métricas de Avaliação
- **NDCG@10** - Normalized Discounted Cumulative Gain
- **MAP** - Mean Average Precision
- **MRR** - Mean Reciprocal Rank
- **Recall@K** (K=5, 10, 20)

### Dataset de Teste
- **Corpus:** 250 documentos (25 por categoria, 10 categorias)
- **Queries:** 259 queries (85 base × ~3 variantes)
- **Anotações:** 2.591 pares query-documento anotados manualmente
- **Escala de relevância:** 0 (irrelevante) a 3 (muito relevante)

**Validação metodológica:** O corpus de 250 documentos foi validado como adequado para comparação de modelos através de análise empírica (99.6% de taxa de recuperação de documentos âncora com BGE-M3) e fundamentação teórica (Voorhees & Harman, 2005; Sanderson & Zobel, 2005). Consulte [docs/METODOLOGIA_METRICAS.md](docs/METODOLOGIA_METRICAS.md) para detalhes completos sobre representatividade do corpus e validade dos resultados.

### Dimensões de Análise
1. **Qualitativa**: Jargão gov, siglas, sinônimos, contexto temporal
2. **Quantitativa**: Métricas de retrieval (NDCG, MAP, MRR)
3. **Técnica**: Velocidade, dimensionalidade, facilidade de uso
4. **Domínio**: Compreensão de termos governamentais brasileiros

**Documentação metodológica:**
- [METODOLOGIA_QUERIES.md](docs/METODOLOGIA_QUERIES.md) - Justificativa das 85 queries de teste
- [METODOLOGIA_METRICAS.md](docs/METODOLOGIA_METRICAS.md) - Validação do corpus e escolha de métricas
- [ANALISE_CORPUS.md](docs/ANALISE_CORPUS.md) - Estatísticas do corpus de notícias

---

## 🚀 Quick Start

### Instalação

```bash
# Navegar para o diretório raiz do projeto
cd /l/disk0/lpmoraes/environments/data-science

# Instalar dependências (se necessário)
poetry install --with dev

# Ativar ambiente
poetry shell
```

### Executar Notebook

```bash
# Iniciar Jupyter
jupyter lab source/embeddings/notebooks/embedding_comparison.ipynb
```

### Gerar Embeddings

```bash
# Gerar embeddings para todos os modelos
python source/embeddings/scripts/generate_embeddings.py

# Avaliar métricas
python source/embeddings/scripts/evaluate_metrics.py

# Benchmark de velocidade
python source/embeddings/scripts/benchmark_speed.py
```

---

## 📚 Recursos e Referências

### Papers Principais

1. **Sentence-BERT** (Reimers & Gurevych, 2019)
   - https://arxiv.org/abs/1908.10084

2. **BGE M3-Embedding** (BAAI, 2024)
   - https://arxiv.org/abs/2402.03216

3. **Serafim PT Encoders** (Gomes et al., 2024)
   - https://arxiv.org/abs/2407.19527

4. **Albertina PT** (Rodrigues et al., 2023)
   - https://arxiv.org/abs/2305.06721

### Benchmarks
- **MTEB Leaderboard**: https://huggingface.co/spaces/mteb/leaderboard
- **ASSIN (PT-BR)**: https://sites.google.com/view/assin2

### Repositórios
- **Sentence-Transformers**: https://github.com/UKPLab/sentence-transformers
- **FlagEmbedding**: https://github.com/FlagOpen/FlagEmbedding
- **PORTULAN Models**: https://huggingface.co/PORTULAN

---

## 📅 Cronograma

### Semana 1: Setup e Revisão (5 dias)
- [x] Estruturação do projeto
- [ ] Revisão bibliográfica (papers)
- [ ] Setup técnico (modelos + GPU)
- [ ] Preparação de dataset

### Semana 2: Experimentação (5 dias)
- [ ] Geração de embeddings (batch)
- [ ] Avaliação quantitativa (métricas)
- [ ] Avaliação qualitativa (casos)
- [ ] Benchmark de velocidade

### Semana 3: Documentação (5 dias)
- [ ] Escrita do documento de pesquisa
- [ ] Criação de visualizações
- [ ] Preparação de apresentação
- [ ] Revisão final

---

## 📋 Deliverables

- [ ] **Notebook Jupyter** (`notebooks/embedding_comparison.ipynb`)
- [ ] **Documento de Pesquisa** (`docs/RESEARCH_EMBEDDING_MODELS.md`)
- [ ] **Apresentação Executiva** (`docs/presentation_embedding_models.pdf`)
- [ ] **Scripts Reproduzíveis** (`scripts/*.py`)
- [ ] **Resultados Salvos** (`results/`)

---

## 🔗 Relações com Outras Issues

**Alimenta:**
- Issue #2 (Fine-tuning) - modelo base para fine-tune
- Issue #5 (RAG) - modelo de embedding para retrieval
- Issue #8 (Storage) - informações sobre dimensões/volumes
- Issue #10 (Trends) - embeddings para clustering
- Issue #11 (Cross-Órgãos) - similaridade semântica

---

## 📝 Notas de Implementação

### Dependências Principais
```python
sentence-transformers>=2.2.0
transformers>=4.30.0
torch>=2.0.0
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
matplotlib>=3.7.0
seaborn>=0.12.0
```

### Tempo Estimado de Computação
- Carregamento de modelos: ~10min
- Geração de embeddings (300k docs): 2-8 horas (GPU dependente)
- Cálculo de métricas: ~30min
- **Total**: ~1 dia de computação

---

## 🎓 Aprendizados Esperados

### Técnicos
- Avaliar qualidade de embeddings objetivamente
- Trade-offs entre arquiteturas de modelos
- Impacto de dimensionalidade e contexto

### Domínio
- Características de textos governamentais
- Desafios de jargão técnico e siglas
- Importância de contexto brasileiro vs europeu

### Metodológicos
- Conduzir benchmark reproduzível
- Balancear métricas quantitativas e qualitativas
- Criar dataset de validação representativo

---

**Última Atualização**: 2026-03-05
**Versão**: 1.0
