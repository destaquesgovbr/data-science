# Guia Rápido - Avaliação de Embeddings

Guia prático para executar a avaliação de modelos de embedding conforme Issue #1.

## Setup Inicial (5 minutos)

### 1. Instalar dependências

```bash
# Na raiz do projeto
cd /l/disk0/lpmoraes/environments/data-science
poetry install

# IMPORTANTE: Use 'poetry run python' para executar scripts
# Ou ative o ambiente virtual:
poetry shell
```

**Alias útil** (adicione no seu ~/.bashrc):
```bash
alias poetrypy="poetry run python"
```

### 2. Verificar instalação

```bash
cd source/embeddings/scripts

# Ver modelos disponíveis
poetry run poetry run python load_models.py --info

# Testar métricas
poetry run python evaluate_models.py
```

**Saída esperada:**
```
====================================================================================================
MODELOS DISPONÍVEIS PARA AVALIAÇÃO
====================================================================================================
...
✓ Testes concluídos
```

## Teste Rápido (10 minutos)

### 1. Criar corpus de exemplo

```bash
poetry run python prepare_corpus.py --create-sample
```

### 2. Avaliar 2 modelos

```bash
# Teste com BGE-M3 e BERTimbau (mais rápido)
poetry run python run_evaluation.py --models BGE-M3 BERTimbau-Base
```

**Saída esperada:**
```
====================================================================================================
PIPELINE DE AVALIAÇÃO DE MODELOS DE EMBEDDING
====================================================================================================
...
✓ Avaliação completa!
```

### 3. Ver resultados

```bash
cat ../results/evaluation_report_*.txt
```

## Avaliação Completa (Issue #1)

### Semana 1: Preparação de Dados

#### 1.1. Coletar 250 notícias

Fonte: https://www.gov.br/pt-br/noticias

**Distribuição (10 categorias × 25 docs):**
- Saúde
- Educação
- Economia
- Meio Ambiente
- Segurança Pública
- Assistência Social
- Infraestrutura
- Cultura
- Ciência e Tecnologia
- Agricultura

**Formato:**
```json
{
  "id": "doc_00_00",
  "title": "Título da notícia",
  "content": "Conteúdo completo...",
  "category": "Saúde",
  "length": 250,
  "metadata": {}
}
```

Salvar em: `data/documents/doc_XX_YY.json`

#### 1.2. Criar 60 queries

**Tipos:**
- 25 gerais (linguagem natural)
- 25 jargão BR (siglas, termos técnicos)
- 10 docs longos

**Formato:**
```json
{
  "id": "q001",
  "text": "novas medidas para educação",
  "query_type": "geral",
  "expected_category": "Educação"
}
```

Salvar em: `data/queries/qXXX.json`

#### 1.3. Anotar relevâncias

Para cada query, anotar pelo menos 15 documentos (~900 anotações totais):

**Formato:**
```jsonl
{"query_id": "q001", "doc_id": "doc_01_00", "relevance": 3, "notes": "Muito relevante"}
{"query_id": "q001", "doc_id": "doc_01_01", "relevance": 2, "notes": "Relevante"}
...
```

**Escala:**
- 3: Muito relevante
- 2: Relevante
- 1: Pouco relevante
- 0: Irrelevante

Salvar em: `data/annotations/query_qXXX.jsonl`

#### 1.4. Validar corpus

```bash
poetry run python prepare_corpus.py --stats
```

**Checklist:**
- [ ] 250 documentos (25 por categoria)
- [ ] 60 queries (25 geral + 25 jargão + 10 longos)
- [ ] ~900 anotações (15 docs por query)
- [ ] Formato JSON válido

### Semana 2: Execução da Avaliação

#### 2.1. Avaliar todos os modelos

```bash
# GPU (recomendado)
poetry run python run_evaluation.py

# CPU (mais lento)
poetry run python run_evaluation.py --device cpu
```

**Tempo estimado:**
- GPU: 2-4 horas para 10 modelos
- CPU: 8-12 horas para 10 modelos

#### 2.2. Avaliar por etapas (se GPU limitada)

```bash
# Primeiro os multilinguais
poetry run python run_evaluation.py --category multilingual

# Depois os PT-específicos
poetry run python run_evaluation.py --category pt-specific
```

#### 2.3. Monitorar progresso

O script exibe progresso em tempo real:

```
==================================================================================================
MODELO 1/10: BGE-M3
==================================================================================================

Carregando BGE-M3 (BAAI/bge-m3)...
✓ BGE-M3 carregado com sucesso!

1. Avaliando queries gerais...
Codificando 100 documentos...
Codificando 15 queries...
...
```

### Semana 3: Análise dos Resultados

#### 3.1. Ver ranking final

```bash
cat ../results/evaluation_report_*.txt
```

**Exemplo:**
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

#### 3.2. Analisar métricas detalhadas

```bash
# CSV completo
cat ../results/evaluation_results_*.csv

# JSON para análise programática
cat ../results/evaluation_results_*.json
```

#### 3.3. Comparar top 3 modelos

```bash
# Re-executar apenas os 3 melhores para confirmar
poetry run python run_evaluation.py --models BGE-M3 E5-Large-Multilingual Serafim-900M
```

#### 3.4. Visualizações (notebook)

```bash
jupyter notebook ../notebooks/embedding_comparison.ipynb
```

## Comandos Úteis

### Listar modelos disponíveis

```bash
poetry run poetry run python load_models.py --info
```

### Testar carregamento de um modelo

```bash
poetry run python load_models.py --models BGE-M3
```

### Ver estatísticas do corpus

```bash
poetry run python prepare_corpus.py --stats
```

### Exportar corpus para CSV

```bash
poetry run python prepare_corpus.py --export corpus_export
```

### Avaliar modelos específicos

```bash
poetry run python run_evaluation.py --models BGE-M3 BERTimbau-Base
```

### Mudar device

```bash
# Auto (padrão)
poetry run python run_evaluation.py --device auto

# Forçar GPU
poetry run python run_evaluation.py --device cuda

# Forçar CPU
poetry run python run_evaluation.py --device cpu
```

## Troubleshooting

### Erro: CUDA out of memory

**Solução 1: Usar CPU**
```bash
poetry run python run_evaluation.py --device cpu
```

**Solução 2: Avaliar um por vez**
```bash
for model in BGE-M3 E5-Large-Multilingual BERTimbau-Base; do
    poetry run python run_evaluation.py --models $model
    sleep 10  # Dar tempo para liberar memória
done
```

### Erro: Modelo não encontrado

**Solução:**
```bash
# Atualizar sentence-transformers
pip install -U sentence-transformers

# Baixar modelo manualmente
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

### Corpus vazio

**Solução:**
```bash
# Criar corpus de exemplo primeiro
poetry run python prepare_corpus.py --create-sample

# Ou seguir passos da Semana 1 para corpus real
```

### Resultados muito baixos (NDCG < 0.3)

**Possíveis causas:**
1. Anotações incorretas (verificar relevâncias)
2. Queries mal formuladas (muito genéricas ou específicas)
3. Corpus de baixa qualidade (documentos muito curtos)

**Solução:**
```bash
# Revisar anotações
poetry run python prepare_corpus.py --export corpus_review
# Abrir CSV e verificar relevâncias
```

## Estrutura de Arquivos

```
source/embeddings/
├── QUICKSTART.md                    # Este arquivo
├── ROTEIRO_TESTES_EMBEDDINGS.md     # Plano completo (3 semanas)
├── README.md                         # Visão geral do projeto
│
├── data/                            # Corpus de teste
│   ├── documents/                   # 100 notícias (JSON)
│   ├── queries/                     # 40 queries (JSON)
│   ├── annotations/                 # Relevâncias (JSONL)
│   └── README.md
│
├── scripts/                         # Scripts de avaliação
│   ├── load_models.py              # Carrega modelos
│   ├── prepare_corpus.py           # Prepara corpus
│   ├── evaluate_models.py          # Implementa métricas
│   ├── run_evaluation.py           # Pipeline completo
│   └── README.md
│
├── notebooks/                       # Análise interativa
│   └── embedding_comparison.ipynb
│
├── docs/                            # Documentação
│   └── PAPERS_READING_LIST.md
│
└── results/                         # Resultados da avaliação
    ├── evaluation_results_*.csv
    ├── evaluation_results_*.json
    └── evaluation_report_*.txt
```

## Próximos Passos

1. **Agora:** Executar teste rápido (seção "Teste Rápido")
2. **Semana 1:** Preparar corpus real com 100 notícias
3. **Semana 2:** Executar avaliação completa
4. **Semana 3:** Analisar resultados e documentar decisão

## Referências

- [ROTEIRO_TESTES_EMBEDDINGS.md](ROTEIRO_TESTES_EMBEDDINGS.md) - Plano detalhado
- [PAPERS_READING_LIST.md](docs/PAPERS_READING_LIST.md) - Papers de referência
- [scripts/README.md](scripts/README.md) - Documentação dos scripts
- [data/README.md](data/README.md) - Formato do corpus

## Suporte

- **Dúvidas técnicas:** consultar [scripts/README.md](scripts/README.md)
- **Conceitos:** consultar [PAPERS_READING_LIST.md](docs/PAPERS_READING_LIST.md)
- **Planejamento:** consultar [ROTEIRO_TESTES_EMBEDDINGS.md](ROTEIRO_TESTES_EMBEDDINGS.md)
