# Fase 6: Temporalidade

Implementação de consciência temporal no sistema RAG, permitindo que o LLM e os usuários entendam quando as notícias foram publicadas.

---

## 📋 Objetivo

Adicionar capacidade temporal ao sistema RAG para:

1. **LLM tem consciência de datas**: Mostrar data de publicação no contexto
2. **Respostas temporalmente corretas**: LLM pode ordenar eventos cronologicamente
3. **Filtros de data**: API permite buscar por período específico
4. **UX melhorada**: Usuários veem quando cada notícia foi publicada

---

## 🏗️ Arquitetura

### Fluxo de Dados com Temporalidade

```
Query: "Notícias recentes sobre periferias"
   ↓
[Retrieval com filtro opcional de data]
   ↓
published_at incluído nos resultados
   ↓
[Context Building]
   - Fonte 1: [título]
   - Data de Publicação: 19/03/2026  ← NOVO
   - Categoria: ...
   - Conteúdo: ...
   ↓
[LLM Generation]
   - Prompt inclui instrução sobre temporalidade
   - LLM vê datas de todas as fontes
   - Pode ordenar eventos cronologicamente
   ↓
[Response]
   - Answer com datas mencionadas quando relevante
   - Sources com campo published_at
```

---

## ✨ Implementações

### 1. Retrieval Layer

**Arquivo:** `src/retrieval.py`

**Mudanças:**

```python
@dataclass
class RetrievalResult:
    # ... campos existentes ...
    doc_published_at: Optional[str] = None  # Publication date (ISO format)
```

**SQL Query (vector search):**

```sql
SELECT
    dc.id as chunk_id,
    dc.document_id,
    dc.content,
    dc.chunk_index,
    1 - (dc.embedding <=> %s::vector) as score,
    nd.title as doc_title,
    nd.url as doc_url,
    nd.category as doc_category,
    nd.source_agency as doc_agency,
    nd.published_at as doc_published_at  -- NOVO
FROM document_chunks dc
JOIN news_documents nd ON dc.document_id = nd.id
WHERE ...
```

**Filtros de data:**

```python
if 'date_from' in filters:
    where_clauses.append("nd.published_at >= %s")
    params.append(filters['date_from'])

if 'date_to' in filters:
    where_clauses.append("nd.published_at <= %s")
    params.append(filters['date_to'])
```

---

### 2. Generation Layer

**Arquivo:** `src/generation.py`

**Context Building com data:**

```python
# Format publication date for display
published_info = ""
if result.doc_published_at:
    dt = datetime.fromisoformat(result.doc_published_at)
    published_info = f"Data de Publicação: {dt.strftime('%d/%m/%Y')}\n"

chunk_text = f"""[Fonte {source_num}: {result.doc_title}]
Categoria: {result.doc_category}
Órgão: {result.doc_agency}
{published_info}
{result.content}
"""
```

**Prompt com instrução temporal:**

```python
INSTRUÇÕES IMPORTANTES:
1. SEMPRE cite suas fontes usando [1], [2], etc.
2. ...
7. ATENÇÃO À TEMPORALIDADE: Cada fonte possui uma "Data de Publicação". 
   Quando relevante (perguntas sobre "recente", "último", "atual", etc.), 
   considere a ordem cronológica das notícias. Mencione datas quando 
   apropriado para contextualizar a informação.
```

**Sources com data:**

```python
sources.append({
    'index': i,
    'title': result.doc_title,
    'url': result.doc_url,
    'category': result.doc_category,
    'agency': result.doc_agency,
    'published_at': published_date,  # Formato: DD/MM/YYYY
    'chunk_text': result.content[:300] + '...',
    'score': result.score
})
```

---

### 3. API Layer

**Arquivo:** `api/server.py`

**Request Model:**

```python
class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    # ... outros parâmetros ...
    
    # Filtros temporais
    date_from: Optional[str] = Field(None, description="Filter by date from (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Filter by date to (YYYY-MM-DD)")
```

**Response Model:**

```python
class Source(BaseModel):
    index: int
    title: str
    url: str
    category: str
    agency: str
    published_at: Optional[str] = None  # Publication date (DD/MM/YYYY)
    chunk_text: str
    score: float
```

**Aplicação dos filtros:**

```python
filters = {}
if request.date_from:
    filters['date_from'] = request.date_from
if request.date_to:
    filters['date_to'] = request.date_to

rag_response = generator.generate(query=request.query, filters=filters)
```

---

### 4. Client Layer

**Arquivo:** `api/client.py`

**Display de sources com data:**

```python
console.print(f"\n[cyan][{source['index']}][/cyan] {source['title']}")

metadata_parts = [
    f"Categoria: {source['category']}", 
    f"Órgão: {source['agency']}"
]
if source.get('published_at'):
    metadata_parts.append(f"Data: {source['published_at']}")

console.print(f"   [dim]{' | '.join(metadata_parts)}[/dim]")
```

**Configuração de filtros de data:**

```python
# No /config
date_from = Prompt.ask("Date from (YYYY-MM-DD)", default=config.get('date_from') or "")
new_config['date_from'] = date_from if date_from else None

date_to = Prompt.ask("Date to (YYYY-MM-DD)", default=config.get('date_to') or "")
new_config['date_to'] = date_to if date_to else None
```

---

## 🧪 Testes

### Test 1: Consciência temporal do LLM

**Query:** "Quais as notícias mais recentes sobre periferias?"

**Resultado:**

```
ANSWER:
Com base nas fontes disponíveis, a notícia mais recente sobre periferias 
é de **19 de março de 2026** [1]:

## Encontro Nacional das Periferias
A Secretaria Nacional de Periferias (SNP) realizou um encontro que reuniu 
representantes de favelas de todo o país [1]. Durante o evento, foram 
apresentadas várias iniciativas:
...

SOURCES:
  [1] Encontro Nacional das Periferias reúne representantes...
      Data: 19/03/2026 | Score: 0.557
```

✅ **LLM identificou corretamente a data mais recente**
✅ **LLM mencionou explicitamente a data na resposta**
✅ **Source mostra data formatada (DD/MM/YYYY)**

---

### Test 2: Ordenação cronológica

**Query:** "O que aconteceu em março de 2026?"

**Resultado:**

```
ANSWER:
## Políticas de Enfrentamento à Violência
Em **5 de março de 2026**, o Governo do Brasil apresentou...

## Preparação para Conferência Nacional de Arquivos
Em **23 de março de 2026**, estados de todas as regiões...

SOURCES:
  [1] Estupro coletivo no Rio de Janeiro... (05/03/2026)
  [2] Parceria entre MJSP e USP... (02/03/2026)
  [4] Estados iniciam maratona... (23/03/2026)
```

✅ **LLM ordenou eventos cronologicamente**
✅ **LLM mencionou datas específicas (5 e 23 de março)**
✅ **Contexto temporal claro na resposta**

---

### Test 3: Filtros de data via API

**Request:**

```json
POST /query
{
  "query": "Quais notícias foram publicadas em março?",
  "top_k": 5,
  "date_from": "2026-03-01",
  "date_to": "2026-03-31",
  "min_source_score": 0.3
}
```

**Resultado:**
- ✅ Apenas documentos do período especificado
- ✅ Retrieval aplicou filtro SQL corretamente
- ✅ Performance mantida (índice em published_at)

---

## 📊 Impacto

### Benefícios

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **LLM awareness** | Sem noção de tempo | Entende cronologia |
| **Respostas** | "Aconteceu X" | "Em 19/03/2026, aconteceu X" |
| **Sources** | Sem data | Data visível (DD/MM/YYYY) |
| **Filtros** | Apenas categoria/órgão | + date_from / date_to |
| **Queries temporais** | Imprecisas | "Notícias recentes" funciona |

### Casos de Uso Habilitados

1. **"Quais as notícias mais recentes sobre X?"**
   - LLM identifica e menciona a mais recente

2. **"O que aconteceu em março de 2026?"**
   - LLM ordena eventos cronologicamente

3. **"Últimas atualizações sobre Y"**
   - Sistema prioriza notícias recentes

4. **Análise temporal**
   - Usuários podem filtrar por período via API
   - Útil para análises históricas

---

## 🔧 Detalhes Técnicos

### Formato de Datas

**Banco de dados:**
- Tipo: `timestamp without time zone`
- Índice: `idx_news_published` (DESC)

**Retrieval (interno):**
- Formato: ISO string (`2026-03-19T17:22:17`)
- Conversão: `published_at.isoformat()`

**Context (para LLM):**
- Formato: `DD/MM/YYYY` (brasileiro)
- Parsing: `datetime.strptime('%d/%m/%Y')`

**API Response:**
- Formato: `DD/MM/YYYY` (display)
- Campo: `published_at: Optional[str]`

**API Request (filtros):**
- Formato: `YYYY-MM-DD` (ISO date)
- SQL: `WHERE published_at >= '2026-03-01'`

---

### Performance

**Queries com filtro de data:**

```sql
-- Query original (sem filtro)
SELECT ... FROM document_chunks dc
JOIN news_documents nd ON dc.document_id = nd.id
ORDER BY score DESC LIMIT 5
-- ~200-300ms

-- Query com filtro de data
SELECT ... FROM document_chunks dc
JOIN news_documents nd ON dc.document_id = nd.id
WHERE nd.published_at >= '2026-03-01'
  AND nd.published_at <= '2026-03-31'
ORDER BY score DESC LIMIT 5
-- ~200-320ms (impacto mínimo)
```

✅ **Índice `idx_news_published` mantém performance**

---

## 🚀 Uso

### Via Python

```python
from src.generation import Generator

response = generator.generate(
    query="Notícias recentes sobre agricultura",
    filters={
        'date_from': '2026-03-01',
        'date_to': '2026-03-31'
    }
)

for source in response.sources:
    print(f"[{source['index']}] {source['title']}")
    print(f"    Data: {source['published_at']}")
```

### Via API

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "O que aconteceu em março?",
    "top_k": 5,
    "date_from": "2026-03-01",
    "date_to": "2026-03-31"
  }'
```

### Via Cliente Interativo

```
$ python api/client.py

> /config
Date from (YYYY-MM-DD): 2026-03-01
Date to (YYYY-MM-DD): 2026-03-31
✓ Configuration updated

> Notícias de março sobre periferias

[1] Encontro Nacional das Periferias...
    Categoria: Cidades | Órgão: MCid | Data: 19/03/2026
    Score: 0.557
```

---

## 📝 Limitações e Melhorias Futuras

### Limitações Atuais

1. **Sem boosting de recência**
   - Score baseado apenas em similaridade semântica
   - Documentos antigos e recentes têm peso igual
   - Solução: Fase 6.5 (Hybrid scoring)

2. **LLM não ordena automaticamente**
   - Depende de instrução no prompt
   - Funciona bem para queries explícitas ("recente", "último")
   - Pode não priorizar recência em queries genéricas

3. **Formato de data fixo**
   - DD/MM/YYYY hardcoded (padrão brasileiro)
   - API aceita apenas YYYY-MM-DD (ISO)

### Próximas Melhorias (Fase 6.5 - Opcional)

#### 1. Hybrid Scoring (Relevância + Recência)

**Fórmula:**

```python
final_score = (similarity_score * 0.7) + (recency_score * 0.3)

# Recency score
days_old = (today - published_at).days
recency_score = 1 / (1 + days_old / 30)  # Decay over 30 days

# Exemplo:
# - Hoje: 1.0
# - 30 dias atrás: 0.5
# - 60 dias atrás: 0.33
```

**Uso:**

```python
retriever.config = RetrieverConfig(
    use_recency_boost=True,
    recency_weight=0.3  # 30% weight on recency
)
```

**Benefício:** Queries genéricas priorizam notícias recentes automaticamente

---

#### 2. Query-Aware Boosting

**Detectar termos temporais na query:**

```python
temporal_terms = ['recente', 'último', 'atual', 'novo', 'hoje', 'mês passado']

if any(term in query.lower() for term in temporal_terms):
    # Increase recency weight automatically
    recency_weight = 0.5  # 50% for explicit temporal queries
else:
    recency_weight = 0.1  # 10% for generic queries
```

**Benefício:** Sistema adapta scoring baseado na intenção da query

---

#### 3. Temporal Aggregations

**API endpoint para análises temporais:**

```python
POST /temporal-analysis
{
  "query": "agricultura",
  "group_by": "month"  # week, month, year
}

Response:
{
  "2026-03": 12 documents,
  "2026-02": 8 documents,
  "2026-01": 15 documents
}
```

**Benefício:** Visualizar tendências ao longo do tempo

---

## ✅ Conclusão

### O que foi implementado

✅ Campo `published_at` em todas as camadas
✅ Data visível no contexto do LLM (formato brasileiro)
✅ Instrução temporal no prompt padrão
✅ Filtros de data na API (`date_from`, `date_to`)
✅ Display de data nas sources (cliente e API)
✅ LLM consegue ordenar eventos cronologicamente
✅ Performance mantida (índice existente)

### Resultado Final

O sistema RAG agora é **temporalmente consciente**:

- **LLM sabe quando as notícias foram publicadas**
- **Respostas mencionam datas quando relevante**
- **Usuários veem data de cada source**
- **API permite filtrar por período**

### Exemplos de Sucesso

1. ✅ "Quais as notícias mais recentes?" → LLM identifica e menciona 19/03/2026
2. ✅ "O que aconteceu em março?" → LLM ordena: 5 de março, 23 de março
3. ✅ Filtro: `date_from=2026-03-01` → Apenas março retornado
4. ✅ Sources mostram data: "Data: 19/03/2026"

---

**Status:** ✅ **Fase 6 Completa**

**Próximo:** Fase 7 - Salvaguardas de Segurança (Prompt Injection Protection)

---

**Implementado em:** 2026-05-29  
**Estimativa:** 1-2 dias → Real: ~2 horas  
**Complexidade:** Baixa-Média  
**Arquivos modificados:** 4 (retrieval.py, generation.py, server.py, client.py)  
**Linhas adicionadas:** ~150  
**Backward compatible:** ✅ Sim (published_at opcional)
