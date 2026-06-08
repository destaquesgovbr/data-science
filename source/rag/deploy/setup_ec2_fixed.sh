#!/bin/bash
#
# Setup EC2 para RAG System - Baseado em issue3 (testado e funcional)
# AWS G6 instance com L4 GPU
#
# Usage: sudo bash setup_ec2_fixed.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo "================================================================================"
echo "SETUP EC2 - RAG SYSTEM (com GPU L4)"
echo "================================================================================"
echo ""

# ============================================================================
# 1. Verificar GPU e instalar drivers
# ============================================================================

log_info "[1/7] Verificando GPU..."

if ! command -v nvidia-smi &> /dev/null; then
    log_warn "nvidia-smi não encontrado. Instalando drivers NVIDIA 560..."
    apt update
    apt install -y nvidia-driver-560
    log_info "Driver instalado. REINICIANDO EM 5 SEGUNDOS..."
    sleep 5
    reboot
    exit 0
fi

nvidia-smi
echo ""

# ============================================================================
# 2. PostgreSQL 16 + pgvector
# ============================================================================

log_info "[2/7] Instalando PostgreSQL 16 + pgvector..."

if ! command -v psql &> /dev/null; then
    # Add PostgreSQL repo
    sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
    wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

    apt update
    apt install -y postgresql-16 postgresql-contrib-16 postgresql-server-dev-16

    log_info "PostgreSQL 16 instalado"
fi

# Install pgvector
if ! sudo -u postgres psql -c '\dx' | grep -q vector; then
    cd /tmp
    git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git
    cd pgvector
    make
    make install
    cd ..
    rm -rf pgvector
    log_info "pgvector instalado"
fi

systemctl enable postgresql
systemctl start postgresql

# ============================================================================
# 3. Python 3.11
# ============================================================================

log_info "[3/7] Instalando Python 3.11..."

if ! command -v python3.11 &> /dev/null; then
    add-apt-repository -y ppa:deadsnakes/ppa
    apt update
    apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

    log_info "Python 3.11 instalado"
fi

# ============================================================================
# 4. Ollama + Qwen
# ============================================================================

log_info "[4/7] Instalando Ollama..."

if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
    systemctl enable ollama
    systemctl start ollama
    log_info "Ollama instalado"
fi

log_info "Baixando Qwen models (10-20 minutos)..."

if ! ollama list | grep -q "qwen2.5:14b"; then
    log_info "Pulling Qwen 2.5:14B..."
    ollama pull qwen2.5:14b
fi

if ! ollama list | grep -q "qwen2.5:32b"; then
    log_info "Pulling Qwen 2.5:32B..."
    ollama pull qwen2.5:32b
fi

ollama list

# ============================================================================
# 5. Setup PostgreSQL Database
# ============================================================================

log_info "[5/7] Configurando database..."

sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS news_db;
DROP USER IF EXISTS rag_user;

CREATE USER rag_user WITH PASSWORD 'rag_pass';
CREATE DATABASE news_db OWNER rag_user;
GRANT ALL PRIVILEGES ON DATABASE news_db TO rag_user;
EOF

sudo -u postgres psql -d news_db <<EOF
CREATE EXTENSION IF NOT EXISTS vector;
EOF

sudo -u postgres psql -d news_db <<'EOF'
CREATE TABLE IF NOT EXISTS news_documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT UNIQUE,
    source_agency TEXT,
    category TEXT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES news_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1024),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_category ON news_documents(category);
CREATE INDEX IF NOT EXISTS idx_news_agency ON news_documents(source_agency);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_documents(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);

GRANT ALL ON news_documents TO rag_user;
GRANT ALL ON document_chunks TO rag_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rag_user;
EOF

log_info "Database configurado"

# ============================================================================
# 6. Python Environment (como lpmoraes)
# ============================================================================

log_info "[6/7] Configurando ambiente Python..."

RAG_DIR="/home/lpmoraes/rag-system/source/rag"

if [ -d "$RAG_DIR" ]; then
    cd $RAG_DIR

    # Create venv as lpmoraes user
    sudo -u lpmoraes python3.11 -m venv .venv

    # Install dependencies
    sudo -u lpmoraes bash -c "
        source .venv/bin/activate
        pip install --upgrade pip
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        pip install sentence-transformers psycopg[binary] fastapi uvicorn[standard] pydantic numpy rich requests boto3
    "

    chown -R lpmoraes:lpmoraes $RAG_DIR

    log_info "Ambiente Python configurado"
else
    log_warn "Diretório RAG não encontrado: $RAG_DIR"
    log_warn "Execute depois: git clone <repo> /home/lpmoraes/rag-system"
fi

# ============================================================================
# 7. Systemd Service
# ============================================================================

log_info "[7/7] Criando systemd service..."

cat > /etc/systemd/system/rag-api.service <<'EOF'
[Unit]
Description=RAG Q&A API Server
After=network.target postgresql.service ollama.service

[Service]
Type=simple
User=lpmoraes
WorkingDirectory=/home/lpmoraes/rag-system/source/rag
Environment="PATH=/home/lpmoraes/rag-system/source/rag/.venv/bin:/usr/local/cuda/bin:/usr/bin"
Environment="LD_LIBRARY_PATH=/usr/local/cuda/lib64"
ExecStart=/home/lpmoraes/rag-system/source/rag/.venv/bin/python api/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rag-api

log_info "Systemd service criado"

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "================================================================================"
echo "✅ SETUP CONCLUÍDO!"
echo "================================================================================"
echo ""
echo "Componentes instalados:"
echo "  ✓ NVIDIA Driver 560 + GPU L4"
echo "  ✓ PostgreSQL 16 + pgvector"
echo "  ✓ Python 3.11 + PyTorch (CUDA)"
echo "  ✓ Ollama + Qwen 2.5 (14B + 32B)"
echo "  ✓ Systemd service (rag-api)"
echo ""
echo "Próximos passos:"
echo ""
echo "1. Verificar GPU:"
echo "   nvidia-smi"
echo ""
echo "2. Consolidar corpus:"
echo "   cd /home/lpmoraes/rag-system/source/rag"
echo "   source .venv/bin/activate"
echo "   python deploy/consolidate_corpus.py"
echo ""
echo "3. Indexar documentos (GPU):"
echo "   python deploy/batch_indexing.py --gpu --batch-size 32"
echo ""
echo "4. Iniciar API:"
echo "   sudo systemctl start rag-api"
echo "   curl http://localhost:8000/health"
echo ""
