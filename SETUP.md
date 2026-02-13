# Setup do Ambiente - News Enrichment System

## 🎯 Setup Rápido (Recomendado)

```bash
# 1. Instalar Poetry (se ainda não tiver)
curl -sSL https://install.python-poetry.org | python3 -

# 2. Clonar/entrar no repositório
cd data-science

# 3. Instalar dependências
poetry install

# 4. Ativar ambiente
poetry shell

# 5. Configurar API keys
cp .env.example .env
# Editar .env com suas chaves

# 6. Testar instalação
python -c "import polars, pandas, boto3; print('✅ Ambiente OK!')"
```

## 📦 O que foi configurado?

### Poetry como Gerenciador de Dependências

O projeto agora usa **Poetry** ao invés de `pip + requirements.txt`. Vantagens:

- ✅ Ambiente virtual automático (`.venv/`)
- ✅ Lock file determinístico (`poetry.lock`)
- ✅ Resolução inteligente de conflitos
- ✅ Grupos de dependências (dev, docs, ml)
- ✅ Dependências opcionais

### Estrutura de Dependências

**Produção (sempre instaladas):**
- `polars`, `pandas` - Processamento de dados
- `boto3`, `botocore` - AWS Bedrock
- `psycopg2-binary` - PostgreSQL
- `requests` - HTTP client (Ollama)
- `tqdm` - Progress bars
- `pyyaml` - Config files

**Desenvolvimento (--with dev):**
- `pytest`, `pytest-cov` - Testes
- `black`, `flake8`, `mypy`, `isort` - Code quality
- `jupyter`, `ipykernel` - Notebooks

**Machine Learning (--extras ml):**
- `torch` - PyTorch (para scripts BERT)

### Arquivos Importantes

```
.
├── pyproject.toml      # Configuração Poetry + ferramentas
├── poetry.lock         # Lock file (VERSIONAR!)
├── .venv/              # Ambiente virtual (NÃO versionar)
├── .env.example        # Template de variáveis
├── .env                # Suas keys (NÃO versionar)
├── .gitignore          # Arquivos ignorados
├── POETRY_GUIDE.md     # Guia completo do Poetry
└── SETUP.md            # Este arquivo
```

## 🚀 Workflows Comuns

### Desenvolvimento

```bash
# Ativar ambiente
poetry shell

# Rodar script
python exemplo_classificacao.py

# Ou sem ativar
poetry run python exemplo_classificacao.py
```

### Adicionar Biblioteca

```bash
# Adicionar dependência
poetry add transformers

# Versão específica
poetry add "transformers>=4.30.0"

# Dependência de dev
poetry add --group dev pylint
```

### Testes e Qualidade

```bash
# Rodar testes
poetry run pytest

# Com coverage
poetry run pytest --cov

# Formatar código
poetry run black .

# Lint
poetry run flake8 news_enrichment/
```

### Atualizar Dependências

```bash
# Atualizar todas
poetry update

# Atualizar uma específica
poetry update polars

# Ver desatualizadas
poetry show --outdated
```

## 🔧 Configurações do Poetry

O Poetry foi configurado com:

```bash
# .venv na pasta do projeto
poetry config virtualenvs.in-project true
```

Outras configs úteis:

```bash
# Ver todas as configurações
poetry config --list

# Usar cache local
poetry config cache-dir .poetry_cache

# Python version
poetry env use python3.12
```

## 📝 Variáveis de Ambiente

Copie `.env.example` para `.env` e configure:

```bash
# AWS Bedrock (principal)
ANTHROPIC_API_KEY=sk-ant-...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Alternativas (opcional)
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...

# Local (opcional)
OLLAMA_BASE_URL=http://localhost:11434

# PostgreSQL (opcional)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=news_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
```

## 🐛 Troubleshooting

### Poetry não encontrado

```bash
# Adicionar ao PATH
export PATH="$HOME/.local/bin:$PATH"

# Adicionar ao ~/.bashrc ou ~/.zshrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Erro de dependências

```bash
# Limpar cache e reinstalar
poetry cache clear pypi --all
rm -rf .venv poetry.lock
poetry install
```

### Conflito de Python versions

```bash
# Ver ambientes disponíveis
poetry env list

# Remover ambiente atual
poetry env remove python

# Criar com version específica
poetry env use python3.12
poetry install
```

### Erro ao instalar psycopg2-binary

```bash
# Instalar dependências do sistema (Ubuntu/Debian)
sudo apt-get install libpq-dev python3-dev

# Reinstalar
poetry install
```

### torch muito pesado?

Se não precisa dos scripts de ML (BERT):

```bash
# Instalar sem PyTorch
poetry install --without ml

# Ou desinstalar
poetry remove torch
```

## 🎓 Recursos

- **[POETRY_GUIDE.md](POETRY_GUIDE.md)** - Guia completo do Poetry
- **[README.md](README.md)** - Documentação do projeto
- **[.env.example](.env.example)** - Template de configuração
- [Poetry Docs](https://python-poetry.org/docs/) - Documentação oficial

## 📦 Migração do Antigo Setup

Os arquivos antigos foram preservados como backup:

- `requirements.txt.old` - Antigo pip requirements
- `pyproject.toml.old` - Antigo setuptools config

Você pode removê-los após confirmar que tudo funciona:

```bash
rm *.old
```

## ✅ Checklist de Setup

- [ ] Poetry instalado (`poetry --version`)
- [ ] Dependências instaladas (`poetry install`)
- [ ] Ambiente ativo (`poetry shell`)
- [ ] `.env` configurado com suas keys
- [ ] Teste passou (`python -c "import polars, boto3; print('OK')"`)
- [ ] Script de exemplo roda (`python exemplo_classificacao.py`)

---

**Setup completo!** 🎉

Se tiver problemas, consulte [POETRY_GUIDE.md](POETRY_GUIDE.md) ou abra uma issue.
