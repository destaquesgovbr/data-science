# Checklist de Validação: Reconstrução do Zero

**Data:** 2026-06-11  
**Objetivo:** Validar documentação reconstruindo ambiente EC2 do zero  
**Status:** 🔄 EM ANDAMENTO

---

## 📋 ETAPAS DE VALIDAÇÃO

### ✅ Etapa 0: Limpeza Completa
**Status:** ✅ **VALIDADO**  
**Comando:**
```bash
rm -rf ~/rag* ~/embeddings ~/finetuning-env ~/data-science
rm -f ~/ec2_*.sh ~/setup*.sh ~/CLAUDE.md ~/rag-*.tar.gz
DROP DATABASE ragdb, news_db;
```
**Resultado:** EC2 completamente limpa, apenas configs do sistema restantes  
**Validado em:** 2026-06-11 13:03

---

### 🔄 Etapa 1: Transferência de Arquivos (LOCAL → EC2)
**Status:** 🔄 EM PROGRESSO  
**Documento:** N/A (pré-requisito)  
**Comandos:**
```bash
# No LOCAL
ssh lpmoraes@aws-insp-7-01 "mkdir -p ~/rag/{data,scripts,src,config}"
scp source/rag/scripts/setup_ec2_environment.sh lpmoraes@aws-insp-7-01:~/rag/scripts/
scp source/rag/scripts/create_database_schema.sql lpmoraes@aws-insp-7-01:~/rag/scripts/
scp source/rag/src/*.py lpmoraes@aws-insp-7-01:~/rag/src/
scp source/rag/config/*.yaml lpmoraes@aws-insp-7-01:~/rag/config/
scp source/rag/data/corpus_10k.json lpmoraes@aws-insp-7-01:~/rag/data/
```
**Esperado:** Arquivos transferidos sem erros  
**Validado em:** PENDENTE

---

### ⏳ Etapa 2: Setup Automatizado
**Status:** ⏳ AGUARDANDO  
**Documento:** `source/rag/scripts/setup_ec2_environment.sh`  
**Comandos:**
```bash
# Na EC2
cd ~/rag/scripts
chmod +x setup_ec2_environment.sh
sudo ./setup_ec2_environment.sh
```
**Esperado:**
- PostgreSQL instalado ✓
- pgvector instalado ✓
- Banco `ragdb` criado ✓
- Schema aplicado ✓
- Python venv criado em `~/rag/.venv/` ✓
- Dependências instaladas ✓
- .env configurado ✓
**Tempo estimado:** 3-5 minutos  
**Validado em:** PENDENTE

---

### ⏳ Etapa 3: Validação do Setup
**Status:** ⏳ AGUARDANDO  
**Documento:** `docs/05_issue5_rag/deploy/SETUP_EC2_COMPLETO.md` - Seção "Validação"  
**Comandos:**
```bash
# Verificar PostgreSQL
PGPASSWORD=postgres123 psql -h localhost -U postgres -d ragdb -c "SELECT version();"

# Verificar tabelas
PGPASSWORD=postgres123 psql -h localhost -U postgres -d ragdb -c "\dt"

# Verificar Python
cd ~/rag
source .venv/bin/activate
python -c "import psycopg, sentence_transformers; print('✅ Libs OK')"
```
**Esperado:**
- PostgreSQL rodando ✓
- Tabelas: news_documents, document_chunks ✓
- Python libs instaladas ✓
**Validado em:** PENDENTE

---

### ⏳ Etapa 4: Indexação de 10k Documentos
**Status:** ⏳ AGUARDANDO  
**Documento:** `docs/05_issue5_rag/deploy/SETUP_EC2_COMPLETO.md` - Seção 12  
**Comandos:**
```bash
cd ~/rag
source .venv/bin/activate
export PYTHONPATH="/l/disk0/lpmoraes/rag:$PYTHONPATH"
python scripts/index_corpus.py --input data/corpus_10k.json --format json
```
**Esperado:**
- 10,000 documentos indexados ✓
- ~77,630 chunks criados ✓
- 0 falhas ✓
**Tempo estimado:** 2h44min  
**Validado em:** PENDENTE

---

### ⏳ Etapa 5: Criar Índice HNSW (COM Otimização)
**Status:** ⏳ AGUARDANDO  
**Documento:** `docs/05_issue5_rag/deploy/SETUP_EC2_COMPLETO.md` - Seção 13  
**Comandos:**
```bash
PGPASSWORD=postgres123 psql -h localhost -U postgres -d ragdb << 'EOF'
SET maintenance_work_mem = '2GB';
CREATE INDEX idx_chunks_embedding ON document_chunks 
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
ANALYZE document_chunks;
EOF
```
**Esperado:**
- Índice criado sem warning ✓
- Tempo ~5-10 min (não 20 min) ✓
**Tempo estimado:** 5-10 minutos  
**Validado em:** PENDENTE

---

### ⏳ Etapa 6: Teste de Retrieval
**Status:** ⏳ AGUARDANDO  
**Documento:** `docs/05_issue5_rag/deploy/SETUP_EC2_COMPLETO.md` - Seção "Validação"  
**Comandos:**
```bash
cd ~/rag
source .venv/bin/activate
export PYTHONPATH="/l/disk0/lpmoraes/rag:$PYTHONPATH"

# Teste básico Python
python << 'EOF'
import psycopg
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('BAAI/bge-m3', device='cuda')
query_emb = model.encode('tilápia açude nordeste')

conn = psycopg.connect('host=localhost dbname=ragdb user=postgres password=postgres123')
cur = conn.cursor()

cur.execute("""
    SELECT id, content, embedding <=> %s::vector as distance
    FROM document_chunks
    ORDER BY distance
    LIMIT 5
""", (query_emb.tolist(),))

print('Top 5 resultados:')
for i, row in enumerate(cur.fetchall(), 1):
    print(f'{i}. [{row[2]:.4f}] {row[1][:80]}...')
conn.close()
EOF
```
**Esperado:**
- Retrieval funciona ✓
- Latência ~700-1000ms ✓
- Resultados relevantes ✓
**Validado em:** PENDENTE

---

### ⏳ Etapa 7: Transferir e Testar API
**Status:** ⏳ AGUARDANDO  
**Documento:** `docs/05_issue5_rag/api/GUIA_PROMPTS_API.md`  
**Comandos:**
```bash
# Transferir API do backup ou outro local
# TBD - definir fonte da API

# Iniciar servidor
cd ~/rag-system/source/rag  # ou onde ficar
source .venv/bin/activate
python api/server.py &

# Testar
curl http://localhost:8000/health
```
**Esperado:**
- API inicia sem erros ✓
- Health check retorna 200 ✓
**Validado em:** PENDENTE

---

### ⏳ Etapa 8: Teste End-to-End com Prompts
**Status:** ⏳ AGUARDANDO  
**Documento:** `docs/05_issue5_rag/api/GUIA_PROMPTS_API.md`  
**Comandos:**
```bash
# Cliente interativo
python api/client.py

# Testar queries:
# 1. "programas para pescadores" (default)
# 2. "Qual o valor do Plano Safra?" (factual)
# 3. "Resuma políticas de educação" (summary)
```
**Esperado:**
- Cliente funciona ✓
- 4 templates disponíveis ✓
- Respostas úteis (não "não encontrei" excessivo) ✓
- Latência ~1-3s total ✓
**Validado em:** PENDENTE

---

## 📊 Progresso Geral

- **Concluídas:** 1/8 (12.5%)
- **Em progresso:** 1/8 (12.5%)
- **Pendentes:** 6/8 (75%)

---

## 🐛 Problemas Encontrados Durante Validação

### Problema 1
**Etapa:** PENDENTE  
**Descrição:** PENDENTE  
**Solução:** PENDENTE  
**Doc atualizado:** PENDENTE

---

## ✅ Conclusão Final

**Status:** PENDENTE  
**Data conclusão:** PENDENTE  

**Documentação validada:**
- [ ] setup_ec2_environment.sh funciona
- [ ] SETUP_EC2_COMPLETO.md está correto
- [ ] create_database_schema.sql funciona
- [ ] GUIA_PROMPTS_API.md está correto
- [ ] Processo é reproduzível por terceiros

**Próximos passos:** PENDENTE
