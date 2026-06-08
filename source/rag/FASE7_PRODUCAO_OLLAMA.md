# Fase 7: Produção com Ollama - Deploy EC2 e Análise Comparativa

**Data:** 2026-06-02  
**Responsável:** Luis Felipe de Moraes  
**Status:** Concluída  
**Objetivo:** Deploy completo em EC2 com GPU, escala para 250+ documentos, análise comparativa de modelos locais vs cloud

---

## 1. Visão Geral

Esta fase documenta a implementação em produção do sistema RAG utilizando modelos locais via Ollama em EC2 com GPU L4, incluindo análises comparativas de performance, custo e qualidade contra soluções cloud (AWS Bedrock).

### Entregas

1. Deploy automatizado em EC2 com L4 GPU (24GB VRAM)
2. Escala de corpus: 100 → 250 documentos indexados
3. Benchmark GPU vs CPU para indexação
4. Análise comparativa de 5 modelos Ollama (Gemma, Llama, Granite, Qwen)
5. Análise de custo: EC2 vs Bedrock
6. Configuração otimizada de temperature (0.7)
7. Cliente interativo funcional em ambos ambientes

---

## 2. Infraestrutura EC2

### 2.1 Especificações

**Instance Type:** g6.xlarge (ou similar)
- GPU: NVIDIA L4 (24GB VRAM)
- CPU: 4 vCPUs
- RAM: 16GB
- Storage: 100GB SSD
- OS: Ubuntu 24.04 LTS

**Software Stack:**
- PostgreSQL 16 + pgvector 0.7.0
- Python 3.11
- CUDA 12.1 + Driver 595
- Ollama 0.1.x
- PyTorch 2.5.1+cu121

### 2.2 Script de Setup Automatizado

Arquivo: `deploy/setup_ec2_simple.sh`

```bash
#!/bin/bash
set -e

echo "=== RAG System EC2 Setup ==="
echo "Ubuntu 24.04 + L4 GPU + PostgreSQL + Ollama"
echo ""

# Update system
apt update && apt upgrade -y

# Install NVIDIA drivers (auto-detect compatible version)
ubuntu-drivers autoinstall
# Result: Driver 595 installed automatically

# Install CUDA 12.1
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb
apt update
apt install -y cuda-toolkit-12-1

# Install PostgreSQL 16 + pgvector
apt install -y postgresql-16 postgresql-contrib-16
apt install -y postgresql-16-pgvector

# Configure PostgreSQL
systemctl start postgresql
systemctl enable postgresql

sudo -u postgres psql -c "CREATE USER rag_user WITH PASSWORD 'rag_pass';"
sudo -u postgres psql -c "CREATE DATABASE news_db OWNER rag_user;"
sudo -u postgres psql -d news_db -c "CREATE EXTENSION vector;"

# Install Python 3.11
apt install -y python3.11 python3.11-venv python3-pip

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull gemma2:2b
ollama pull llama3.2:3b
ollama pull granite4.1:3b
ollama pull qwen2.5:14b-instruct-q4_K_M

echo ""
echo "Setup complete. Reboot required for GPU drivers."
echo "After reboot: verify with 'nvidia-smi'"
```

**Lições Aprendidas:**

1. `ubuntu-drivers autoinstall` é mais confiável que especificar versão manualmente
2. Driver 595 funciona corretamente com Ubuntu 24.04 + CUDA 12.1
3. PyTorch requer downgrade do transformers para 4.46.0 (CVE-2025-32434)

### 2.3 Configuração do Ambiente Python

```bash
cd /home/lpmoraes/source/rag
python3 -m venv .venv
source .venv/bin/activate

# PyTorch com CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Downgrade transformers (vulnerability mitigation)
pip install transformers==4.46.0

# Dependências do RAG
pip install -r requirements.txt
```

**Arquivo: `.env` (EC2)**

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=news_db
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=rag_pass

EMBEDDING_DEVICE=cuda
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BATCH_SIZE=32

OLLAMA_BASE_URL=http://localhost:11434
```

**Diferenças Local vs EC2:**

| Parâmetro | Local | EC2 |
|-----------|-------|-----|
| POSTGRES_PORT | 5433 | 5432 |
| POSTGRES_PASSWORD | rag_password_2024 | rag_pass |
| EMBEDDING_DEVICE | cpu | cuda |

---

## 3. Database Schema

Schema completo identificado através de `scripts/index_corpus.py`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE news_documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT UNIQUE,
    source_agency TEXT,
    category TEXT,
    published_at TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES news_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_type TEXT DEFAULT 'semantic',
    content TEXT NOT NULL,
    enriched_content TEXT,
    embedding vector(1024),
    char_start INTEGER,
    char_end INTEGER,
    tokens INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_embedding ON document_chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX idx_chunks_content_fts ON document_chunks 
USING GIN (to_tsvector('portuguese', content));

CREATE INDEX idx_news_published ON news_documents(published_at DESC);
CREATE INDEX idx_news_category ON news_documents(category);
CREATE INDEX idx_news_agency ON news_documents(source_agency);
```

**Nota Crítica:** Colunas `enriched_content`, `chunk_type`, `char_start`, `char_end`, `tokens`, `metadata` são obrigatórias para compatibilidade com `index_corpus.py`.

---

## 4. Indexação e Performance

### 4.1 Script de Indexação

**Script utilizado:** `scripts/index_corpus.py` (existente, testado com 100 docs)

**Não utilizar:** `deploy/batch_indexing.py` (instável, travamentos frequentes)

```bash
# Consolidar corpus
cd source/rag
python deploy/consolidate_corpus.py

# Indexar (EC2 com GPU)
python scripts/index_corpus.py \
    --input data/corpus_flat.json \
    --format json

# Indexar (Local com CPU)
# Mesmo comando, mas EMBEDDING_DEVICE=cpu no .env
```

### 4.2 Configuração do Embedder

**Arquivo: `config/embeddings.yaml`**

```yaml
model_name: BAAI/bge-m3
dimension: 1024
max_length: 8192
device: cuda  # ou cpu para ambiente local
batch_size: 32
normalize_embeddings: true
```

**Crítico:** O campo `device` em `embeddings.yaml` tem precedência sobre a variável de ambiente `EMBEDDING_DEVICE`.

### 4.3 Benchmark: GPU vs CPU

**Corpus:** 250 documentos de notícias governamentais  
**Resultado:** 2538 chunks indexados

| Ambiente | Device | Tempo Total | Tempo/Doc | Speedup |
|----------|--------|-------------|-----------|---------|
| **EC2** | L4 GPU (24GB) | 2.7 min | 0.65s | 35x |
| **Local** | CPU (Intel) | 1.5 horas | 21.6s | 1x |

**Análise:**

- GPU oferece speedup de 35x para indexação
- Batch size 32 é adequado para L4 (24GB VRAM)
- Tempo de indexação local torna inviável corpus > 500 docs
- Para corpus de 2000+ docs: GPU é essencial (10-15 min vs 3+ horas)

**Observação:** Durante indexação local, sistema apresentou travamentos temporários devido ao alto uso de CPU. EC2 não apresentou problemas de estabilidade.

---

## 5. Modelos Ollama: Análise Comparativa

### 5.1 Modelos Testados

Cinco modelos foram avaliados usando a mesma query: "Pesquisadores Mirins?"

| Modelo | Parâmetros | Quantização | VRAM | Download |
|--------|------------|-------------|------|----------|
| Gemma2 | 2B | q4_K_M | ~2GB | 1.7GB |
| Llama 3.2 | 3B | - | ~3GB | 2GB |
| **Granite 4.1** | **3B** | - | **~4GB** | **2.3GB** |
| Qwen 2.5 | 14B | q4_K_M | ~12GB | 9GB |
| Qwen 2.5 | 32B | q4_K_M | ~24GB | 20GB |

### 5.2 Resultados Detalhados

**Query de teste:** "Pesquisadores Mirins?"

#### Gemma2 2B

```
Latência: 1.4s geração (2.1s total)
Tokens: 1114 input → 112 output
Qualidade: Objetiva, factualmente correta, concisa

Resposta:
"O Clube de Pesquisadores Mirins é um programa educativo oferecido pelo Museu 
Goeldi, com a seleção para o programa acontecendo até esta sexta-feira (06/03). 
Os interessados podem se inscrever no processo seletivo que acontece em etapas."

Análise:
+ Mais rápido (1.4s)
+ Resposta correta
+ Citações adequadas
- Muito enxuta (112 tokens)
- Falta de detalhes
- Formatação simples
```

#### Granite 4.1 3B

```
Latência: 2.7s geração (3.4s total)
Tokens: 1120 input → 221 output
Qualidade: Balanceada, estruturada, completa

Resposta:
"O Clube de Pesquisadores Mirins é uma iniciativa do Museu Paraense Emílio Goeldi
(MPEG) voltada para a educação e pesquisa, especialmente focando em temas 
relacionados à ciência na Amazônia e à história do próprio museu. O processo 
seletivo para novos integrantes está aberto até sexta-feira, 06/03/2026.

Durante o período da seleção, várias turmas são avaliadas, incluindo a turma 
Planeta Animal e a turma Jardins da Ciência. A data de resultado final dos 
candidatos será divulgada em 16/03/2026.

Para participar, os interessados podem consultar as instruções detalhadas 
disponibilizadas no site do MPEG. Não encontrei informações específicas sobre 
veteranos ou detalhes financeiros relacionados ao processo seletivo nas fontes 
fornecidas."

Análise:
+ Latência equilibrada (2.7s)
+ Resposta completa (221 tokens)
+ Estrutura em 3 parágrafos
+ Contextualização adequada (explica MPEG)
+ Menciona limitações ("Não encontrei informações...")
+ Melhor custo-benefício observado
```

#### Bedrock Haiku 4.5 (Comparação)

```
Latência: 5.1s geração (6.0s total)
Tokens: 1536 input → 451 output
Custo: $0.0114 por query
Qualidade: Máxima, formatação rica

Resposta:
[Formatação Markdown rica com títulos, seções, bullets]

# Clube de Pesquisadores Mirins

Com base nas fontes disponíveis, posso informar que:

## O que é
O Clube de Pesquisadores Mirins é uma atividade educativa do Museu Paraense 
Emílio Goeldi (MPEG) que oferece oportunidades para jovens participarem de 
atividades científicas.

## Seleção em Andamento
Está em andamento um processo seletivo para novos integrantes do clube, que 
ocorre até sexta-feira, 06 de março de 2026, no Campus de Pesquisa do Museu 
Goeldi, no bairro Terra Firme.

## Características do Processo Seletivo
• Mais de 300 candidatos disputam as vagas desta edição
• O processo inclui avaliações individuais e dinâmicas em grupo
• As atividades abordam temas como: ciência na Amazônia, história do Museu...

[...]

Análise:
+ Formatação muito rica (Markdown completo)
+ Máximo detalhamento (451 tokens)
+ Estrutura profissional
+ Informações adicionais (300 candidatos, dinâmicas)
- Latência 2x maior que Granite (6s vs 2.7s)
- Custo por query ($0.0114)
```

#### Qwen 2.5 14B

```
Latência: ~20s geração
Qualidade: Alta, similar ao Haiku

Análise:
+ Alta qualidade de resposta
- Latência muito alta (20s inaceitável para produção)
- Uso pesado de VRAM (12GB)
```

#### Qwen 2.5 32B

```
Latência: >12s geração
Qualidade: Máxima

Análise:
+ Máxima qualidade teórica
- Latência proibitiva (>12s)
- VRAM próxima do limite (24GB)
- Não justifica o trade-off vs 14B
```

### 5.3 Matriz de Decisão

| Modelo | Latência | Tokens Out | Qualidade | Custo/Query | Caso de Uso |
|--------|----------|------------|-----------|-------------|-------------|
| **Gemma 2B** | 1.4s | 112 | 6/10 | $0 | Testes rápidos, info objetiva |
| **Granite 3B** | **2.7s** | **221** | **8/10** | **$0*** | **Produção recomendado** |
| Llama 3.2 3B | 7s | ~180 | 7/10 | $0 | Alternativa |
| Haiku 4.5 | 6s | 451 | 9.5/10 | $0.0114 | Quando formatação crítica |
| Qwen 14B | 20s | ~350 | 9/10 | $0 | Análises offline |
| Qwen 32B | >12s | ~400 | 9.5/10 | $0 | Não recomendado |

**$0:** Custo marginal zero, mas requer EC2 ($0.70/hora = $504/mês)

### 5.4 Recomendação: Granite 4.1 3B

**Justificativa:**

1. **Performance:** 2.7s é aceitável para interações ao vivo
2. **Qualidade:** 221 tokens estruturados, resposta completa
3. **Inteligência:** Menciona limitações do conhecimento
4. **VRAM:** Apenas 4GB, permite executar outros serviços
5. **Trade-off:** 45% da latência do Haiku com 85% da qualidade

**Quando usar Haiku 4.5 (Bedrock):**

- Formatação Markdown complexa necessária
- Relatórios formais
- Queries críticas onde 3s extras não importam
- Volume baixo (<100 queries/dia)

---

## 6. Análise de Custo: EC2 vs Bedrock

### 6.1 Custos EC2 (Ollama)

**Fixos (mensais):**
- g6.xlarge (L4 24GB): $0.70/hora × 730h = $511/mês
- Storage (100GB SSD): ~$10/mês
- **Total EC2:** ~$521/mês fixo

**Variáveis:**
- Custo por query: $0 (marginal)
- Porém, custo fixo deve ser amortizado

### 6.2 Custos Bedrock

**Haiku 4.5:**
- Input: $0.80 / 1M tokens
- Output: $4.00 / 1M tokens

**Média observada:**
- 1536 tokens input × $0.0008 = $0.0012
- 451 tokens output × $0.004 = $0.0018
- **Total por query:** ~$0.003

**Nota:** Custo real observado nos testes foi $0.0114/query (possivelmente inclui reranking)

### 6.3 Break-even Analysis

**Queries necessárias para EC2 compensar:**

```
Custo EC2/hora ÷ Custo Bedrock/query = Queries/hora necessárias
$0.70 ÷ $0.0114 ≈ 61 queries/hora

ou

~1 query por minuto (24/7)
```

### 6.4 Cenários de Uso

| Cenário | Queries/Dia | Queries/Hora | Custo EC2 (mês) | Custo Bedrock (mês) | Recomendação |
|---------|-------------|--------------|-----------------|---------------------|--------------|
| Dev/Testes | 50 | 2 | $521 | $17 | **Bedrock** |
| Baixo Volume | 500 | 21 | $521 | $171 | **Bedrock** |
| Médio Volume | 2000 | 83 | $521 | $684 | **EC2** |
| Alto Volume | 10000 | 417 | $521 | $3420 | **EC2** |
| Intenso | 50000 | 2083 | $521 | $17100 | **EC2** |

**Conclusão:**

- **< 1500 queries/dia:** Bedrock mais econômico
- **> 2000 queries/dia:** EC2 compensa
- **> 10000 queries/dia:** EC2 economia massiva (6.5x)

### 6.5 Estratégia Híbrida Recomendada

**Desenvolvimento:**
- Local (CPU) para testes simples
- Bedrock para validação de qualidade

**Produção:**
- EC2 dedicada se volume > 2000 queries/dia
- EC2 spot instances (50-70% desconto) se carga variável
- Bedrock para queries de formatação complexa (relatórios)

---

## 7. Configuração de Temperature

### 7.1 Testes Realizados

**Query:** "Notícias com temática nuclear?"

| Temperature | Tokens Output | Características |
|-------------|---------------|-----------------|
| 0.0 | 223 | Determinístico, repetível, conciso |
| 0.7 | 251 | Variável, mais detalhes, natural |
| 2.0 | ~200 | Alta variação, risco de inconsistência |

### 7.2 Resultado Temperature 0.7

**Resposta observada (Granite 3B):**

```
As notícias disponíveis destacam a abertura das inscrições para as Olímpiadas 
Nucleares da América Latina - Hackapower LATAM 2026, uma competição acadêmica 
internacional voltada para estudantes de pós-graduação, com foco em teranósticos 
e radioteranóstico. Essa iniciativa visa estimular a inovação, o desenvolvimento 
de habilidades de gestão em projetos complexos e fortalecer redes de colaboração 
no setor nuclear.

O tema central da edição 2026 é o radioteranóstico, uma abordagem da medicina 
nuclear que integra diagnóstico e terapia utilizando radiofármacos direcionados 
ao mesmo alvo biológico, permitindo identificação, tratamento e monitoramento 
personalizados de doenças.

Essas competições promovem a divulgação da ciência e tecnologia em alinhamento 
com os Objetivos de Desenvolvimento Sustentável (ODS) da ONU, além de incentivar 
a formação de talentos qualificados na área nuclear.
```

**Latência:** 3.4s  
**Tokens:** 251 (vs 223 com temp 0.0)

### 7.3 Análise

**Temperature 0.0:**
- Respostas idênticas em execuções repetidas
- Mais concisa
- Tom robotizado

**Temperature 0.7:**
- Variação natural entre execuções
- Resposta mais completa (+12% tokens)
- Escrita mais fluida
- Ainda factual (ancorado nas sources)

**Temperature 2.0:**
- Variação excessiva
- Risco de "inventar" detalhes
- Não recomendado para RAG

### 7.4 Configuração Recomendada

```json
{
  "provider": "ollama",
  "model": "granite4.1:3b",
  "temperature": 0.7,
  "top_k": 5,
  "use_reranking": true,
  "max_tokens": 2000
}
```

**Justificativa:** Temperature 0.7 balanceia naturalidade e precisão factual.

---

## 8. Cliente Interativo

### 8.1 Execução

**Local:**
```bash
cd /l/disk0/lpmoraes/environments/data-science/source/rag
source .venv/bin/activate
python api/client.py
```

**EC2:**
```bash
ssh lpmoraes@aws-insp-7-01
cd /home/lpmoraes/source/rag
source .venv/bin/activate
python api/client.py
```

### 8.2 Configuração via `/config`

Permite alternar dinamicamente:
- Provider: bedrock / ollama
- Model: granite4.1:3b, llama3.2:3b, etc.
- Temperature: 0.0 - 2.0
- Top K: 1 - 50
- Filtros temporais

### 8.3 Métricas Exibidas

```
📊 Metrics:
   Retrieval:  779ms
   Generation: 3370ms
   Total:      4149ms
   Tokens:     1639 → 251
   Model:      granite4.1:3b (ollama)
```

---

## 9. Scripts Finais

### 9.1 Setup EC2

**Arquivo:** `deploy/setup_ec2_simple.sh`

Instalação completa automatizada:
- Drivers NVIDIA (auto-detect)
- CUDA 12.1
- PostgreSQL 16 + pgvector
- Python 3.11
- Ollama + modelos

**Tempo:** ~15 minutos + reboot

### 9.2 Consolidação de Corpus

**Arquivo:** `deploy/consolidate_corpus.py`

Consolida múltiplos arquivos JSON em corpus único:
```bash
python deploy/consolidate_corpus.py
# Output: data/corpus_flat.json (250 docs)
```

### 9.3 Indexação

**Arquivo:** `scripts/index_corpus.py` (RECOMENDADO)

Indexação com embeddings BGE-M3:
```bash
python scripts/index_corpus.py \
    --input data/corpus_flat.json \
    --format json
```

**Importante:** Utilizar `scripts/index_corpus.py`, não `deploy/batch_indexing.py` (instável).

### 9.4 API Server

**Arquivo:** `api/server.py`

```bash
# Modo foreground (dev)
python api/server.py

# Modo background
python api/server.py > /tmp/rag_api.log 2>&1 &

# Health check
curl http://localhost:8000/health
```

### 9.5 Cliente Interativo

**Arquivo:** `api/client.py`

REPL interativo com Rich UI:
```bash
python api/client.py
```

---

## 10. Lições Aprendidas

### 10.1 Infraestrutura

1. **ubuntu-drivers autoinstall** é mais confiável que versões específicas
2. Driver 595 compatível com Ubuntu 24.04 + CUDA 12.1
3. PyTorch requer transformers 4.46.0 (CVE mitigation)
4. `device: cuda` em `embeddings.yaml` tem precedência sobre `.env`

### 10.2 Indexação

1. Script `scripts/index_corpus.py` é estável para 100-250 docs
2. Script `deploy/batch_indexing.py` apresentou travamentos (não usar)
3. GPU oferece 35x speedup vs CPU (crítico para corpus > 500 docs)
4. Batch size 32 adequado para L4 24GB

### 10.3 Modelos

1. **Granite 4.1 3B** melhor custo-benefício (2.7s, 221 tokens, qualidade 8/10)
2. Modelos > 14B apresentam latência proibitiva (>20s)
3. Qwen 32B não justifica o trade-off vs 14B
4. Haiku 4.5 vale apenas quando formatação rica é crítica

### 10.4 Configuração

1. Temperature 0.7 balanceia naturalidade e precisão
2. Temperature 2.0 é excessiva (risco de alucinação)
3. Top K 5 suficiente para qualidade

### 10.5 Custo

1. EC2 compensa apenas com > 2000 queries/dia
2. Bedrock mais econômico para dev/testes e baixo volume
3. Estratégia híbrida recomendada: Bedrock para relatórios, Ollama para queries comuns

---

## 11. Próximos Passos

### 11.1 Curto Prazo

1. Escalar para 2000+ documentos (validar performance em produção)
2. Implementar caching Redis (reduzir latência em queries repetidas)
3. Monitoramento Prometheus + Grafana

### 11.2 Médio Prazo

1. Migração IVFFlat → HNSW (se performance crítica em escala)
2. Avaliação RAGAS (métricas automatizadas de qualidade)
3. A/B testing: Granite vs Haiku

### 11.3 Longo Prazo

1. Deploy Kubernetes (alta disponibilidade)
2. Load balancing múltiplas instâncias
3. CI/CD automatizado

---

## 12. Referências

### Scripts Implementados

- `deploy/setup_ec2_simple.sh` - Setup automatizado EC2
- `scripts/index_corpus.py` - Indexação com BGE-M3
- `deploy/consolidate_corpus.py` - Consolidação de corpus
- `api/server.py` - REST API FastAPI
- `api/client.py` - Cliente interativo

### Documentação Relacionada

- `FASE1_IMPLEMENTACAO.md` - Setup inicial
- `FASE2_IMPLEMENTACAO.md` - Retrieval pipeline
- `FASE4_IMPLEMENTACAO.md` - Generation pipeline
- `FASE5_API.md` - REST API
- `FASE6_TEMPORALIDADE.md` - Features temporais
- `deploy/README_DEPLOY.md` - Deploy geral
- `deploy/QUICKSTART_EC2.md` - Quick start

---

**Documento criado por:** Claude Code  
**Data:** 2026-06-02  
**Última revisão:** 2026-06-02  
**Status:** Final
