# Setup Completo EC2 - Sistema RAG

**Documento:** Guia completo de setup do ambiente EC2 para produção  
**Data:** 2026-06-09  
**Autor:** Luis Felipe de Moraes (com Claude Code)  
**Contexto:** Lições aprendidas durante escala 250 → 10k notícias

---

## 📋 Visão Geral

Este documento detalha TODO o processo de setup de uma instância EC2 limpa para rodar o sistema RAG de Q&A sobre notícias governamentais. Inclui todas as soluções de problemas encontrados e decisões tomadas.

**Tempo total estimado:** ~60 minutos (setup + indexação)

---

## 🎯 Pré-requisitos

### Instância EC2
- **Tipo:** g5.xlarge ou superior (GPU necessária)
- **OS:** Ubuntu 24.04 LTS
- **Storage:** 100 GB SSD (mínimo)
- **RAM:** 16 GB (mínimo)
- **GPU:** NVIDIA (para embeddings rápidos)

### Acesso
- Chave SSH configurada
- Usuário: `lpmoraes` (ou seu usuário)
- Host: `aws-insp-7-01` (ou seu hostname)

---

## 🚀 Passo a Passo Completo

### 1. Conexão Inicial

```bash
# Local
ssh lpmoraes@aws-insp-7-01
```

### 2. Atualizar Sistema

```bash
# Na EC2
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential git wget curl
```

### 3. Instalar Python 3.12+

```bash
# Verificar versão
python3 --version  # Deve ser 3.12+

# Se necessário, instalar
sudo apt install -y python3 python3-pip python3-venv
```

### 4. Instalar PostgreSQL com pgvector

```bash
# Instalar PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Iniciar serviço
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Instalar pgvector
sudo apt install -y postgresql-server-dev-all
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### 5. Configurar PostgreSQL

#### 5.1 Resetar senha do postgres
```bash
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres123';"
```

#### 5.2 Criar banco de dados
```bash
PGPASSWORD=postgres123 psql -h localhost -U postgres -c "CREATE DATABASE ragdb;"
```

#### 5.3 Habilitar pgvector e criar schema
```bash
PGPASSWORD=postgres123 psql -h localhost -U postgres -d ragdb << 'EOF'

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create documents table (URL como unique para ON CONFLICT)
CREATE TABLE news_documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT UNIQUE,  -- IMPORTANTE: unique constraint!
    source_agency TEXT,
    category TEXT,
    published_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB,
    indexed_at TIMESTAMP DEFAULT NOW()
);

-- Create chunks table
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES news_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    enriched_content TEXT,
    embedding vector(1024),
    chunk_type TEXT,
    char_start INTEGER,
    char_end INTEGER,
    tokens INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- Create indexes
CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_documents_category ON news_documents(category);
CREATE INDEX idx_documents_url ON news_documents(url);
CREATE INDEX idx_documents_published ON news_documents(published_at);

-- Vector index será criado depois com dados
-- CREATE INDEX idx_chunks_embedding ON document_chunks 
--   USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

EOF
```

**⚠️ IMPORTANTE:** O schema acima foi ajustado para match com o código `src/indexing.py`:
- `url` com constraint UNIQUE (para `ON CONFLICT (url)`)
- Colunas: `content`, `enriched_content`, `chunk_type`, `char_start`, `char_end`, `tokens`
- `document_id` como INTEGER (não TEXT) porque é SERIAL

### 6. Criar Estrutura de Diretórios

```bash
# Na EC2
mkdir -p ~/rag/{data,scripts,src,config,logs}
```

### 7. Configurar Ambiente Python

#### 7.1 Criar venv
```bash
cd ~/rag
python3 -m venv .venv
source .venv/bin/activate
```

#### 7.2 Instalar dependências
```bash
pip install --upgrade pip
pip install sentence-transformers psycopg[binary] pyyaml rich tqdm python-dotenv torch
```

**Nota:** Para GPU, instalar versão CUDA do torch:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### 8. Transferir Arquivos do Repositório

**No terminal LOCAL**, execute:

```bash
cd ~/environments/data-science

# 8.1 - Recuperar arquivos do git (se necessário)
git show f4f1463bb:source/rag/scripts/index_corpus.py > source/rag/scripts/index_corpus.py
git show f4f1463bb:source/rag/src/__init__.py > source/rag/src/__init__.py
git show f4f1463bb:source/rag/src/chunking.py > source/rag/src/chunking.py
git show f4f1463bb:source/rag/src/generation.py > source/rag/src/generation.py
git show f4f1463bb:source/rag/src/indexing.py > source/rag/src/indexing.py
git show f4f1463bb:source/rag/src/llm_providers.py > source/rag/src/llm_providers.py
git show f4f1463bb:source/rag/src/reranking.py > source/rag/src/reranking.py
git show f4f1463bb:source/rag/src/retrieval.py > source/rag/src/retrieval.py

# Configs
git show f4f1463bb:source/rag/config/database.yaml > source/rag/config/database.yaml
git show f4f1463bb:source/rag/config/embeddings.yaml > source/rag/config/embeddings.yaml
git show f4f1463bb:source/rag/config/llm.yaml > source/rag/config/llm.yaml
git show f4f1463bb:source/rag/config/retrieval.yaml > source/rag/config/retrieval.yaml

# 8.2 - Transferir para EC2
scp source/rag/scripts/index_corpus.py lpmoraes@aws-insp-7-01:~/rag/scripts/
scp source/rag/src/*.py lpmoraes@aws-insp-7-01:~/rag/src/
scp source/rag/config/*.yaml lpmoraes@aws-insp-7-01:~/rag/config/
```

### 9. Configurar Variáveis de Ambiente

**Na EC2**, criar arquivo `.env`:

```bash
cat > ~/rag/.env << 'EOF'
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ragdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# Embeddings
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024
EMBEDDING_DEVICE=cuda  # ou cpu se não tiver GPU

# Retrieval
IVFFLAT_PROBES=10
VECTOR_SEARCH_TOP_K=50
FULLTEXT_SEARCH_TOP_K=50

# Indexing
BATCH_SIZE=32
SKIP_EXISTING=true
EOF
```

### 10. Configurar PYTHONPATH

**Na EC2**, adicionar ao `~/.bashrc`:

```bash
echo 'export PYTHONPATH="/l/disk0/lpmoraes/rag:$PYTHONPATH"' >> ~/.bashrc
source ~/.bashrc
```

Ou exportar manualmente antes de rodar:
```bash
export PYTHONPATH="/l/disk0/lpmoraes/rag:$PYTHONPATH"
```

### 11. Transferir Corpus de Dados

**No LOCAL**, transferir arquivo de dados:

```bash
# Se ainda não extraiu, extrair do banco local
cd ~/environments/data-science
python source/rag/scripts/extract_10k_corpus.py \
  --output source/rag/data/corpus_10k.json \
  --limit 10000 \
  --host localhost \
  --port 5433 \
  --dbname news_db \
  --user postgres

# Transferir para EC2
scp source/rag/data/corpus_10k.json lpmoraes@aws-insp-7-01:~/rag/data/
```

### 12. Indexar Corpus

**Na EC2**:

```bash
cd ~/rag
source .venv/bin/activate
export PYTHONPATH="/l/disk0/lpmoraes/rag:$PYTHONPATH"

# Rodar indexação
python scripts/index_corpus.py --input data/corpus_10k.json --format json
```

**Tempo estimado:**
- 10k documentos: ~30-40 minutos
- 50k documentos: ~2-3 horas

**Progresso esperado:**
```
Loading embedding model... ✓
Loading documents... ✓ 10000 documents
Creating indexing pipeline... ✓
Indexing documents: 100%|████████████| 10000/10000 [35:24<00:00, 4.7it/s]
```

### 13. Criar Índices Vetoriais (Pós-indexação)

**Após indexação completa**, criar índice HNSW para busca rápida.

#### 13.1 Aumentar memória de manutenção (IMPORTANTE!)

**Problema:** Por default, `maintenance_work_mem` é pequeno (~64MB). Para índices HNSW grandes, isso causa:
- ⚠️ Warning: "hnsw graph no longer fits into maintenance_work_mem"
- ⏱️ Criação **muito mais lenta** (usa disco ao invés de RAM)

**Solução:** Aumentar antes de criar índice

```bash
PGPASSWORD=postgres123 psql -h localhost -U postgres -d ragdb << 'EOF'

-- Aumentar memória de manutenção (temporário para esta sessão)
-- 10k docs (~77k chunks): 2GB
-- 50k docs (~300k chunks): 4GB
-- 100k docs (~600k chunks): 8GB
SET maintenance_work_mem = '2GB';

-- Criar índice HNSW (melhor que IVFFlat para <1M vetores)
CREATE INDEX idx_chunks_embedding ON document_chunks 
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Analisar tabela para otimizar queries
ANALYZE document_chunks;

EOF
```

**Tempo com memória adequada:**
- 10k docs (77k chunks): ~5-10 minutos
- 50k docs (300k chunks): ~20-30 minutos

**Tempo SEM memória adequada:**
- 10k docs: ~20-30 minutos (3x mais lento)
- 50k docs: ~1-2 horas (3x mais lento)

#### 13.2 Configuração Permanente (Opcional)

Para tornar a configuração permanente:

```bash
# Editar postgresql.conf
sudo nano /etc/postgresql/16/main/postgresql.conf

# Adicionar/alterar linha:
maintenance_work_mem = 2GB  # ou 4GB para corpus maior

# Reiniciar PostgreSQL
sudo systemctl restart postgresql
```

**Recomendação:** ~25% da RAM disponível, mas não exceder 2-4GB (diminishing returns)

---

## ✅ Validação do Setup

### 1. Verificar banco de dados

```bash
PGPASSWORD=postgres123 psql -h localhost -U postgres -d ragdb -c "
SELECT 
  (SELECT COUNT(*) FROM news_documents) as docs,
  (SELECT COUNT(*) FROM document_chunks) as chunks,
  (SELECT pg_size_pretty(pg_database_size('ragdb'))) as db_size;
"
```

**Output esperado:**
```
 docs  | chunks | db_size 
-------+--------+---------
 10000 |  40000 | 2500 MB
```

### 2. Testar embedding model

```bash
cd ~/rag
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-m3')
emb = model.encode('teste')
print(f'✅ Embedding OK: dim={len(emb)}')
"
```

### 3. Testar retrieval

```bash
cd ~/rag
python scripts/test_retrieval.py --query "tilápia açude nordeste"
```

---

## 🐛 Problemas Comuns e Soluções

### Problema 1: Autenticação PostgreSQL
```
FATAL: password authentication failed for user "postgres"
```

**Solução:**
```bash
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres123';"
```

### Problema 2: Tabela não existe
```
relation "news_documents" does not exist
```

**Solução:** Execute novamente a seção 5.3 (criar schema)

### Problema 3: ON CONFLICT constraint
```
there is no unique or exclusion constraint matching the ON CONFLICT specification
```

**Solução:** Certifique-se que `url` tem constraint UNIQUE na tabela `news_documents`

### Problema 4: ModuleNotFoundError
```
ModuleNotFoundError: No module named 'src.indexing'
```

**Solução:**
```bash
export PYTHONPATH="/l/disk0/lpmoraes/rag:$PYTHONPATH"
```

### Problema 5: CUDA out of memory
```
RuntimeError: CUDA out of memory
```

**Solução:** Reduzir batch_size:
```bash
python scripts/index_corpus.py --input data/corpus_10k.json --format json --batch-size 16
```

---

## 📊 Métricas de Performance

### Indexação (GPU NVIDIA L4)
- **10k docs:** ~35 minutos (~4.7 docs/s)
- **Chunking:** ~40k chunks gerados (ratio 4:1)
- **Embeddings:** 1024 dimensões por chunk
- **Espaço:** ~2.5 GB database total

### Retrieval (após índices HNSW)
- **Latência:** 50-100ms (top-50 vetorial)
- **Throughput:** ~20 queries/s

---

## 🔐 Segurança (Produção)

### Checklist de Segurança

- [ ] Trocar senha postgres default
- [ ] Configurar firewall (apenas portas necessárias)
- [ ] Habilitar SSL no PostgreSQL
- [ ] Usar variáveis de ambiente (não hardcode)
- [ ] Restringir acesso SSH (chave privada)
- [ ] Configurar backup automático do banco
- [ ] Monitorar uso de recursos (CloudWatch)
- [ ] Limitar taxa de requisições (rate limiting)

### Configuração SSL PostgreSQL

```bash
# Editar postgresql.conf
sudo nano /etc/postgresql/16/main/postgresql.conf

# Adicionar:
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'

# Reiniciar
sudo systemctl restart postgresql
```

---

## 📝 Manutenção

### Backup do Banco

```bash
# Backup completo
PGPASSWORD=postgres123 pg_dump -h localhost -U postgres ragdb > backup_$(date +%Y%m%d).sql

# Backup comprimido
PGPASSWORD=postgres123 pg_dump -h localhost -U postgres ragdb | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restauração

```bash
PGPASSWORD=postgres123 psql -h localhost -U postgres -d ragdb < backup_20260609.sql
```

### Limpeza de Dados Antigos

```bash
PGPASSWORD=postgres123 psql -h localhost -U postgres -d ragdb << 'EOF'

-- Deletar documentos mais antigos que 2 anos
DELETE FROM news_documents 
WHERE published_at < NOW() - INTERVAL '2 years';

-- Vacuum para recuperar espaço
VACUUM FULL news_documents;
VACUUM FULL document_chunks;

EOF
```

---

## 🚀 Próximos Passos

1. [ ] Criar script `setup_ec2.sh` automatizado
2. [ ] Criar Docker image com ambiente completo
3. [ ] Configurar CI/CD para deploy automático
4. [ ] Criar Skill do Claude Code para setup rápido
5. [ ] Documentar testes de retrieval e generation
6. [ ] Criar guia de troubleshooting expandido

---

## 📚 Referências

- PostgreSQL: https://www.postgresql.org/docs/
- pgvector: https://github.com/pgvector/pgvector
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- Sentence Transformers: https://www.sbert.net/

---

**Última atualização:** 2026-06-09  
**Versão:** 1.0  
**Status:** ✅ Testado e validado com 10k documentos
