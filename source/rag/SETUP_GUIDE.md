# Setup Guide - Issue #5: RAG System

## 📦 O que foi criado

### Estrutura de Diretórios
```
source/rag/
├── README.md                  # Documentação completa (50 páginas)
├── SETUP_GUIDE.md            # Este arquivo
├── requirements.txt          # Dependências Python
├── .env.example             # Template de variáveis de ambiente
├── .gitignore               # Git ignore rules
│
├── config/                  # Arquivos de configuração
│   ├── database.yaml       # PostgreSQL + pgvector
│   ├── embeddings.yaml     # BGE-M3 (Issue #1)
│   ├── llm.yaml           # Claude/GPT generation
│   └── retrieval.yaml     # Multi-stage retrieval
│
├── src/                    # Source code (próximo)
│   └── __init__.py
│
├── scripts/               # Utilitários
│   └── setup_database.py # Setup PostgreSQL schema
│
├── notebooks/            # Jupyter notebooks (próximo)
├── data/                # Datasets (próximo)
├── results/             # Resultados (próximo)
└── docs/                # Documentação técnica (próximo)
```

---

## 🚀 Quick Start

### 1. Setup Ambiente Python

```bash
cd source/rag

# Criar virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Download spaCy model (para chunking semântico)
python -m spacy download pt_core_news_lg
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar template
cp .env.example .env

# Editar .env com suas credenciais
nano .env  # ou vim, code, etc.
```

**Mínimo necessário:**
```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=news_db
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password

# LLM (escolher um)
ANTHROPIC_API_KEY=sk-...          # Claude
# ou
AWS_ACCESS_KEY_ID=...             # Bedrock
AWS_SECRET_ACCESS_KEY=...
# ou
OPENAI_API_KEY=sk-...             # GPT

# Embeddings (BGE-M3 da Issue #1)
EMBEDDING_DEVICE=cuda  # ou 'cpu'
```

### 3. Setup PostgreSQL Database

**Opção A: PostgreSQL já instalado**
```bash
# Verificar pgvector
psql -d news_db -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# Se pgvector não existe, instalar:
# https://github.com/pgvector/pgvector#installation

# Rodar setup
python scripts/setup_database.py --config config/database.yaml
```

**Opção B: Docker PostgreSQL + pgvector**
```bash
# Docker Compose (criar se necessário)
docker-compose up -d postgres

# Aguardar container subir
sleep 5

# Rodar setup
python scripts/setup_database.py
```

### 4. Verificar Setup

```bash
# Verificar extensão pgvector
psql -d news_db -c "\dx vector"

# Verificar tabelas
psql -d news_db -c "\dt"

# Ver schema da tabela de chunks
psql -d news_db -c "\d document_chunks"

# Testar BGE-M3 (Issue #1)
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-m3')
print('✓ BGE-M3 loaded successfully')
"
```

---

## 📋 Próximos Passos

### Fase 1: Indexing Pipeline (Semana 1-2)

**Tasks restantes:**
- [ ] `src/chunking.py` - Implementar chunking strategies
- [ ] `src/indexing.py` - Pipeline de indexação
- [ ] `scripts/index_corpus.py` - Script para indexar corpus
- [ ] `data/corpus_sample.json` - Sample de 10k notícias

**Ordem sugerida:**
1. Implementar `src/chunking.py` (semantic + fixed)
2. Implementar `src/indexing.py` (pipeline completo)
3. Criar `scripts/index_corpus.py`
4. Testar com sample pequeno (100 notícias)
5. Indexar corpus completo (10k)

### Fase 2: Retrieval Pipeline (Semana 3-4)

- [ ] `src/retrieval.py` - Multi-stage retrieval
- [ ] `scripts/test_retrieval.py` - Testar retrieval
- [ ] Implement RRF fusion
- [ ] Integrate re-ranking (Cohere ou cross-encoder)

### Fase 3: Generation Pipeline (Semana 5)

- [ ] `src/generation.py` - LLM generation
- [ ] `scripts/test_generation.py` - Testar generation
- [ ] Prompt engineering
- [ ] Citation extraction

### Fase 4: Interfaces (Semana 6)

- [ ] `src/mcp_server.py` - MCP Server
- [ ] `src/api/main.py` - REST API
- [ ] Documentation

---

## 🔍 Debugging

### PostgreSQL Connection Issues

```bash
# Test connection
psql -h localhost -p 5432 -U your_user -d news_db -c "SELECT version();"

# Check logs
tail -f /var/log/postgresql/postgresql-15-main.log

# Verify config
cat config/database.yaml
```

### pgvector Issues

```bash
# Verify pgvector installed
psql -d news_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# If error: install pgvector
# Ubuntu/Debian:
sudo apt install postgresql-15-pgvector

# macOS:
brew install pgvector

# From source:
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### BGE-M3 Issues

```bash
# Test manually
python << 'PYTHON'
from sentence_transformers import SentenceTransformer

print("Loading BGE-M3...")
model = SentenceTransformer('BAAI/bge-m3', device='cuda')

print("Testing encoding...")
embeddings = model.encode(["Test text"], normalize_embeddings=True)

print(f"✓ Success! Embedding shape: {embeddings.shape}")
PYTHON

# If CUDA out of memory, use CPU:
export EMBEDDING_DEVICE=cpu
```

---

## 📚 Documentação

**Completa:** [README.md](README.md) (~50 páginas)

**Resumos:**
- Fundamentos teóricos: Seção "Fundamentos Teóricos"
- Arquitetura: Seção "Arquitetura do Sistema"
- Configuração: Arquivos `config/*.yaml`
- Roadmap: Seção "Fases de Execução"

**Referências Externas:**
- pgvector: https://github.com/pgvector/pgvector
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- LangChain: https://python.langchain.com/
- RAGAS: https://github.com/explodinggradients/ragas

---

## 🐛 Troubleshooting

### "Cannot import SentenceTransformer"
```bash
pip install sentence-transformers
```

### "psycopg.OperationalError: could not connect"
- Verificar PostgreSQL está rodando: `sudo systemctl status postgresql`
- Verificar credenciais no `.env`
- Verificar firewall: `sudo ufw allow 5432`

### "pgvector extension not found"
- Instalar pgvector (ver seção pgvector Issues)
- Reiniciar PostgreSQL: `sudo systemctl restart postgresql`

### "CUDA out of memory"
- Reduzir batch size: `EMBEDDING_BATCH_SIZE=16`
- Usar CPU: `EMBEDDING_DEVICE=cpu`
- Usar float16: (já configurado em `embeddings.yaml`)

---

## ✅ Checklist de Setup

- [ ] Python 3.10+ instalado
- [ ] Virtual environment criado e ativado
- [ ] Dependências instaladas (`requirements.txt`)
- [ ] spaCy model baixado (`pt_core_news_lg`)
- [ ] PostgreSQL 15+ instalado e rodando
- [ ] pgvector extension instalada
- [ ] `.env` configurado com credenciais
- [ ] Database schema criado (`setup_database.py`)
- [ ] BGE-M3 testado e funcionando
- [ ] LLM API key configurada (Claude/Bedrock/OpenAI)

---

**Última atualização:** 2026-05-21  
**Status:** ✅ Setup base completo - Pronto para Fase 1 (Indexing)
