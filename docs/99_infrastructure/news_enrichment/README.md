# News Enrichment System

Sistema de enriquecimento e classificação automática de notícias usando Large Language Models (LLMs), desenvolvido para processar notícias do Portal Gov.br.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/Poetry-managed-blue)](https://python-poetry.org/)
[![Anthropic Claude](https://img.shields.io/badge/Powered%20by-Claude%20Haiku-orange)](https://www.anthropic.com)

## Funcionalidades

- **Classificação Hierárquica**: Classifica notícias em 3 níveis de taxonomia (410 categorias)
- **Classificador Standalone**: API independente de banco de dados
- **Processamento em Batch**: Suporte para processar múltiplas notícias simultaneamente
- **Multi-Provider**: Suporta Anthropic Claude, OpenAI, Groq e Ollama (local)
- **Otimizado para Performance**: Processamento paralelo com ThreadPoolExecutor
- **Taxonomia Rica**: Sistema hierárquico com 10 temas principais e centenas de subtemas

## Arquitetura

```
news_enrichment/
├── classifier.py          # Classificador standalone (sem DB)
├── enricher.py           # Enriquecedor com persistência
├── llm_client.py         # Cliente LLM base
├── llm_client_optimized.py  # Cliente otimizado para batch
├── local_llm_client.py   # Cliente para LLMs locais (Ollama)
├── dataset_manager.py    # Gerenciamento de datasets
└── postgres_exporter.py  # Exportação para PostgreSQL
```

## Instalação

> **Nota**: Este projeto faz parte do workspace [data-science](../../). O ambiente Poetry é gerenciado na raiz do repositório.

### Pré-requisitos

- Python 3.9 ou superior
- Poetry (gerenciador de dependências)

### 1. Clone o repositório principal

```bash
git clone https://github.com/seu-usuario/data-science.git
cd data-science
```

### 2. Instale o Poetry (se necessário)

```bash
# Linux/Mac/WSL
curl -sSL https://install.python-poetry.org | python3 -

# Ou via pip
pip install poetry
```

### 3. Instale as dependências

```bash
# Instalação básica (da raiz do repositório)
poetry install

# Com dependências de desenvolvimento
poetry install --with dev

# Com suporte a Machine Learning (PyTorch)
poetry install --extras ml

# Completo (dev + ML)
poetry install --with dev --extras ml
```

### 4. Ative o ambiente virtual

```bash
# Poetry cria e gerencia o ambiente automaticamente
poetry shell

# Ou execute comandos diretamente
poetry run python source/news-enrichment/examples/classificacao_simples.py
```

### 5. Configure as variáveis de ambiente

```bash
# Na raiz do repositório
cp .env.example .env
# Edite .env e adicione suas API keys
```

## Uso Rápido

### Classificação Simples (Standalone)

```python
from news_enrichment import NewsClassifier

# Inicializar classificador
classifier = NewsClassifier(
    provider="anthropic",
    model="claude-3-haiku-20240307"
)

# Classificar uma notícia
news = {
    "title": "Governo anuncia reforma tributária",
    "content": "O governo federal apresentou hoje..."
}

result = classifier.classify_single(news)
print(result)  # JSON com classificações
```

### Processamento em Batch

```python
# Classificar múltiplas notícias
news_list = [news1, news2, news3, ...]
results = classifier.classify_batch(news_list)
```

### Enriquecimento com Dataset

```python
from news_enrichment import NewsEnricher

enricher = NewsEnricher(
    dataset_path="data/news.parquet",
    provider="anthropic"
)

# Enriquecer todas as notícias
enricher.enrich_all()

# Salvar resultados
enricher.save("data/news_enriched.parquet")
```

## Documentação

A documentação completa está disponível em:

- **[Classifier README](docs/CLASSIFIER_README.qmd)** - Documentação do classificador standalone
- **[Documentação de Prompts](docs/DOCUMENTACAO_PROMPTS.qmd)** - Benchmarks e análise de prompts
- **[Guia de Documentação](docs/DOCS_README.md)** - Índice geral da documentação

### Gerar documentação HTML/PDF

```bash
cd docs
make html  # Gera HTMLs
make pdf   # Gera PDFs
```

## Exemplos

Veja a pasta [examples/](examples/) para exemplos completos:

- **[classificacao_simples.py](examples/classificacao_simples.py)** - Uso básico do classificador
- **[classificacao_api.py](examples/classificacao_api.py)** - Integração com FastAPI/Flask
- **[enriquecimento_basico.py](examples/enriquecimento_basico.py)** - Enriquecimento de dataset
- **[enriquecimento_otimizado.py](examples/enriquecimento_otimizado.py)** - Versão otimizada para alto volume

## Benchmarks

Performance com Claude Haiku (110 notícias):

| Métrica | Valor |
|---------|-------|
| Tempo médio por notícia | 4.3s |
| Custo por notícia | $0.0024 |
| Acurácia (validação manual) | 92% |
| Taxa de sucesso | 100% |

Veja [benchmarks/](benchmarks/) para análises detalhadas.

## Taxonomia

A taxonomia hierárquica possui 3 níveis:

- **Nível 1**: 10 temas principais (Economia, Política, Saúde, etc.)
- **Nível 2**: ~50 subtemas
- **Nível 3**: ~410 categorias específicas

Arquivo: [arvore.yaml](../../arvore.yaml) (na raiz do repositório)

## Configuração Avançada

### Usando LLM Local (Ollama)

```python
classifier = NewsClassifier(
    provider="ollama",
    model="llama3:70b",
    api_base="http://localhost:11434"
)
```

### Ajustando Paralelismo

```python
from news_enrichment.llm_client_optimized import LLMClientOptimized

client = LLMClientOptimized(
    provider="anthropic",
    max_workers=8  # Aumentar paralelismo
)
```

## Contribuindo

Por favor:

1. Faça fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request
6. Tudo documentado e apontado de acordo com a Issue de origem.

## 👤 Autor

**Luis Felipe de Moraes**
- Cientista de Dados - CPQD


---
