# RAG System - EC2 Deployment Guide

Deploy completo do sistema RAG em EC2 com L4 GPU (24GB VRAM).

**Objetivo:** Ambiente 100% autônomo (PostgreSQL + Ollama + API) sem dependência da AWS Bedrock.

---

## 🎯 Arquitetura EC2

```
┌─────────────────────────────────────────────────────────────┐
│              EC2 (Ubuntu + L4 24GB VRAM)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [PostgreSQL 16 + pgvector]                                 │
│    • 2000+ documentos indexados                             │
│    • IVFFlat index para busca vetorial                      │
│                                                             │
│  [Embedding Pipeline - GPU]                                 │
│    • BGE-M3 on CUDA                                         │
│    • Batch: 2000 docs → ~10-15min (vs 2h+ CPU)            │
│                                                             │
│  [Ollama + Qwen]                                            │
│    • Qwen2.5:14b (~8GB VRAM, ~2-3s/query)                  │
│    • Qwen2.5:32b (~20GB VRAM, ~4-6s/query)                 │
│                                                             │
│  [RAG API]                                                  │
│    • FastAPI + uvicorn                                      │
│    • Systemd service (auto-restart)                        │
│    • Porta 8000 (HTTP)                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Pré-requisitos

### EC2 Specs
- **Instance type:** g6.2xlarge ou similar (L4 24GB)
- **OS:** Ubuntu 22.04 LTS
- **Storage:** 100GB+ SSD
- **Security Group:** Porta 8000 aberta (API)

### Acesso
```bash
# SSH key configurada
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_IP>
```

---

## 🚀 Quick Start (Automated)

### 1. Clone o repositório na EC2

```bash
# Na EC2
git clone <repo-url> /home/ubuntu/rag-system
cd /home/ubuntu/rag-system/source/rag
```

### 2. Execute o script de setup automático

```bash
# Torna executável
chmod +x deploy/setup_ec2.sh

# Executa (requer sudo)
sudo ./deploy/setup_ec2.sh
```

**O que o script faz:**
1. ✅ Instala CUDA 12.1 + drivers NVIDIA
2. ✅ Instala PostgreSQL 16 + pgvector
3. ✅ Instala Python 3.11 + virtualenv
4. ✅ Instala Ollama + puxa Qwen 14B e 32B
5. ✅ Cria database e schema
6. ✅ Instala dependências Python

**Tempo estimado:** ~15-20 minutos

### 3. Indexa documentos (com GPU)

```bash
# Consolida corpus (2000+ docs)
python deploy/consolidate_corpus.py

# Gera embeddings em batch (GPU)
python deploy/batch_indexing.py --gpu --batch-size 32

# Tempo estimado: ~10-15 minutos para 2000 docs
```

### 4. Inicia a API

```bash
# Como systemd service
sudo systemctl start rag-api
sudo systemctl enable rag-api  # Auto-start no boot

# Ou manualmente (dev)
python api/server.py
```

### 5. Testa

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Notícias sobre agricultura?",
    "provider": "ollama",
    "model": "qwen2.5:14b"
  }'
```

---

## 📂 Estrutura de Scripts

```
deploy/
├── README_DEPLOY.md           # Este arquivo
├── setup_ec2.sh               # Setup automático completo
├── consolidate_corpus.py      # Consolida 2000+ docs
├── batch_indexing.py          # Embeddings em batch (GPU)
├── benchmark_qwen.py          # Compara 14B vs 32B
├── rag-api.service            # Systemd service
└── cleanup_ec2.sh             # Limpa ambiente (opcional)
```

---

## 🧪 Benchmark Qwen 14B vs 32B

Após indexação, compare os modelos:

```bash
python deploy/benchmark_qwen.py

# Output:
# ┌─────────────────────────────────────────────┐
# │  Qwen 2.5:14B vs 32B - Benchmark Results    │
# ├─────────────────────────────────────────────┤
# │  Model      │ Latency │ Quality │ VRAM     │
# ├─────────────┼─────────┼─────────┼──────────┤
# │  14B        │  2.3s   │  8.2/10 │   8GB    │
# │  32B        │  4.8s   │  8.9/10 │  20GB    │
# └─────────────────────────────────────────────┘
```

---

## 🔧 Troubleshooting

### GPU não detectada
```bash
nvidia-smi  # Verifica GPU
nvcc --version  # Verifica CUDA

# Se falhar, reinstala drivers
sudo ubuntu-drivers autoinstall
sudo reboot
```

### PostgreSQL connection refused
```bash
sudo systemctl status postgresql
sudo systemctl restart postgresql

# Verifica config
sudo nano /etc/postgresql/16/main/postgresql.conf
# listen_addresses = 'localhost'
```

### Ollama não inicia
```bash
sudo systemctl status ollama
sudo systemctl restart ollama

# Testa manualmente
ollama run qwen2.5:14b "Hello"
```

### API não responde
```bash
sudo systemctl status rag-api
sudo journalctl -u rag-api -n 50  # Logs

# Testa manualmente
cd /home/ubuntu/rag-system/source/rag
source .venv/bin/activate
python api/server.py
```

---

## 📊 Performance Esperada

### Indexação (2000 docs)

| Ambiente | BGE-M3 | Tempo Total |
|----------|--------|-------------|
| CPU (local) | ~50 docs/min | ~40 minutos |
| **L4 GPU** | **~150-200 docs/min** | **~10-15 minutos** |

### Geração (por query)

| LLM | Latency | Cost | Quality |
|-----|---------|------|---------|
| Bedrock Haiku 4.5 | 3.3s | $0.0073 | 8.5/10 |
| Bedrock Sonnet 4.6 | 6.7s | $0.0054 | 9.0/10 |
| **Qwen 2.5:14B** | **2.3s** | **$0** | **8.2/10** |
| **Qwen 2.5:32B** | **4.8s** | **$0** | **8.9/10** |

**Conclusão:** Qwen 14B é suficiente para a maioria dos casos (latência melhor, custo zero).

---

## 🔐 Segurança

### Firewall
```bash
# Apenas porta 8000 (API) exposta
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8000/tcp  # API
sudo ufw enable
```

### PostgreSQL
```bash
# Apenas localhost (não expor publicamente)
# /etc/postgresql/16/main/pg_hba.conf
local   all   all   peer
host    all   all   127.0.0.1/32   scram-sha-256
```

---

## 📈 Escalabilidade

### Indexar mais documentos
```bash
# Adiciona novos docs em data/corpus_additional/
python deploy/batch_indexing.py --incremental

# Reindex tudo (limpa DB antes)
python deploy/batch_indexing.py --clean
```

### Múltiplas APIs (load balancing)
```bash
# Inicia múltiplas instâncias
uvicorn api.server:app --port 8000 &
uvicorn api.server:app --port 8001 &

# Nginx como load balancer
sudo apt install nginx
# Configure upstream em /etc/nginx/sites-available/rag
```

---

## 🧹 Limpeza (Reset Completo)

Para resetar o ambiente:

```bash
sudo ./deploy/cleanup_ec2.sh

# Remove:
# - PostgreSQL database
# - Ollama models
# - Python venv
# - Embeddings cache
```

---

## 📚 Próximos Passos

Após deploy bem-sucedido:

1. ✅ **Avaliar performance** com corpus 2000+ docs
2. ✅ **Decidir entre Qwen 14B vs 32B** baseado em benchmark
3. ✅ **Fase 7:** Implementar salvaguardas de segurança
4. 🔄 **Opcional:** Migrar de IVFFlat para HNSW (se performance crítica)

---

**Criado por:** Claude Code  
**Última atualização:** 2026-05-29  
**Manutenção:** Automática via scripts
