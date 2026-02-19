# Data Science Workspace

Repositório centralizado de projetos de Data Science e Machine Learning desenvolvidos por Luis Felipe de Moraes.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/Poetry-managed-blue)](https://python-poetry.org/)


## 🎯 Sobre

Este workspace utiliza **Poetry** como gerenciador de dependências unificado, permitindo que múltiplos projetos compartilhem o mesmo ambiente virtual enquanto mantêm suas estruturas independentes.

## 📁 Estrutura

```
data-science/
├── README.md                  # Este arquivo
├── pyproject.toml             # Configuração Poetry (ambiente compartilhado)
├── poetry.lock                # Lock file das dependências
├── .venv/                     # Ambiente virtual (não versionado)
├── .gitignore                 # Arquivos ignorados
├── LICENSE                    # Licença MIT
│
└── source/                    # Projetos organizados
    └── news-enrichment/       # Sistema de classificação de notícias
        ├── news_enrichment/   # Código fonte
        ├── examples/          # Exemplos de uso
        ├── docs/              # Documentação
        ├── tests/             # Testes
        └── README.md          # Documentação específica
```

## 🚀 Projetos

### [News Enrichment System](source/news-enrichment/)

Sistema de enriquecimento e classificação automática de notícias usando Large Language Models (LLMs).

**Tecnologias:**
- AWS Bedrock (Claude Haiku)
- Polars / Pandas
- PostgreSQL
- Python 3.9+

**Features:**
- Classificação hierárquica em 3 níveis (410 categorias)
- Processamento em batch otimizado
- Suporte a múltiplos provedores LLM
- API standalone

[📖 Ver documentação completa](source/news-enrichment/README.md)

---

## 💻 Setup do Ambiente

### Pré-requisitos

- Python 3.9 ou superior
- Poetry (gerenciador de dependências)

### Instalação

```bash
# 1. Instalar Poetry (se necessário)
curl -sSL https://install.python-poetry.org | python3 -

# 2. Clonar repositório
git clone https://github.com/seu-usuario/data-science.git
cd data-science

# 3. Instalar dependências
poetry install

# 4. Ativar ambiente
poetry shell

# 5. Configurar variáveis (copiar .env.example se existir)
cp .env.example .env
# Editar .env com suas credenciais
```

### Instalação Personalizada

```bash
# Apenas dependências de produção
poetry install --only main

# Com dependências de desenvolvimento
poetry install --with dev

# Com Machine Learning (PyTorch)
poetry install --extras ml

# Completo
poetry install --with dev --extras ml
```

## 🛠️ Uso

### Executar Scripts

```bash
# Dentro do ambiente Poetry
poetry shell
python source/news-enrichment/examples/classificacao_simples.py

# Ou diretamente
poetry run python source/news-enrichment/examples/classificacao_simples.py
```

### Adicionar Dependências

```bash
# Adicionar nova biblioteca
poetry add nome-da-biblioteca

# Adicionar como dev dependency
poetry add --group dev pytest-mock

# Remover
poetry remove nome-da-biblioteca
```

### Testes

```bash
# Rodar testes de todos os projetos
poetry run pytest

# Rodar testes de um projeto específico
poetry run pytest source/news-enrichment/tests/

# Com coverage
poetry run pytest --cov
```

### Qualidade de Código

```bash
# Formatar código
poetry run black .

# Lint
poetry run flake8 source/

# Type checking
poetry run mypy source/
```

## 📚 Estrutura de Dependências

As dependências são organizadas em grupos:

**Main (Produção):**
- `polars`, `pandas` - Manipulação de dados
- `boto3` - AWS SDK
- `psycopg2-binary` - PostgreSQL
- `requests`, `tqdm`, `pyyaml`

**Dev (Desenvolvimento):**
- `pytest`, `pytest-cov` - Testes
- `black`, `flake8`, `mypy`, `isort` - Qualidade
- `jupyter`, `ipykernel` - Notebooks

**Docs (Documentação):**
- `mkdocs`, `mkdocs-material`

**ML (Machine Learning - Opcional):**
- `torch` - PyTorch

## 🤝 Contribuindo

Para contribuir:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/NovaFeature`)
3. Commit suas mudanças (`git commit -m 'Add: nova feature'`)
4. Push para a branch (`git push origin feature/NovaFeature`)
5. Abra um Pull Request
6. Tudo documentado e apontado de acordo com a Issue de origem.

## 📋 Convenções

### Organização de Projetos

Novos projetos devem seguir a estrutura:

```
source/
└── nome-do-projeto/
    ├── nome_do_projeto/    # Código fonte (snake_case)
    │   ├── __init__.py
    │   └── ...
    ├── examples/           # Exemplos de uso
    ├── tests/              # Testes unitários
    ├── docs/               # Documentação específica
    └── README.md           # Documentação do projeto
```


## 👤 Autor

**Luis Felipe de Moraes**
- Cientista de Dados - CPQD

## 🔗 Links Úteis

- [Poetry Documentation](https://python-poetry.org/docs/)
- [News Enrichment System](source/news-enrichment/)
- [Python Best Practices](https://docs.python-guide.org/)

---

**Workspace mantido com ☕**
