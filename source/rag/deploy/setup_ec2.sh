#!/bin/bash
# EC2 Setup Script for RAG System
# Ubuntu 22.04 + L4 GPU + PostgreSQL + Ollama + Python
#
# Usage: sudo ./setup_ec2.sh

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo ./setup_ec2.sh)"
    exit 1
fi

log_info "Starting EC2 setup for RAG system..."

# ============================================================================
# 1. System Update
# ============================================================================

log_info "[1/8] Updating system packages..."
apt-get update
apt-get upgrade -y
apt-get install -y \
    build-essential \
    wget \
    curl \
    git \
    vim \
    htop \
    tmux \
    software-properties-common \
    pkg-config \
    libpq-dev

# ============================================================================
# 2. NVIDIA Drivers + CUDA
# ============================================================================

log_info "[2/8] Installing NVIDIA drivers and CUDA..."

# Check if GPU exists
if ! lspci | grep -i nvidia > /dev/null; then
    log_warn "No NVIDIA GPU detected! Skipping CUDA installation."
else
    # Remove old drivers
    apt-get remove --purge -y nvidia-* || true
    apt-get autoremove -y

    # Install drivers
    ubuntu-drivers autoinstall

    # Install CUDA 12.1 (toolkit + drivers only, skip problematic nsight)
    if ! command -v nvcc &> /dev/null; then
        log_info "Installing CUDA 12.1..."

        # Add CUDA repo
        wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
        dpkg -i cuda-keyring_1.0-1_all.deb
        apt-get update

        # Install only essential components (avoid nsight-systems that requires libtinfo5)
        apt-get install -y cuda-toolkit-12-1 cuda-drivers-550 || {
            log_warn "Failed to install CUDA via apt, trying alternative method..."

            # Install libtinfo5 for Ubuntu 24.04 compatibility
            wget -q http://archive.ubuntu.com/ubuntu/pool/universe/n/ncurses/libtinfo5_6.3-2ubuntu0.1_amd64.deb
            dpkg -i libtinfo5_6.3-2ubuntu0.1_amd64.deb || true

            # Retry CUDA installation
            apt-get install -y cuda-toolkit-12-1 cuda-drivers-550
        }

        # Add to PATH (for both ubuntu and lpmoraes users)
        for user in ubuntu lpmoraes; do
            if id "$user" &>/dev/null; then
                echo 'export PATH=/usr/local/cuda-12.1/bin:$PATH' >> /home/$user/.bashrc
                echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64:$LD_LIBRARY_PATH' >> /home/$user/.bashrc
            fi
        done

        rm -f cuda-keyring_1.0-1_all.deb libtinfo5_*.deb

        log_info "CUDA installed. Reboot may be required!"

        # Check if reboot needed
        if ! nvidia-smi &>/dev/null; then
            log_warn "GPU not detected yet. Reboot required!"
            log_warn "Run 'sudo reboot' and then re-run this script."
            exit 0
        fi
    else
        log_info "CUDA already installed: $(nvcc --version | grep release)"
    fi
fi

# ============================================================================
# 3. PostgreSQL 16 + pgvector
# ============================================================================

log_info "[3/8] Installing PostgreSQL 16 + pgvector..."

if ! command -v psql &> /dev/null; then
    # Add PostgreSQL repo
    sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
    wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

    apt-get update
    apt-get install -y postgresql-16 postgresql-contrib-16

    log_info "PostgreSQL 16 installed"
else
    log_info "PostgreSQL already installed"
fi

# Install pgvector
if ! sudo -u postgres psql -c '\dx' | grep -q vector; then
    log_info "Installing pgvector..."

    apt-get install -y postgresql-server-dev-16

    # Clone and build pgvector
    cd /tmp
    git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git
    cd pgvector
    make
    make install
    cd ..
    rm -rf pgvector

    log_info "pgvector installed"
else
    log_info "pgvector already installed"
fi

# Start PostgreSQL
systemctl enable postgresql
systemctl start postgresql

# ============================================================================
# 4. Python 3.11
# ============================================================================

log_info "[4/8] Installing Python 3.11..."

if ! command -v python3.11 &> /dev/null; then
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update
    apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

    # Set as default
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

    log_info "Python 3.11 installed"
else
    log_info "Python 3.11 already installed"
fi

# ============================================================================
# 5. Ollama
# ============================================================================

log_info "[5/8] Installing Ollama..."

if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh

    # Start Ollama service
    systemctl enable ollama
    systemctl start ollama

    log_info "Ollama installed"
else
    log_info "Ollama already installed"
fi

# Pull Qwen models
log_info "Pulling Qwen models (this may take 10-20 minutes)..."

if ! ollama list | grep -q "qwen2.5:14b"; then
    log_info "Pulling Qwen 2.5:14B (~8GB)..."
    ollama pull qwen2.5:14b
fi

if ! ollama list | grep -q "qwen2.5:32b"; then
    log_info "Pulling Qwen 2.5:32B (~20GB)..."
    ollama pull qwen2.5:32b
fi

log_info "Qwen models ready:"
ollama list

# ============================================================================
# 6. Setup PostgreSQL Database
# ============================================================================

log_info "[6/8] Setting up PostgreSQL database..."

# Create user and database
sudo -u postgres psql <<EOF
-- Drop if exists (clean start)
DROP DATABASE IF EXISTS news_db;
DROP USER IF EXISTS rag_user;

-- Create user
CREATE USER rag_user WITH PASSWORD 'rag_pass';

-- Create database
CREATE DATABASE news_db OWNER rag_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE news_db TO rag_user;
EOF

# Enable pgvector extension
sudo -u postgres psql -d news_db <<EOF
CREATE EXTENSION IF NOT EXISTS vector;
EOF

# Create schema
sudo -u postgres psql -d news_db -U rag_user <<'EOF'
-- News documents table
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

-- Document chunks table (with embeddings)
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES news_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1024),  -- BGE-M3 dimension
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_news_category ON news_documents(category);
CREATE INDEX IF NOT EXISTS idx_news_agency ON news_documents(source_agency);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_documents(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_metadata ON news_documents USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);

-- IVFFlat index for vector search (will be created after data load)
-- CREATE INDEX idx_chunks_embedding ON document_chunks
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Grant permissions
GRANT ALL ON news_documents TO rag_user;
GRANT ALL ON document_chunks TO rag_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rag_user;
EOF

log_info "Database schema created"

# ============================================================================
# 7. Python Environment Setup
# ============================================================================

log_info "[7/8] Setting up Python virtual environment..."

RAG_DIR="/home/ubuntu/rag-system/source/rag"

if [ ! -d "$RAG_DIR" ]; then
    log_warn "RAG directory not found at $RAG_DIR"
    log_warn "Please clone the repository first:"
    log_warn "  git clone <repo-url> /home/ubuntu/rag-system"
    log_warn "Then re-run this script"
else
    cd $RAG_DIR

    # Create venv
    if [ ! -d ".venv" ]; then
        python3.11 -m venv .venv
        log_info "Virtual environment created"
    fi

    # Activate and install dependencies
    source .venv/bin/activate

    pip install --upgrade pip

    # Install PyTorch with CUDA support
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

    # Install other dependencies
    pip install \
        sentence-transformers \
        psycopg[binary] \
        fastapi \
        uvicorn[standard] \
        pydantic \
        numpy \
        rich \
        requests \
        boto3

    log_info "Python dependencies installed"

    # Change ownership to ubuntu user
    chown -R ubuntu:ubuntu /home/ubuntu/rag-system
fi

# ============================================================================
# 8. Systemd Service for API
# ============================================================================

log_info "[8/8] Creating systemd service for RAG API..."

cat > /etc/systemd/system/rag-api.service <<'EOF'
[Unit]
Description=RAG Q&A API Server
After=network.target postgresql.service ollama.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/rag-system/source/rag
Environment="PATH=/home/ubuntu/rag-system/source/rag/.venv/bin:/usr/local/cuda-12.1/bin:/usr/bin"
Environment="LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64"
ExecStart=/home/ubuntu/rag-system/source/rag/.venv/bin/python api/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rag-api

log_info "Systemd service created (use 'systemctl start rag-api' to start)"

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  Setup Complete! ✓                           ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Components Installed:                                       ║"
echo "║    ✓ NVIDIA Drivers + CUDA 12.1                             ║"
echo "║    ✓ PostgreSQL 16 + pgvector                               ║"
echo "║    ✓ Python 3.11 + virtualenv                               ║"
echo "║    ✓ Ollama + Qwen 2.5 (14B + 32B)                          ║"
echo "║    ✓ RAG API systemd service                                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "  1. Verify GPU:"
echo "     nvidia-smi"
echo ""
echo "  2. Test Ollama:"
echo "     ollama run qwen2.5:14b 'Hello!'"
echo ""
echo "  3. Index documents:"
echo "     cd /home/ubuntu/rag-system/source/rag"
echo "     source .venv/bin/activate"
echo "     python deploy/consolidate_corpus.py"
echo "     python deploy/batch_indexing.py --gpu"
echo ""
echo "  4. Start API:"
echo "     sudo systemctl start rag-api"
echo "     curl http://localhost:8000/health"
echo ""
echo "  5. Run benchmark:"
echo "     python deploy/benchmark_qwen.py"
echo ""
