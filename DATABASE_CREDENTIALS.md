# Credenciais de Banco de Dados - Desenvolvimento

⚠️ **ATENÇÃO:** Este arquivo contém credenciais de desenvolvimento. NÃO usar em produção!

---

## PostgreSQL Local (Porta 5432)

**Usado para:** Repositório de corpus de notícias (50k notícias)

```
Host: localhost
Port: 5432
Database: postgres
User: postgres
Password: postgres123
```

**Tabelas principais:**
- `news_corpus_repository` - 50,100 notícias do HuggingFace

**Comando de conexão:**
```bash
psql -h localhost -p 5432 -U postgres -d postgres
# Senha: postgres123
```

**String de conexão (Python/psycopg):**
```python
conn = psycopg.connect("host=localhost port=5432 dbname=postgres user=postgres password=postgres123")
```

---

## PostgreSQL RAG (Porta 5433)

**Usado para:** Sistema RAG da Issue #5

```
Host: localhost
Port: 5433
Database: news_db
User: rag_user
Password: rag_password_2024
```

**Tabelas principais:**
- `documents` - Metadados dos documentos
- `chunks` - Chunks com embeddings vetoriais
- Índices HNSW para busca vetorial

**Comando de conexão:**
```bash
psql -h localhost -p 5433 -U rag_user -d news_db
# Senha: rag_password_2024
```

**Configuração em:** `source/rag/.env`

---

## PostgreSQL EC2 (Produção)

**Usado para:** Testes em escala com GPU

```
Host: <IP-DA-EC2>
Port: 5432
Database: ragdb
User: postgres
Password: <senha-diferente-verificar-EC2>
```

**Acesso via SSH:**
```bash
ssh -i ~/.ssh/sua-chave.pem ec2-user@<IP-DA-EC2>
psql -U postgres -d ragdb
```

---

## Notas de Segurança

1. ✅ Senhas simples OK para desenvolvimento local
2. ❌ NUNCA commitar este arquivo em produção
3. ✅ Arquivo já está no .gitignore
4. ⚠️ Trocar senhas ao migrar para produção
5. ✅ Usar variáveis de ambiente em scripts

---

**Última atualização:** 2026-06-09  
**Ambiente:** Desenvolvimento local
