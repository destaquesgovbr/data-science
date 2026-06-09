# Log de Execução: Escala 250 → 10k Notícias

**Data:** 2026-06-09  
**Objetivo:** Indexar 10k notícias e avaliar performance vs baseline 250

---

## ✅ Passo 1: Extração (COMPLETO)

**Tempo:** ~5 minutos  
**Arquivo:** `source/rag/data/corpus_10k.json` (48 MB)

### Descobertas:
- Corpus estava em `news_db` porta 5433 (não postgres porta 5432)
- 50,100 notícias disponíveis no total
- Senha postgres local resetada para `postgres123` (documentada em DATABASE_CREDENTIALS.md)

### Comando usado:
```bash
PGPASSWORD=postgres123 psql -h localhost -p 5433 -U postgres -d news_db \
  -f extract_10k_simple.sql > source/rag/data/corpus_10k.json
```

### Estatísticas:
- Total documentos: 10,000
- Tamanho arquivo: 48 MB
- Primeira notícia: "Educação como ferramenta de prevenção..." (ABCD)
- Categorias: Diversas (Educação, Saúde, etc)
- Agências: abcd, saude, mec, etc

---

## 🔄 Passo 2: Transferir para EC2 (PENDENTE)

**Comando:**
```bash
scp source/rag/data/corpus_10k.json ec2-user@<IP-EC2>:/home/ec2-user/rag/data/
```

**Status:** Aguardando IP da EC2

---

## ⏳ Próximos Passos:

3. SSH EC2 e indexar com `index_corpus.py`
4. Testar retrieval com queries da Fase 1-7
5. Testar generation com perguntas conhecidas
6. Comparar métricas 250 vs 10k
7. Documentar em `fase8_escala_10k.md`

