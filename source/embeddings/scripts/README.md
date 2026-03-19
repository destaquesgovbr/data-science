# Scripts de Avaliação de Embeddings

Scripts para executar o pipeline completo de avaliação de modelos de embedding conforme o [ROTEIRO_TESTES_EMBEDDINGS.md](../ROTEIRO_TESTES_EMBEDDINGS.md).

## Estrutura

```
scripts/
├── load_models.py         # Carregamento dos 10 modelos de embedding
├── prepare_corpus.py      # Preparação do corpus de teste (100 docs + queries)
├── evaluate_models.py     # Implementação das métricas (NDCG, MAP, MRR)
├── run_evaluation.py      # Pipeline completo de avaliação
└── README.md              # Este arquivo
```

## 1. Preparar Corpus de Teste

### Criar corpus de exemplo

```bash
cd source/embeddings/scripts

# Criar estrutura com dados de exemplo
poetry run python prepare_corpus.py --create-sample

# Ver estatísticas
poetry run python prepare_corpus.py --stats

# Exportar para CSV
poetry run python prepare_corpus.py --export corpus_export
```

**Dica:** Para não precisar digitar `poetry run` toda vez:
```bash
# Ative o ambiente virtual do poetry
poetry shell

# Agora pode usar python diretamente
python prepare_corpus.py --create-sample
```

### Estrutura esperada

```
data/
├── documents/           # 100 notícias (JSON)
│   ├── doc_00_00.json
│   ├── doc_00_01.json
│   └── ...
├── queries/             # 30-40 queries (JSON)
│   ├── q001.json
│   ├── q002.json
│   └── ...
└── annotations/         # Anotações de relevância (JSONL)
    ├── query_q001.jsonl
    ├── query_q002.jsonl
    └── ...
```

### Formato dos dados

**Document (doc_XX_YY.json):**
```json
{
  "id": "doc_00_00",
  "title": "Ministério da Saúde anuncia nova campanha",
  "content": "Texto completo da notícia...",
  "category": "Saúde",
  "length": 250,
  "metadata": {}
}
```

**Query (qXXX.json):**
```json
{
  "id": "q001",
  "text": "novas medidas para educação",
  "query_type": "geral",
  "expected_category": "Educação",
  "metadata": {}
}
```

**Annotation (query_qXXX.jsonl):**
```json
{"query_id": "q001", "doc_id": "doc_01_00", "relevance": 3, "notes": "Muito relevante"}
{"query_id": "q001", "doc_id": "doc_01_01", "relevance": 2, "notes": "Relevante"}
{"query_id": "q001", "doc_id": "doc_00_00", "relevance": 0, "notes": "Não relacionado"}
```

**Escala de relevância:**
- 0: Irrelevante
- 1: Pouco relevante
- 2: Relevante
- 3: Muito relevante

## 2. Listar Modelos Disponíveis

```bash
# Ver informações de todos os modelos
poetry run python load_models.py --info

# Testar carregamento (apenas multilinguais)
poetry run python load_models.py --category multilingual

# Testar carregamento (apenas PT-específicos)
poetry run python load_models.py --category pt-specific
```

### Modelos disponíveis

**Multilinguais (4):**
- BGE-M3
- E5-Large-Multilingual
- GTE-Multilingual-Base
- Paraphrase-Multilingual-MPNet

**PT-BR Específicos (6):**
- BGE-Large-PT
- BGE-Small-PT
- Serafim-900M
- Serafim-335M
- Jina-V2-Base-PT
- BERTimbau-Base

## 3. Testar Métricas

```bash
# Executar testes unitários das métricas
poetry run python evaluate_models.py
```

Testa:
- NDCG@10 (Normalized Discounted Cumulative Gain)
- MAP (Mean Average Precision)
- MRR (Mean Reciprocal Rank)

## 4. Executar Avaliação Completa

### Avaliar todos os modelos

```bash
# Pipeline completo (GPU se disponível)
poetry run python run_evaluation.py

# Forçar CPU
poetry run python run_evaluation.py --device cpu

# Forçar GPU
poetry run python run_evaluation.py --device cuda
```

### Avaliar categoria específica

```bash
# Apenas multilinguais
poetry run python run_evaluation.py --category multilingual

# Apenas PT-específicos
poetry run python run_evaluation.py --category pt-specific
```

### Avaliar modelos específicos

```bash
# Testar apenas BGE-M3 e BERTimbau
poetry run python run_evaluation.py --models BGE-M3 BERTimbau-Base

# Testar apenas os modelos BGE
poetry run python run_evaluation.py --models BGE-M3 BGE-Large-PT BGE-Small-PT
```

### Customizar parâmetros

```bash
# Mudar tamanho do ranking (padrão: 10)
poetry run python run_evaluation.py --k 20

# Mudar diretórios
poetry run python run_evaluation.py --data-dir /path/to/data --results-dir /path/to/results
```

## 5. Resultados

Após a avaliação, os seguintes arquivos são gerados em `results/`:

```
results/
├── evaluation_results_YYYYMMDD_HHMMSS.csv    # Todas as métricas (CSV)
├── evaluation_results_YYYYMMDD_HHMMSS.json   # Todas as métricas (JSON)
└── evaluation_report_YYYYMMDD_HHMMSS.txt     # Relatório resumido
```

### Exemplo de relatório

```
====================================================================================================
RANKING FINAL DOS MODELOS
====================================================================================================

Rank   Modelo                              Score      NDCG Geral   NDCG Jargão
----------------------------------------------------------------------------------------------------
1      BGE-M3                              87.3       0.8542       0.8231
2      E5-Large-Multilingual               84.1       0.8421       0.8012
3      Serafim-900M                        81.5       0.8234       0.7890
...
```

## 6. Workflow Recomendado

### Semana 1 - Setup e Preparação

```bash
# 1. Criar corpus de exemplo
python prepare_corpus.py --create-sample

# 2. Verificar modelos
poetry run python load_models.py --info

# 3. Testar métricas
poetry run python evaluate_models.py

# 4. Teste rápido com 2 modelos
poetry run python run_evaluation.py --models BGE-M3 BERTimbau-Base
```

### Semana 2 - Avaliação Completa

```bash
# 1. Coletar dados reais (manual)
# - 100 notícias gov.br
# - 30-40 queries
# - Anotar relevâncias

# 2. Avaliar todos os modelos
poetry run python run_evaluation.py

# 3. Analisar resultados
cat ../results/evaluation_report_*.txt
```

### Semana 3 - Análise e Documentação

```bash
# 1. Re-executar top 3 para confirmar
poetry run python run_evaluation.py --models [top-3-models]

# 2. Gerar visualizações (usar notebook)
# Ver: ../notebooks/embedding_comparison.ipynb

# 3. Documentar decisão final
```

## Troubleshooting

### Erro: CUDA out of memory

```bash
# Opção 1: Usar CPU
poetry run python run_evaluation.py --device cpu

# Opção 2: Avaliar um modelo por vez
poetry run python run_evaluation.py --models BGE-M3
poetry run python run_evaluation.py --models E5-Large-Multilingual
```

### Erro: Modelo não encontrado no HuggingFace

```bash
# Verificar conectividade
pip install -U sentence-transformers

# Baixar modelo manualmente
poetry run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

### Corpus vazio

```bash
# Criar corpus de exemplo primeiro
python prepare_corpus.py --create-sample

# Verificar
python prepare_corpus.py --stats
```

## Métricas Calculadas

### Qualidade de Retrieval

- **NDCG@10** (0-1): Qualidade do ranking considerando relevância gradual
- **MAP** (0-1): Precisão média considerando todos os documentos relevantes
- **MRR** (0-1): Posição do primeiro documento relevante

### Performance

- **Throughput**: Documentos processados por segundo
- **Latência P50/P95/P99**: Percentis de latência em milissegundos

### Score Final

Conforme roteiro (0-100 pontos):
- NDCG@10 Geral: 25 pts
- NDCG@10 Jargão BR: 25 pts
- MAP: 10 pts
- MRR: 5 pts
- Throughput: 15 pts
- Latência P99: 10 pts
- Docs Longos: 10 pts

## Dependências

```bash
# Instalar via poetry (na raiz do projeto)
poetry install

# Ou via pip
pip install sentence-transformers scikit-learn pandas numpy
```

## Referências

- [ROTEIRO_TESTES_EMBEDDINGS.md](../ROTEIRO_TESTES_EMBEDDINGS.md) - Plano completo de 3 semanas
- [PAPERS_READING_LIST.md](../docs/PAPERS_READING_LIST.md) - Papers de referência
- [embedding_comparison.ipynb](../notebooks/embedding_comparison.ipynb) - Análise visual
