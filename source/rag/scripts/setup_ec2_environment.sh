#!/usr/bin/env bash
#
# Setup EC2 Environment for RAG System
#
# Usage:
#   ./setup_ec2_environment.sh
#
# Description:
#   Automated setup script for EC2 instance to run RAG Q&A system.
#   Installs all dependencies, configures PostgreSQL, creates database schema.
#
# Requirements:
#   - Ubuntu 24.04 LTS
#   - sudo access
#   - Internet connection
#
# Author: Luis Felipe de Moraes
# Date: 2026-06-09

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres123}"
DATABASE_NAME="${DATABASE_NAME:-ragdb}"
RAG_HOME="${RAG_HOME:-$HOME/rag}"

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  RAG System - EC2 Environment Setup${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# Function to print step
step() {
    echo -e "${YELLOW}==>${NC} $1"
}

# Function to print success
success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error
error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if running on Ubuntu
if ! grep -q "Ubuntu" /etc/os-release; then
    error "This script requires Ubuntu. Exiting."
    exit 1
fi

# 1. Update system
step "Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential git wget curl
success "System updated"

# 2. Install Python 3.12+
step "Checking Python version..."
PYTHON_VERSION=$(python3 --version | awk '{print $2}' | cut -d. -f1,2)
if (( $(echo "$PYTHON_VERSION < 3.12" | bc -l) )); then
    error "Python 3.12+ required. Current: $PYTHON_VERSION"
    step "Installing Python 3.12..."
    sudo apt install -y python3 python3-pip python3-venv
fi
success "Python $(python3 --version) installed"

# 3. Install PostgreSQL
step "Installing PostgreSQL..."
if ! command -v psql &> /dev/null; then
    sudo apt install -y postgresql postgresql-contrib postgresql-server-dev-all
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    success "PostgreSQL installed"
else
    success "PostgreSQL already installed"
fi

# 4. Install pgvector
step "Installing pgvector extension..."
if ! sudo -u postgres psql -c "SELECT * FROM pg_extension WHERE extname='vector';" | grep -q vector; then
    cd /tmp
    if [ ! -d "pgvector" ]; then
        git clone https://github.com/pgvector/pgvector.git
    fi
    cd pgvector
    make clean
    make
    sudo make install
    success "pgvector installed"
else
    success "pgvector already installed"
fi

# 5. Configure PostgreSQL
step "Configuring PostgreSQL..."

# Set postgres password
sudo -u postgres psql -c "ALTER USER postgres PASSWORD '$POSTGRES_PASSWORD';" || true
success "PostgreSQL password set"

# Create database
step "Creating database '$DATABASE_NAME'..."
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U postgres -c "CREATE DATABASE $DATABASE_NAME;" 2>/dev/null || \
    echo "Database '$DATABASE_NAME' already exists"
success "Database ready"

# 6. Create database schema
step "Creating database schema..."
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U postgres -d $DATABASE_NAME << 'EOF'

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop existing tables (fresh start)
DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS news_documents CASCADE;

-- Documents table
CREATE TABLE news_documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT UNIQUE,
    source_agency TEXT,
    category TEXT,
    published_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB,
    indexed_at TIMESTAMP DEFAULT NOW()
);

-- Chunks table
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

-- Indexes
CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_documents_category ON news_documents(category);
CREATE INDEX idx_documents_url ON news_documents(url);
CREATE INDEX idx_documents_published ON news_documents(published_at);

EOF

success "Database schema created"

# 7. Create directory structure
step "Creating directory structure..."
mkdir -p "$RAG_HOME"/{data,scripts,src,config,logs,models}
success "Directories created at $RAG_HOME"

# 8. Setup Python environment
step "Setting up Python virtual environment..."
cd "$RAG_HOME"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

step "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -q sentence-transformers psycopg[binary] pyyaml rich tqdm python-dotenv

# Check for GPU
if command -v nvidia-smi &> /dev/null; then
    step "GPU detected, installing CUDA-enabled torch..."
    pip install -q torch --index-url https://download.pytorch.org/whl/cu121
    success "CUDA torch installed"
else
    step "No GPU detected, installing CPU torch..."
    pip install -q torch
    success "CPU torch installed"
fi

success "Python environment ready"

# 9. Create .env file
step "Creating .env configuration..."
cat > "$RAG_HOME/.env" << EOF
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=$DATABASE_NAME
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# Embeddings
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024
EMBEDDING_DEVICE=cuda

# Retrieval
IVFFLAT_PROBES=10
VECTOR_SEARCH_TOP_K=50
FULLTEXT_SEARCH_TOP_K=50

# Indexing
BATCH_SIZE=32
SKIP_EXISTING=true
EOF

success ".env file created"

# 10. Configure PYTHONPATH
step "Configuring PYTHONPATH..."
if ! grep -q "PYTHONPATH.*$RAG_HOME" ~/.bashrc; then
    echo "export PYTHONPATH=\"$RAG_HOME:\$PYTHONPATH\"" >> ~/.bashrc
fi
export PYTHONPATH="$RAG_HOME:$PYTHONPATH"
success "PYTHONPATH configured"

# 11. Summary
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Setup Complete! 🎉${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Summary:"
echo "  ✓ PostgreSQL installed and configured"
echo "  ✓ Database '$DATABASE_NAME' created with pgvector"
echo "  ✓ Python environment ready at $RAG_HOME/.venv"
echo "  ✓ Directory structure created"
echo ""
echo "Next steps:"
echo "  1. Transfer files from local:"
echo "     scp -r source/rag/{scripts,src,config} user@ec2:$RAG_HOME/"
echo ""
echo "  2. Transfer corpus data:"
echo "     scp source/rag/data/corpus_10k.json user@ec2:$RAG_HOME/data/"
echo ""
echo "  3. Activate environment and index:"
echo "     cd $RAG_HOME"
echo "     source .venv/bin/activate"
echo "     export PYTHONPATH=\"$RAG_HOME:\$PYTHONPATH\""
echo "     python scripts/index_corpus.py --input data/corpus_10k.json --format json"
echo ""
echo "Database credentials saved in: $RAG_HOME/.env"
echo ""
