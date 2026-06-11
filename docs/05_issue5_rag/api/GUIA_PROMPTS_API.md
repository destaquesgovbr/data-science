# Guia de Prompts e Configuração da API RAG

**Data:** 2026-06-11  
**Autor:** Luis Felipe de Moraes  
**Contexto:** Otimização de prompts durante testes com 10k documentos

---

## 📋 Visão Geral

A API RAG possui **4 templates de prompt** diferentes, cada um otimizado para um tipo específico de tarefa. Os templates são selecionados via parâmetro `prompt_template` no endpoint `/query`.

**Localização do código:**
- Templates: `source/rag/src/generation.py` → classe `PromptLibrary`
- API: `source/rag/api/server.py` → endpoint `/query`

---

## 🎯 Templates Disponíveis

### 1. **default** (Padrão)
**Uso:** Perguntas gerais, Q&A padrão

**Características:**
- Tom profissional e objetivo
- Sintetiza informações de múltiplas fontes
- Apresenta informações disponíveis mesmo que parciais
- Sempre cita fontes com [1], [2], etc.

**Quando usar:**
- Perguntas abertas sobre temas gerais
- Busca por informações contextuais
- Usuário quer resposta completa e bem formatada

**Exemplo de query:**
```
"Quais são as ações do governo sobre saúde no Nordeste?"
"O que se tem falado sobre seguro defeso?"
```

---

### 2. **factual** (Factual)
**Uso:** Perguntas que exigem fatos específicos, números, datas

**Características:**
- Conciso e direto ao ponto
- Prioriza dados objetivos (valores, datas, nomes)
- Menos interpretação, mais informação bruta
- Sempre cita fonte exata para cada fato

**Quando usar:**
- Perguntas sobre valores monetários
- Busca por datas específicas
- Verificação de fatos
- Informações numéricas ou estatísticas

**Exemplo de query:**
```
"Qual o valor do Plano Safra 2024?"
"Quantos beneficiários tem o seguro-defeso?"
"Quando foi publicado o edital do PRH?"
```

---

### 3. **summary** (Resumo)
**Uso:** Sintetizar informações complexas ou múltiplas fontes

**Características:**
- Organiza em tópicos estruturados
- Destaca valores e datas importantes
- Menciona órgãos/agências responsáveis
- Formato mais longo e detalhado

**Quando usar:**
- Resumir políticas complexas
- Sintetizar múltiplas notícias sobre um tema
- Visão geral de programas governamentais
- Documentação executiva

**Exemplo de query:**
```
"Resuma todas as informações sobre agricultura familiar"
"Faça um resumo dos programas de bolsas de estudo disponíveis"
"Sintetize as políticas de energia renovável"
```

---

### 4. **comparison** (Comparação)
**Uso:** Comparar programas, políticas ou iniciativas

**Características:**
- Formato estruturado (comum, diferenças, conclusão)
- Destaca aspectos comparáveis
- Organiza lado a lado
- Útil para análises comparativas

**Quando usar:**
- Comparar dois ou mais programas
- Diferenças entre políticas regionais
- Evolução temporal de uma política
- Análise comparativa de órgãos/agências

**Exemplo de query:**
```
"Compare o Plano Safra 2023 e 2024"
"Diferenças entre seguro-defeso e seguro-desemprego do pescador"
"Compare as políticas de saúde do Nordeste e Sul"
```

---

## 🔧 Como Usar via API

### Exemplo Python (client.py)

```python
import requests

# Configuração base
API_URL = "http://localhost:8000/query"

# Request com template DEFAULT
response = requests.post(API_URL, json={
    "query": "Quais programas existem para pescadores?",
    "prompt_template": "default",  # ou "factual", "summary", "comparison"
    "top_k": 5,
    "use_reranking": True,
    "temperature": 0.0
})

result = response.json()
print(result['answer'])
```

### Exemplo cURL

```bash
# Template FACTUAL
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual o valor do Bolsa Família?",
    "prompt_template": "factual",
    "top_k": 5
  }'

# Template SUMMARY
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Resuma as políticas de educação",
    "prompt_template": "summary",
    "top_k": 10
  }'
```

### Client Interativo

No `client.py` interativo:

```
> /config

Prompt template [default/factual/summary/comparison] (default): factual
✓ Configuration updated

> Qual o valor do Plano Safra 2024?
```

---

## 🐛 Problema Identificado e Corrigido

### ❌ Problema Original (até 2026-06-11)

**Sintoma:** LLM respondia "não encontrei essa informação" mesmo quando **havia** informações relevantes nas fontes.

**Causa raiz:** Instrução muito restritiva no prompt:

```
2. Se uma informação não estiver nas fontes fornecidas, 
   diga claramente "não encontrei essa informação nas fontes disponíveis"
```

**Exemplo de resposta problemática:**
```
Query: "notícias sobre saúde no nordeste"
Resposta: "Infelizmente, não encontrei informações específicas..."

Fontes recuperadas:
- "Trabalhadores da região Nordeste debatem a saúde suplementar"
- "Workshop Promoprev Recife"
- "Anvisa realiza webinar com coordenadores do Nordeste"
```

→ **Há 3 fontes relevantes, mas LLM disse "não encontrei"!**

---

### ✅ Solução Aplicada

**Mudança na instrução:**

**ANTES:**
```
2. Se uma informação não estiver nas fontes fornecidas, 
   diga claramente "não encontrei essa informação nas fontes disponíveis"
```

**DEPOIS:**
```
2. Use as informações disponíveis nas fontes para construir uma resposta útil
3. Se as fontes contêm informações relacionadas (mesmo que parciais), 
   apresente o que está disponível
4. Apenas diga "não encontrei" se as fontes forem COMPLETAMENTE irrelevantes
```

**Resultado esperado:**
```
Query: "notícias sobre saúde no nordeste"
Resposta: "Com base nas fontes, encontrei as seguintes informações 
sobre saúde no Nordeste:

A ANS realizou encontro em Recife [1] para debater saúde suplementar 
com trabalhadores da região. O mercado de saúde suplementar no Nordeste 
possui 149 operadoras e 6,58 milhões de beneficiários [1].

Além disso, a Anvisa realizou webinar com coordenadores de vigilância 
sanitária da região [3]..."
```

→ **Agora apresenta as informações disponíveis!** ✅

---

## 📊 Comparação: Antes vs Depois

### Teste 1: "saúde no nordeste"

**ANTES (prompt restritivo):**
- ❌ "Não encontrei essa informação"
- 3 fontes relevantes ignoradas
- Usuário frustrado

**DEPOIS (prompt otimizado):**
- ✅ Sintetiza 3 fontes sobre saúde no Nordeste
- Cita ANS, Anvisa, Workshop Promoprev
- Menciona 6,58 milhões de beneficiários
- Resposta útil e informativa

### Teste 2: "programas para pescadores"

**ANTES:**
- ❌ "Não encontrei informações específicas"
- Fonte sobre seguro-defeso ignorada

**DEPOIS:**
- ✅ Explica seguro-defeso do pescador artesanal
- Cita Lei 14.601/2023
- Menciona valor (1 salário mínimo em 5 parcelas)
- Informação completa

---

## 🎯 Boas Práticas

### 1. Escolha o Template Certo

**Regra geral:**
- Pergunta simples → `default`
- Preciso de número/data → `factual`
- Preciso entender o todo → `summary`
- Preciso comparar → `comparison`

### 2. Ajuste o `top_k`

```python
# Query específica (busca pontual)
top_k = 3-5

# Query ampla (múltiplos aspectos)
top_k = 10-15

# Summary ou comparison (precisa contexto completo)
top_k = 10-20
```

### 3. Use Reranking para Queries Complexas

```python
# Query simples
use_reranking = False  # Mais rápido

# Query com múltiplos conceitos
use_reranking = True   # Mais preciso
```

### 4. Ajuste Temperature

```python
# Respostas factuais (zero criatividade)
temperature = 0.0

# Respostas criativas/síntese
temperature = 0.3-0.6
```

---

## 🔧 Parâmetros Completos do Endpoint `/query`

```python
class QueryRequest:
    # Query obrigatória
    query: str                    # Pergunta do usuário
    
    # Retrieval
    top_k: int = 5                # Número de chunks (1-20)
    use_reranking: bool = True    # Ativar reranking
    
    # LLM
    provider: str = "bedrock"     # bedrock, ollama
    model: str = "haiku-4.5"      # Modelo específico
    max_tokens: int = 2000        # Limite de resposta
    temperature: float = 0.0      # 0.0-2.0 (criatividade)
    
    # Prompts
    prompt_template: str = "default"  # default, factual, summary, comparison
    
    # Filtragem
    min_source_score: float = 0.0     # Filtrar por relevância
    category: str = None              # Filtrar por categoria
    agency: str = None                # Filtrar por agência
    date_from: str = None             # YYYY-MM-DD
    date_to: str = None               # YYYY-MM-DD
```

---

## 📝 Exemplo de Uso Completo

```python
import requests

API_URL = "http://localhost:8000/query"

# Query complexa com filtros
request = {
    # Query
    "query": "Quais programas de bolsas foram anunciados em 2024?",
    
    # Retrieval otimizado
    "top_k": 10,
    "use_reranking": True,
    
    # Template para resumo
    "prompt_template": "summary",
    
    # Filtros
    "date_from": "2024-01-01",
    "date_to": "2024-12-31",
    "min_source_score": 0.5,  # Apenas fontes relevantes
    
    # LLM
    "provider": "ollama",
    "model": "llama3.2:3b",
    "temperature": 0.0
}

response = requests.post(API_URL, json=request)
result = response.json()

print(f"Resposta: {result['answer']}\n")
print(f"Fontes usadas: {len(result['sources'])}")
print(f"Latência: {result['metrics']['total_ms']}ms")
```

---

## 🚀 Próximos Passos

### Melhorias Futuras

1. **Templates Adicionais**
   - `timeline`: Ordenar eventos cronologicamente
   - `analysis`: Análise crítica de políticas
   - `citation-heavy`: Para uso acadêmico/jurídico

2. **Prompts Dinâmicos**
   - Detectar tipo de query automaticamente
   - Sugerir melhor template ao usuário
   - A/B testing de prompts

3. **Personalização**
   - Usuário pode criar templates customizados
   - Salvar templates favoritos
   - Histórico de templates usados

4. **Métricas de Qualidade**
   - Avaliar qualidade por template
   - User feedback por tipo de resposta
   - Otimização contínua via RL

---

## 📚 Referências

**Documentação relacionada:**
- `source/rag/src/generation.py` - Implementação dos templates
- `source/rag/api/server.py` - Endpoint da API
- `docs/05_issue5_rag/api/documentacao_api.md` - Documentação completa da API

**Papers relevantes:**
- Chain-of-Thought Prompting (Wei et al., 2022)
- ReAct: Reasoning and Acting (Yao et al., 2023)
- Lost in the Middle (Liu et al., 2023) - Importância da posição das fontes

**Changelog:**
- 2026-06-11: Corrigido problema "não encontrei" nos prompts
- 2026-06-11: Documentação criada

---

**Última atualização:** 2026-06-11  
**Versão:** 2.0 (pós-correção de prompts)  
**Status:** ✅ Validado com 10k documentos
