# Guia Completo de Tecnologias - Sistema RAG

**Documento para revisão e aprendizado pessoal**  
**Data**: 2026-05-29

Este documento explica todas as tecnologias usadas no sistema RAG, desde os fundamentos até a implementação prática.

---

## 📑 Índice

1. [PostgreSQL + pgvector](#1-postgresql--pgvector)
2. [Embeddings e BGE-M3](#2-embeddings-e-bge-m3)
3. [Sentence Transformers](#3-sentence-transformers)
4. [Busca Vetorial e Similaridade](#4-busca-vetorial-e-similaridade)
5. [Índices Vetoriais (IVFFlat)](#5-índices-vetoriais-ivfflat)
6. [Re-ranking e Cross-Encoders](#6-re-ranking-e-cross-encoders)
7. [RAG (Retrieval-Augmented Generation)](#7-rag-retrieval-augmented-generation)
8. [AWS Bedrock](#8-aws-bedrock)
9. [Ollama](#9-ollama)
10. [Claude (Modelos e Inference Profiles)](#10-claude-modelos-e-inference-profiles)
11. [FastAPI](#11-fastapi)
12. [Conceitos Avançados](#12-conceitos-avançados)

---

## 1. PostgreSQL + pgvector

### O que é?

**PostgreSQL** é um banco de dados relacional open-source, extremamente robusto e popular.

**pgvector** é uma extensão do PostgreSQL que adiciona suporte nativo para **vetores** (arrays de números) e operações de **similaridade vetorial**.

### Por que usar?

Sem pgvector, teríamos que:
- Armazenar embeddings em arquivos JSON/pickle
- Implementar busca vetorial manualmente (MUITO lento)
- Gerenciar índices e cache nós mesmos

Com pgvector:
- ✅ Embeddings armazenados no banco (integrado com dados)
- ✅ Busca vetorial **nativa** e otimizada
- ✅ Índices especializados (IVFFlat, HNSW)
- ✅ ACID transactions (consistência)

### Como funciona?

**Instalação da extensão:**
```sql
CREATE EXTENSION vector;
```

**Criação de tabela com vetores:**
```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(1024)  -- Vetor de 1024 dimensões
);
```

**Inserção de embedding:**
```sql
INSERT INTO document_chunks (content, embedding) 
VALUES (
    'Texto do chunk',
    '[0.123, -0.456, 0.789, ...]'::vector  -- Array de 1024 números
);
```

**Busca por similaridade:**
```sql
-- <=> é o operador de distância cosseno
SELECT content, 1 - (embedding <=> '[query_embedding]'::vector) as similarity
FROM document_chunks
ORDER BY embedding <=> '[query_embedding]'::vector
LIMIT 10;
```

### Operadores do pgvector

| Operador | Significado | Uso |
|----------|-------------|-----|
| `<->` | Distância Euclidiana | `ORDER BY embedding <-> query` |
| `<=>` | Distância Cosseno | `ORDER BY embedding <=> query` (nosso caso) |
| `<#>` | Produto Interno Negativo | `ORDER BY embedding <#> query` |

**Qual usar?**
- **Cosseno (`<=>`)**: Para embeddings normalizados (nosso caso com BGE-M3)
- Euclidiana: Para embeddings não-normalizados
- Produto interno: Para casos específicos

### No nosso projeto

```python
# Armazenamos embeddings BGE-M3 (1024 dimensões, normalizados)
embedding_column = vector(1024)

# Buscamos usando distância cosseno
ORDER BY embedding <=> query_embedding

# Convertemos distância para similaridade
similarity = 1 - distance  # Varia de 0 (nada similar) a 1 (idêntico)
```

**Vantagens:**
- Busca em ~50-200ms para 1000 chunks
- Escalável para milhões de documentos
- Integrado com SQL (JOIN, WHERE, etc.)

---

## 2. Embeddings e BGE-M3

### O que são embeddings?

**Embeddings** são representações numéricas (vetores) de texto que capturam o **significado semântico**.

**Analogia:** 
- Texto = descrição de uma localização ("casa perto da praia")
- Embedding = coordenadas GPS (latitude, longitude)
- Similaridade = distância entre coordenadas

Textos com significados similares têm embeddings próximos no espaço vetorial.

### Exemplo visual (2D simplificado)

```
"cachorro" → [0.8, 0.2]
"gato"     → [0.7, 0.3]    ← Próximos (animais)
"carro"    → [-0.5, 0.9]   ← Distante (objeto)
```

No mundo real, usamos **1024 dimensões** (BGE-M3), não 2!

### BGE-M3: BAAI General Embedding Model v3

**Desenvolvido por:** Beijing Academy of Artificial Intelligence (BAAI)  
**Lançamento:** 2023  
**Paper:** [BGE M3-Embedding](https://arxiv.org/abs/2402.03216)

**Características:**
- **M3** = Multi-Lingual, Multi-Functionality, Multi-Granularity
- Suporta **100+ idiomas** (incluindo português)
- **1024 dimensões**
- Normalizado (norma L2 = 1)
- State-of-the-art em benchmarks multilíngues

**Comparação com alternativas:**

| Modelo | Dimensões | Idiomas | Qualidade PT | Velocidade |
|--------|-----------|---------|--------------|------------|
| BGE-M3 | 1024 | 100+ | ⭐⭐⭐⭐⭐ | Média |
| text-embedding-3-small (OpenAI) | 1536 | Multi | ⭐⭐⭐⭐ | Rápida (API) |
| multilingual-e5-large | 1024 | 100+ | ⭐⭐⭐⭐ | Média |
| paraphrase-multilingual | 768 | 50+ | ⭐⭐⭐ | Rápida |

**Por que escolhemos BGE-M3?**
1. ✅ Excelente para português
2. ✅ Open-source (sem custo de API)
3. ✅ Estado-da-arte em benchmarks
4. ✅ Compatível com Sentence Transformers

### Como funciona internamente?

```
Texto → Tokenização → BERT Encoder → Pooling → Normalização → Embedding [1024]
```

1. **Tokenização**: "Programa do CNPq" → [101, 2534, 1045, 7632, 102]
2. **BERT Encoder**: Transforma tokens em vetores contextualizados
3. **Pooling**: Agrega vetores de todos os tokens (média, CLS token, etc.)
4. **Normalização**: Escala para norma 1 (importante para cosine similarity)

### No nosso projeto

```python
from sentence_transformers import SentenceTransformer

# Carregar modelo (download automático da HuggingFace)
embedder = SentenceTransformer('BAAI/bge-m3', device='cpu')

# Gerar embedding
text = "Programa do CNPq para pesca"
embedding = embedder.encode(text, normalize_embeddings=True)

# Resultado: numpy array [1024]
print(embedding.shape)  # (1024,)
print(np.linalg.norm(embedding))  # ~1.0 (normalizado)
```

**Performance:**
- CPU: ~100-200ms por texto
- GPU (T4): ~10-20ms por texto
- Batch de 32: ~500ms (CPU), ~50ms (GPU)

---

## 3. Sentence Transformers

### O que é?

**Sentence Transformers** é uma biblioteca Python para trabalhar com embeddings de sentenças/documentos.

**Desenvolvido por:** UKP Lab (Technical University of Darmstadt)  
**GitHub:** [UKPLab/sentence-transformers](https://github.com/UKPLab/sentence-transformers)

### Funcionalidades principais

1. **Carregar modelos pré-treinados** (HuggingFace Hub)
2. **Gerar embeddings** (encode)
3. **Calcular similaridade** (util.cos_sim)
4. **Fine-tuning** (treinar seus próprios embeddings)

### API básica

```python
from sentence_transformers import SentenceTransformer, util

# 1. Carregar modelo
model = SentenceTransformer('BAAI/bge-m3')

# 2. Gerar embeddings
texts = ["cachorro", "gato", "carro"]
embeddings = model.encode(texts, normalize_embeddings=True)

# 3. Calcular similaridade
similarity = util.cos_sim(embeddings[0], embeddings[1])
print(f"Similaridade cachorro-gato: {similarity:.3f}")  # ~0.7-0.8

similarity = util.cos_sim(embeddings[0], embeddings[2])
print(f"Similaridade cachorro-carro: {similarity:.3f}")  # ~0.2-0.3
```

### Modelos disponíveis

HuggingFace tem **1000+ modelos** de sentence embeddings:

**Multilíngues:**
- `BAAI/bge-m3` (nosso)
- `intfloat/multilingual-e5-large`
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

**Inglês (state-of-the-art):**
- `BAAI/bge-large-en-v1.5`
- `sentence-transformers/all-mpnet-base-v2`

**Português específico:**
- `neuralmind/bert-base-portuguese-cased` (embeddings BERT)
- `rufimelo/bert-large-portuguese-cased-legal` (domínio jurídico)

### No nosso projeto

```python
# Inicialização (1x ao carregar API)
embedder = SentenceTransformer('BAAI/bge-m3', device='cpu')

# Uso durante retrieval
def _vector_search(self, query: str):
    # Gerar embedding da query
    query_embedding = self.embedder.encode(
        query,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False
    )
    
    # Buscar no PostgreSQL
    # ...
```

**Parâmetros importantes:**
- `normalize_embeddings=True` - Norma L2 = 1 (para cosine similarity)
- `convert_to_numpy=True` - Retorna numpy array (não torch tensor)
- `show_progress_bar=False` - Sem output visual (para API)
- `device='cpu'` ou `'cuda'` - CPU ou GPU

---

## 4. Busca Vetorial e Similaridade

### Fundamentos matemáticos

**Similaridade Cosseno:**

```
cos(θ) = (A · B) / (||A|| × ||B||)

Onde:
- A, B = vetores
- · = produto escalar
- ||.|| = norma (magnitude)
```

**Se vetores estão normalizados** (nosso caso):
```
cos(θ) = A · B  (simplificado!)
```

**Interpretação:**
- cos(θ) = 1 → vetores idênticos (θ = 0°)
- cos(θ) = 0 → ortogonais (θ = 90°)
- cos(θ) = -1 → opostos (θ = 180°)

### Distância vs Similaridade

pgvector retorna **distância**, não similaridade:

```python
distance = embedding1 <=> embedding2  # pgvector

similarity = 1 - distance  # Nossa conversão

# Exemplo:
# distance = 0.42 → similarity = 0.58
# distance = 0.15 → similarity = 0.85
```

### Busca KNN (K-Nearest Neighbors)

**Algoritmo naive (força bruta):**
```python
# Para cada documento no banco
for doc in all_documents:
    distance = calculate_distance(query_embedding, doc.embedding)
    
# Ordenar por distância
# Retornar top K
```

**Complexidade:** O(N) onde N = número de documentos

**Problema:** Lento para milhões de documentos!

**Solução:** Índices aproximados (próxima seção)

### No nosso projeto

```sql
-- Busca os 10 chunks mais similares
SELECT 
    content,
    1 - (embedding <=> '[query_embedding]'::vector) as similarity
FROM document_chunks
ORDER BY embedding <=> '[query_embedding]'::vector  -- Ordena por distância
LIMIT 10;
```

**Performance observada:**
- 1037 chunks: ~50-200ms (com índice IVFFlat)
- Sem índice: ~500-1000ms (busca exata)

---

## 5. Índices Vetoriais (IVFFlat)

### O problema

Busca exata em vetores é **O(N)** - precisa comparar query com TODOS os documentos.

Para 1 milhão de documentos: ~10-100 segundos (inviável!)

### Solução: Approximate Nearest Neighbor (ANN)

**Ideia:** Trocar um pouco de **precisão** por **velocidade**.

Em vez de encontrar os **exatos** 10 melhores, encontra **aproximadamente** os 10 melhores (99% de recall).

### IVFFlat (Inverted File with Flat compression)

**IVF** = Inverted File Index  
**Flat** = Vetores armazenados sem compressão

**Como funciona:**

1. **Treinamento (criação do índice):**
   ```
   - Agrupa documentos em N clusters (k-means)
   - Cada cluster tem um centroide
   - Armazena quais documentos pertencem a cada cluster
   ```

2. **Busca:**
   ```
   - Compara query com centroides
   - Seleciona M clusters mais próximos
   - Busca exata APENAS nesses clusters
   - Retorna top K resultados
   ```

**Diagrama conceitual:**
```
Corpus de 1000 documentos
    ↓
Divide em 10 clusters (lists=10)
    ↓
Query → compara com 10 centroides
    ↓
Seleciona 2 clusters mais próximos (probes=2)
    ↓
Busca exata em ~200 documentos (não 1000!)
    ↓
10x mais rápido!
```

### Criação do índice

```sql
-- Criar índice IVFFlat com 100 clusters
CREATE INDEX idx_chunks_embedding 
ON document_chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);
```

**Parâmetros:**
- `lists`: Número de clusters
  - Regra prática: `sqrt(num_rows)` para < 1M rows
  - Nosso caso: `lists=100` para ~1000 chunks
  
- `probes`: Quantos clusters buscar (configurado em runtime)
  ```sql
  SET ivfflat.probes = 10;  -- Busca em 10 clusters
  ```
  - Maior probes = mais preciso, mais lento
  - Menor probes = menos preciso, mais rápido

### IVFFlat vs HNSW

| Característica | IVFFlat | HNSW |
|----------------|---------|------|
| Velocidade busca | Boa | Excelente |
| Velocidade inserção | Excelente | Boa |
| Memória | Baixa | Alta |
| Precisão | Boa | Excelente |
| Quando usar | Corpus estático/quasi-estático | Corpus altamente dinâmico |

**Nossa escolha:** IVFFlat
- Corpus muda pouco (batch updates)
- Menor uso de memória
- Suficientemente rápido (<200ms)

### No nosso projeto

```sql
-- Índice atual
CREATE INDEX idx_chunks_embedding 
ON document_chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Configuração de probes (pode ajustar)
SET ivfflat.probes = 10;  -- Default
```

**Performance:**
- Sem índice: ~500-1000ms (busca exata)
- Com IVFFlat: ~50-200ms (busca aproximada, 99% recall)
- **10x mais rápido!**

---

## 6. Re-ranking e Cross-Encoders

### Problema: Bi-encoders não são perfeitos

**Bi-encoder** (BGE-M3, usado na busca inicial):
```
Query → Encoder → embedding_query
Document → Encoder → embedding_doc

Similarity = cosine(embedding_query, embedding_doc)
```

**Limitação:** Query e Document são encodados **independentemente**, sem "conversarem" entre si.

**Resultado:** Retrieval pode trazer resultados irrelevantes no top-10.

### Solução: Cross-encoders

**Cross-encoder** vê query + document **juntos**:

```
[CLS] Query [SEP] Document [SEP] → BERT → Score (0-1)
```

**Vantagem:** Captura interações entre query e documento (muito mais preciso).

**Desvantagem:** Precisa reprocessar CADA par (query, doc) - muito lento para milhões de docs.

### Pipeline de Re-ranking

```
1. Bi-encoder (rápido): 1M docs → top 100 (busca inicial)
2. Cross-encoder (preciso): top 100 → top 10 (re-ranking)
```

**Por que funciona?**
- Bi-encoder reduz espaço de busca (1M → 100) rapidamente
- Cross-encoder refina ordem dos top 100 com precisão

### ms-marco-MiniLM-L-12-v2

**Nome completo:** `cross-encoder/ms-marco-MiniLM-L-12-v2`

**Desenvolvido por:** Microsoft (MS MARCO dataset)  
**Arquitetura:** MiniLM (versão compacta do BERT)  
**Treinamento:** 8.8 milhões de pares (query, document) em inglês

**Características:**
- 12 layers (L-12)
- v2 (versão melhorada)
- Otimizado para retrieval/re-ranking

**Performance:**
- Input: par (query, document)
- Output: score de 0 a 1 (quanto maior, mais relevante)
- Latência: ~50ms (GPU), ~600ms (CPU) para 10 pares

### Transfer Learning: Inglês → Português

**Experimento que fizemos:**

Testamos 2 modelos:
1. `cross-encoder/ms-marco-MiniLM-L-12-v2` (inglês, 8.8M exemplos)
2. `BAAI/bge-reranker-v2-m3` (multilíngue, ~50k exemplos PT)

**Resultado surpreendente:**
- ms-marco (inglês): **93.3% accuracy**, 609ms
- bge-v2-m3 (multilíngue): 86.7% accuracy, 4935ms

**Por quê?**
- **Quantidade > idioma nativo**: 8.8M exemplos > 50k exemplos
- Embeddings já são multilíngues (BERT aprendeu padrões gerais)
- Transfer learning funciona muito bem em retrieval

### No nosso projeto

```python
from sentence_transformers import CrossEncoder

# Carregar cross-encoder
reranker = CrossEncoder(
    'cross-encoder/ms-marco-MiniLM-L-12-v2',
    max_length=512,
    device='cpu'
)

# Re-ranking
def _rerank(self, query: str, results: List[RetrievalResult]):
    # Preparar pares (query, document)
    pairs = [(query, result.content) for result in results]
    
    # Calcular scores
    scores = self.reranker.predict(pairs)  # Array de scores [0-1]
    
    # Atualizar e reordenar
    for result, score in zip(results, scores):
        result.score = float(score)
    
    results.sort(key=lambda x: x.score, reverse=True)
    return results
```

**Quando usar re-ranking?**
- ✅ Query complexa (múltiplos conceitos)
- ✅ Precisão crítica (resposta deve ser perfeita)
- ❌ Latência crítica (<1s total)
- ❌ Queries muito frequentes (custo computacional)

**Nossa configuração:**
- Opcional (parâmetro `use_reranking`)
- CPU: +600ms de latência
- GPU: +50ms de latência

---

## 7. RAG (Retrieval-Augmented Generation)

### O que é RAG?

**RAG** = Retrieval-Augmented Generation (Geração Aumentada por Recuperação)

**Paper original:** [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) (Lewis et al., 2020, Meta AI)

### Problema que resolve

**LLMs puros (sem RAG):**
```
User: "Qual foi o valor do Plano Safra 2025/2026?"
LLM: "Não tenho informações atualizadas sobre isso..."
```

**Problemas:**
- ❌ Conhecimento limitado (até data de treinamento)
- ❌ Não conhece dados privados/específicos da empresa
- ❌ Pode alucinar (inventar informações)
- ❌ Não cita fontes

**RAG (com recuperação):**
```
1. Buscar documentos relevantes no banco de dados
2. Inserir documentos no contexto do LLM
3. LLM responde baseado nos documentos fornecidos
4. Resposta inclui citações das fontes
```

### Pipeline RAG (nosso sistema)

```
┌─────────────────────────────────────────────────────────────┐
│                   RAG Pipeline Completo                      │
└─────────────────────────────────────────────────────────────┘

Query: "Qual o valor do Plano Safra?"
    ↓
[1] Query Embedding (BGE-M3)
    embedding = [0.123, -0.456, ...]
    ↓
[2] Vector Search (PostgreSQL + pgvector)
    SELECT ... ORDER BY embedding <=> query LIMIT 10
    → 10 chunks mais similares
    ↓
[3] Re-ranking (opcional, ms-marco)
    CrossEncoder predicts relevance
    → Reordena top 10
    ↓
[4] Context Building
    Monta prompt com chunks:
    """
    Fontes:
    [1] Plano Safra 2025/2026... R$ 113,4 bilhões...
    [2] Crédito rural cresceu 7%...
    
    Pergunta: Qual o valor do Plano Safra?
    """
    ↓
[5] LLM Generation (Claude/Ollama)
    Gera resposta baseada no contexto
    → "O Plano Safra conta com R$ 113,4 bilhões [1]"
    ↓
[6] Response Assembly
    {
      answer: "...",
      sources: [{title, url, score}],
      metrics: {latency, tokens, cost}
    }
```

### Vantagens do RAG

1. **Conhecimento atualizado:** Busca em banco sempre current
2. **Dados privados:** Funciona com corpus interno
3. **Menos alucinação:** LLM tem contexto factual
4. **Citações:** Rastreabilidade das informações
5. **Custo controlado:** Não precisa retreinar LLM

### Tipos de RAG

**Naive RAG** (básico):
```
Query → Retrieval → LLM → Answer
```

**Advanced RAG** (nosso):
```
Query → Retrieval → Re-ranking → Context Building → LLM → Answer
```

**Modular RAG** (futuro):
```
Query → Query Expansion → Multi-stage Retrieval → Re-ranking → 
Context Compression → LLM → Self-reflection → Answer
```

### Desafios do RAG

**1. Retrieval failures:**
- Embeddings ruins (modelo fraco)
- Query mal formulada
- Chunks muito grandes/pequenos

**2. Context limitations:**
- LLM context window (8k, 32k, 128k tokens)
- Informação relevante não cabe no contexto

**3. Generation failures:**
- LLM ignora contexto
- Alucinação mesmo com contexto
- Citações incorretas

**Nossas soluções:**
- ✅ BGE-M3 (state-of-the-art embeddings)
- ✅ Re-ranking (refina retrieval)
- ✅ Prompt engineering (instruções claras anti-alucinação)
- ✅ Deduplicação de sources (UX melhor)
- ✅ Claude Haiku/Sonnet (LLMs de alta qualidade)

---

## 8. AWS Bedrock

### O que é?

**AWS Bedrock** = Serviço gerenciado de LLMs da Amazon

**Lançamento:** Abril 2023  
**Objetivo:** Facilitar acesso a modelos foundation (Claude, Mistral, Llama, etc.) via API

### Vantagens

1. **Múltiplos modelos:** Claude, Mistral, Llama, Titan, etc.
2. **Sem gerenciar infraestrutura:** AWS cuida de scaling, uptime
3. **Integração AWS:** IAM, VPC, CloudWatch, etc.
4. **Compliance:** HIPAA, SOC 2, GDPR
5. **Pricing:** Pay-per-use (sem mínimo)

### Modelos disponíveis

**Anthropic (Claude):**
- Claude Opus 4 (mais capaz)
- Claude Sonnet 4.6 (balanceado)
- Claude Sonnet 4.5
- Claude Haiku 4.5 (rápido, barato)

**Mistral AI:**
- Mistral Large
- Mixtral 8x7B

**Meta:**
- Llama 3.3 70B
- Llama 3.1 8B

**Amazon:**
- Titan Text
- Nova Premier

### Inference Profiles (IMPORTANTE!)

**Problema que descobrimos:**

Modelos Claude 4+ **não podem ser acessados diretamente** pelo model ID:

```python
# ❌ NÃO FUNCIONA
model_id = 'anthropic.claude-sonnet-4-6'

# ✅ FUNCIONA (via inference profile)
model_id = 'us.anthropic.claude-sonnet-4-6'
```

**O que são Inference Profiles?**

Profiles são "aliases" para modelos que permitem:
- Cross-region inference (roteamento automático)
- Load balancing entre regiões
- Quotas e rate limits específicos

**Listar profiles disponíveis:**
```bash
aws bedrock list-inference-profiles --region us-east-1
```

**Profiles que funcionam:**
- `us.anthropic.claude-sonnet-4-6`
- `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `us.anthropic.claude-opus-4-20250514-v1:0`
- `global.anthropic.claude-sonnet-4-6`

### API Bedrock

**Formato de requisição (Claude):**

```python
import boto3
import json

client = boto3.client('bedrock-runtime', region_name='us-east-1')

body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 2000,
    "temperature": 0.0,
    "messages": [
        {
            "role": "user",
            "content": "Explique RAG"
        }
    ],
    "system": "Você é um assistente técnico."
}

response = client.invoke_model(
    modelId='us.anthropic.claude-sonnet-4-6',
    body=json.dumps(body)
)

result = json.loads(response['body'].read())
text = result['content'][0]['text']
```

**Diferenças por provider:**

| Provider | Body Format | System Prompt | Stop Sequences |
|----------|-------------|---------------|----------------|
| Claude | Messages API | `system` field | `stop_sequences` |
| Mistral | `prompt` string | Inline no prompt | `stop` |
| Llama | Messages ou prompt | Inline | `stop` |

**Nossa abstração esconde essas diferenças!**

### Pricing (Maio 2026)

**Claude Haiku 4.5:**
- Input: $0.80 / 1M tokens
- Output: $4.00 / 1M tokens
- Nossa média: ~$0.007/query

**Claude Sonnet 4.6:**
- Input: $3.00 / 1M tokens
- Output: $15.00 / 1M tokens
- Nossa média: ~$0.005/query

**Observação:** Sonnet 4.6 tem pricing competitivo com Haiku devido a otimizações!

### No nosso projeto

```python
class BedrockProvider(LLMProvider):
    def __init__(self, model_id: str, region: str = 'us-east-1'):
        self.client = boto3.client('bedrock-runtime', region_name=region)
        self.model_id = model_id
        
        # Detectar provider do model_id
        # us.anthropic.claude → provider = anthropic
        self.provider_name = self._parse_provider(model_id)
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        # Monta body específico do provider
        if self.provider_name == 'anthropic':
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                ...
            }
        elif self.provider_name == 'mistral':
            body = {"prompt": prompt, ...}
        
        # Invoca modelo
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )
        
        # Parse response
        return LLMResponse(...)
```

---

## 9. Ollama

### O que é?

**Ollama** = Framework para rodar LLMs **localmente** (no seu computador/servidor)

**Website:** [ollama.ai](https://ollama.ai)  
**Lançamento:** 2023  
**Open-source:** Sim (MIT license)

### Por que usar?

**Vantagens:**
- ✅ **Custo zero** (sem pagar por API)
- ✅ **Privacidade total** (dados não saem do servidor)
- ✅ **Sem rate limits** (exceto hardware)
- ✅ **Offline** (não precisa de internet)

**Desvantagens:**
- ❌ Requer GPU potente (ou é lento na CPU)
- ❌ Qualidade inferior a Claude/GPT-4
- ❌ Você gerencia infraestrutura

### Instalação

```bash
# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# macOS
brew install ollama

# Windows
# Download do site ollama.ai
```

### Modelos disponíveis

**Listar modelos locais:**
```bash
ollama list
```

**Baixar modelo:**
```bash
ollama pull llama3.1:8b      # Llama 3.1 8B
ollama pull qwen2.5:7b       # Qwen 2.5 7B (multilíngue)
ollama pull mistral:7b       # Mistral 7B
ollama pull llama3.1:70b     # Llama 3.1 70B (requer GPU forte)
```

**Modelos recomendados para português:**

| Modelo | Tamanho | RAM | Qualidade PT | Velocidade |
|--------|---------|-----|--------------|------------|
| qwen2.5:7b | 4.7 GB | 8 GB | ⭐⭐⭐⭐ | Média |
| llama3.1:8b | 4.9 GB | 8 GB | ⭐⭐⭐ | Média |
| mistral:7b | 4.4 GB | 8 GB | ⭐⭐⭐ | Rápida |
| llama3.1:70b | 40 GB | 64 GB | ⭐⭐⭐⭐⭐ | Lenta (requer GPU) |

### API Ollama

**HTTP REST API (localhost:11434):**

```python
import requests

# Gerar texto
response = requests.post('http://localhost:11434/api/generate', json={
    'model': 'llama3.1:8b',
    'prompt': 'Explique RAG',
    'stream': False,
    'options': {
        'temperature': 0.0,
        'num_predict': 2000
    }
})

result = response.json()
text = result['response']
```

**Streaming (para UX em tempo real):**

```python
response = requests.post(
    'http://localhost:11434/api/generate',
    json={'model': 'llama3.1:8b', 'prompt': '...', 'stream': True},
    stream=True
)

for line in response.iter_lines():
    chunk = json.loads(line)
    print(chunk['response'], end='', flush=True)
```

### Performance

**CPU (Intel i7):**
- llama3.1:8b: ~10-15 tokens/s
- Query típica: ~100-150s

**GPU (NVIDIA T4):**
- llama3.1:8b: ~80-100 tokens/s
- Query típica: ~5-10s

**GPU (NVIDIA A100):**
- llama3.1:70b: ~40-60 tokens/s
- Query típica: ~10-20s

**Conclusão:** Para produção, **GPU é essencial** se usar Ollama.

### No nosso projeto

```python
class OllamaProvider(LLMProvider):
    def __init__(self, model: str = 'qwen2.5:7b', base_url: str = 'http://localhost:11434'):
        self.model = model
        self.base_url = base_url
        
        # Verificar se modelo está disponível
        response = requests.get(f"{base_url}/api/tags")
        models = response.json()['models']
        
        if model not in [m['name'] for m in models]:
            raise ValueError(f"Model {model} not found. Run: ollama pull {model}")
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                'model': self.model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': kwargs.get('temperature', 0.0),
                    'num_predict': kwargs.get('max_tokens', 2000)
                }
            }
        )
        
        result = response.json()
        return LLMResponse(
            text=result['response'],
            model=self.model,
            provider='ollama',
            cost_usd=0.0  # Local = grátis!
        )
```

**Resultado nos testes:**
- Qwen 2.5 7B (CPU): ~110s, respostas corretas, custo $0
- Com GPU: ~5-10s esperado

---

## 10. Claude (Modelos e Inference Profiles)

### Família Claude

**Desenvolvedor:** Anthropic  
**Filosofia:** AI Safety, Constitutional AI, Helpful/Harmless/Honest

### Gerações

**Claude 3 (Março 2024):**
- Opus 3 (mais capaz)
- Sonnet 3 (balanceado)
- Haiku 3 (rápido)

**Claude 3.5 (Outubro 2024):**
- Sonnet 3.5 (melhor que Opus 3!)
- Haiku 3.5

**Claude 4 (Dezembro 2024 - Janeiro 2025):**
- Opus 4 (mais capaz da família)
- Sonnet 4.6 (excelente custo-benefício)
- Sonnet 4.5
- Haiku 4.5 (rápido, 2x melhor que Haiku 3.5)

### Comparação de capacidades

| Modelo | Context Window | Força | Fraqueza | Use Case |
|--------|----------------|-------|----------|----------|
| Opus 4 | 200k tokens | Raciocínio complexo | Mais caro | Análise profunda, código complexo |
| Sonnet 4.6 | 200k tokens | Balanceado | - | **Nossa escolha default** |
| Haiku 4.5 | 200k tokens | Velocidade | Raciocínio limitado | RAG, classificação, QA simples |

### Sonnet 4.6 (nosso favorito)

**Por que escolhemos?**
1. ✅ Qualidade excelente (próximo do Opus)
2. ✅ Velocidade boa (2-3s para respostas)
3. ✅ Pricing competitivo ($3/$15 input/output)
4. ✅ Context window grande (200k tokens)
5. ✅ Excelente em português

**Benchmarks:**
- MMLU: 88.7% (conhecimento geral)
- HumanEval: 92.0% (código)
- Math: 78.3% (matemática)

### Inference Profiles (repetindo por importância!)

**Claude 4+ só funciona via profiles:**

```python
# ❌ Não funciona
'anthropic.claude-sonnet-4-6'

# ✅ Funciona
'us.anthropic.claude-sonnet-4-6'          # US region
'global.anthropic.claude-sonnet-4-6'      # Global (roteamento automático)
```

**Como descobrir profiles:**
```bash
aws bedrock list-inference-profiles --region us-east-1 \
    | jq '.inferenceProfileSummaries[] | select(.inferenceProfileName | contains("Claude"))'
```

### Prompt Engineering para Claude

**Princípios:**

1. **Seja específico:**
   ```
   ❌ "Responda a pergunta"
   ✅ "Responda com base APENAS nas fontes fornecidas. Cite usando [1], [2]."
   ```

2. **Use system prompts:**
   ```python
   system="Você é um assistente especializado em responder perguntas sobre notícias governamentais brasileiras. Sempre cite suas fontes usando [1], [2], etc."
   ```

3. **Estruture o contexto:**
   ```
   [Fonte 1: Título]
   Categoria: X
   Órgão: Y
   
   Conteúdo...
   ```

4. **Anti-alucinação:**
   ```
   Se a informação não estiver nas fontes, diga claramente "não encontrei essa informação".
   Não invente ou especule.
   ```

### No nosso projeto

**Configuração default:**
```python
DEFAULT_MODEL = 'us.anthropic.claude-haiku-4-5-20251001-v1:0'

# Para casos complexos, usuário pode escolher:
ALTERNATIVE_MODELS = [
    'us.anthropic.claude-sonnet-4-6',  # Melhor qualidade
    'us.anthropic.claude-opus-4-20250514-v1:0'  # Máxima capacidade
]
```

**System prompt:**
```python
system = "Você é um assistente especializado em responder perguntas sobre notícias e políticas governamentais brasileiras. Sempre cite suas fontes usando [1], [2], etc."
```

**Resultados observados:**
- Haiku 4.5: 2-3s latência, respostas boas, $0.007/query
- Sonnet 4.6: 5-7s latência, respostas excelentes, $0.005/query
- Anti-alucinação funciona bem (diz "não encontrei" quando apropriado)

---

## 11. FastAPI

### O que é?

**FastAPI** = Framework web moderno para criar APIs em Python

**Desenvolvedor:** Sebastián Ramírez (tiangolo)  
**Lançamento:** 2018  
**GitHub:** [tiangolo/fastapi](https://github.com/tiangolo/fastapi)

### Por que FastAPI?

**Comparação com alternativas:**

| Feature | FastAPI | Flask | Django REST |
|---------|---------|-------|-------------|
| Performance | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Type hints | ✅ Nativo | ❌ | ❌ |
| Auto docs | ✅ (Swagger) | ❌ | 🟡 (requer config) |
| Async/await | ✅ Nativo | 🟡 (desde 2.0) | 🟡 |
| Validação | ✅ (Pydantic) | ❌ Manual | 🟡 (Serializers) |
| Aprendizado | Fácil | Muito fácil | Médio |

**Vantagens FastAPI:**
1. ✅ **Performance** (comparável com Node.js, Go)
2. ✅ **Documentação automática** (Swagger UI)
3. ✅ **Validação automática** (Pydantic)
4. ✅ **Type safety** (IDE autocomplete)
5. ✅ **Async/await** nativo

### Conceitos básicos

**1. Definir API:**
```python
from fastapi import FastAPI

app = FastAPI(title="My API", version="1.0.0")

@app.get("/")
def root():
    return {"message": "Hello World"}
```

**2. Path parameters:**
```python
@app.get("/items/{item_id}")
def get_item(item_id: int):
    return {"item_id": item_id}
```

**3. Query parameters:**
```python
@app.get("/search")
def search(q: str, limit: int = 10):
    return {"query": q, "limit": limit}
```

**4. Request body (Pydantic):**
```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float
    is_offer: bool = False

@app.post("/items")
def create_item(item: Item):
    return {"name": item.name, "price": item.price}
```

### Pydantic Models

**Validação automática:**

```python
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(5, ge=1, le=20)
    temperature: float = Field(0.0, ge=0.0, le=2.0)

# FastAPI valida automaticamente:
# - query deve ter 3-500 caracteres
# - top_k deve estar entre 1 e 20
# - temperature deve estar entre 0.0 e 2.0

# Se inválido, retorna HTTP 422 com erro detalhado
```

### Documentação automática

FastAPI gera automaticamente:

**Swagger UI (`/docs`):**
- Interface interativa para testar API
- Documenta todos os endpoints
- Mostra request/response schemas

**ReDoc (`/redoc`):**
- Documentação alternativa (mais limpa)

### Async/Await

**Sync endpoint:**
```python
@app.get("/slow")
def slow_endpoint():
    time.sleep(5)  # Bloqueia thread!
    return {"message": "done"}
```

**Async endpoint:**
```python
@app.get("/fast")
async def fast_endpoint():
    await asyncio.sleep(5)  # Não bloqueia!
    return {"message": "done"}
```

**Quando usar async?**
- ✅ I/O bound (database, API calls, file read)
- ❌ CPU bound (processamento pesado, embeddings)

**Nossa API:**
- Endpoints são `async def` (preparados para futuro)
- Operações atuais são síncronas (embeddings, LLM) - OK
- Futuro: adicionar cache async (Redis)

### No nosso projeto

**Estrutura:**
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="RAG Q&A API",
    description="Question answering system for Brazilian government news using RAG",
    version="1.0.0"
)

# CORS (permitir frontend chamar API)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Models
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(5, ge=1, le=20)
    use_reranking: bool = True
    # ...

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    latency_ms: Dict[str, float]
    # ...

# Endpoints
@app.get("/")
def root():
    return {"name": "RAG Q&A API", "version": "1.0.0"}

@app.get("/health")
def health():
    # Check embedder, database
    return HealthResponse(status="ok", ...)

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    # Process query
    # Return QueryResponse
    ...
```

**Rodando:**
```bash
# Desenvolvimento (com reload)
uvicorn api.server:app --reload --port 8000

# Produção (com Gunicorn)
gunicorn api.server:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 12. Conceitos Avançados

### Context Window

**O que é:** Quantidade máxima de tokens que um LLM pode processar de uma vez.

**Limites típicos:**
- GPT-3.5: 4k tokens (~3k palavras)
- GPT-4: 8k / 32k tokens
- Claude 3: 200k tokens (~150k palavras, ~500 páginas!)
- Llama 3.1: 128k tokens

**No RAG:**
```
Context = [System Prompt] + [Retrieved Documents] + [Query]

Se context > window → precisa comprimir/truncar
```

**Nossa gestão:**
```python
def _build_context(self, results, max_tokens=8000):
    # Limite conservador (8k tokens = ~32k chars)
    max_chars = max_tokens * 4
    
    for result in results:
        if total_chars + chunk_chars > max_chars:
            break  # Para antes de exceder
```

### Token Counting

**Tokens ≠ Palavras ≠ Caracteres**

```
Texto: "Programa do CNPq para pesca"
Palavras: 5
Caracteres: 30
Tokens: ~8-10 (depende do tokenizer)
```

**Regra prática (português):**
- 1 token ≈ 4 caracteres
- 1 token ≈ 0.75 palavras

**Tokenizers diferentes:**
- GPT (tiktoken): ~1.3 tokens/palavra
- Claude (Claude tokenizer): ~1.2 tokens/palavra
- Llama (SentencePiece): ~1.4 tokens/palavra

**Contar tokens exatos:**
```python
import tiktoken

# GPT tokenizer
enc = tiktoken.encoding_for_model("gpt-4")
tokens = enc.encode("Programa do CNPq")
print(len(tokens))  # 8

# Claude - usar aproximação (não tem tokenizer público)
approx_tokens = len(text) // 4
```

### Temperature

**O que é:** Controla aleatoriedade da geração do LLM.

**Escala:** 0.0 a 2.0 (típico: 0.0 a 1.0)

**Como funciona:**
```
temperature = 0.0 → deterministico (sempre mesma resposta)
temperature = 0.5 → alguma variação
temperature = 1.0 → variação maior (criativo)
temperature = 2.0 → muito aleatório
```

**Quando usar:**
- **0.0**: RAG, classificação, Q&A factual (nosso caso)
- **0.3-0.5**: Escrita criativa com alguma consistência
- **0.7-1.0**: Brainstorming, geração de ideias
- **>1.0**: Experimentação, arte

**No nosso sistema:**
```python
temperature = 0.0  # Default
# Queremos respostas consistentes e factuais
```

### Latency Breakdown

**Nosso pipeline:**

```
Total Latency = Retrieval + Generation

Retrieval (200-500ms):
  - Query embedding: 100-200ms (BGE-M3 CPU)
  - Vector search: 50-200ms (PostgreSQL + IVFFlat)
  - Re-ranking (opcional): +600ms (ms-marco CPU)

Generation (2000-6000ms):
  - LLM inference: 2000-6000ms (depende do modelo)
  - Bedrock Haiku 4.5: ~2000-3000ms
  - Bedrock Sonnet 4.6: ~5000-7000ms
  - Ollama (CPU): ~100,000ms (110s)
  - Ollama (GPU): ~5000-10000ms esperado
```

**Gargalo:** LLM generation (80-90% do tempo total)

**Otimizações possíveis:**
- Cache de respostas (Redis)
- Modelo mais rápido (Haiku)
- GPU para Ollama
- Streaming (UX melhor, não reduz latência total)

### Cost Optimization

**Trade-off qualidade vs custo:**

| Abordagem | Custo/query | Qualidade | Latência |
|-----------|-------------|-----------|----------|
| Sonnet 4.6 | $0.005 | ⭐⭐⭐⭐⭐ | 5-7s |
| Haiku 4.5 | $0.007 | ⭐⭐⭐⭐ | 2-3s |
| Ollama (GPU) | $0.00 | ⭐⭐⭐ | 5-10s |
| Ollama (CPU) | $0.00 | ⭐⭐⭐ | 110s |

**Para produção (estimativas):**

**Cenário 1:** 10k queries/dia
- Haiku 4.5: $70/dia = $2100/mês
- GPU dedicada (A100): $1500/mês + $0/query
- **Vencedor:** GPU (se > 7.5k queries/dia)

**Cenário 2:** 1k queries/dia
- Haiku 4.5: $7/dia = $210/mês
- GPU dedicada: $1500/mês
- **Vencedor:** Bedrock

### Deduplicação de Sources

**Problema:** Múltiplos chunks do mesmo documento aparecem como sources separadas.

**Solução (implementada):**

```python
def _extract_sources(self, results):
    # Agrupar por document_id
    seen_docs = {}
    
    for result in results:
        doc_id = result.document_id
        
        if doc_id not in seen_docs:
            seen_docs[doc_id] = result
        elif result.score > seen_docs[doc_id].score:
            # Manter chunk com melhor score
            seen_docs[doc_id] = result
    
    # Retornar documentos únicos
    unique_results = sorted(seen_docs.values(), key=lambda x: x.score, reverse=True)
    
    return [make_source(r, i) for i, r in enumerate(unique_results, 1)]
```

**Resultado:**
- Antes: [Periferias, Periferias, Periferias, Periferias, Periferias]
- Depois: [Periferias, Agricultura, Saúde, ...]

**UX melhor** + **context ainda usa todos os chunks** (informação completa)

---

## 📚 Recursos Adicionais

### Papers Fundamentais

1. **RAG:** [Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401) (Lewis et al., 2020)
2. **DPR:** [Dense Passage Retrieval](https://arxiv.org/abs/2004.04906) (Karpukhin et al., 2020)
3. **BGE-M3:** [BGE M3-Embedding](https://arxiv.org/abs/2402.03216) (BAAI, 2024)
4. **Sentence-BERT:** [Sentence-BERT](https://arxiv.org/abs/1908.10084) (Reimers & Gurevych, 2019)

### Documentação Oficial

- **pgvector:** https://github.com/pgvector/pgvector
- **Sentence Transformers:** https://www.sbert.net/
- **FastAPI:** https://fastapi.tiangolo.com/
- **AWS Bedrock:** https://docs.aws.amazon.com/bedrock/
- **Ollama:** https://github.com/ollama/ollama
- **Anthropic Claude:** https://docs.anthropic.com/

### Benchmarks e Leaderboards

- **MTEB (embeddings):** https://huggingface.co/spaces/mteb/leaderboard
- **LMSys Chatbot Arena (LLMs):** https://chat.lmsys.org/
- **Papers With Code (diversos):** https://paperswithcode.com/

---

## 🎓 Conclusão

Este documento cobriu todas as tecnologias usadas no sistema RAG, desde os fundamentos matemáticos até a implementação prática.

**Stack completo:**
- **Storage:** PostgreSQL + pgvector
- **Embeddings:** BGE-M3 (Sentence Transformers)
- **Retrieval:** Vector search (IVFFlat) + Re-ranking (ms-marco)
- **LLM:** AWS Bedrock (Claude) + Ollama (local)
- **API:** FastAPI
- **Conceitos:** RAG, bi-encoders, cross-encoders, inference profiles

**Próximos passos para aprender mais:**
1. Ler papers fundamentais (RAG, DPR)
2. Experimentar com diferentes modelos (HuggingFace)
3. Explorar HNSW index (alternativa ao IVFFlat)
4. Implementar evaluation metrics (RAGAS, BERTScore)
5. Estudar prompt engineering avançado

**Revisões recomendadas:**
- Similaridade cosseno vs distância euclidiana
- IVFFlat vs HNSW (trade-offs)
- Bi-encoder vs cross-encoder (quando usar cada um)
- Context window management (truncation strategies)

---

**Última atualização:** 2026-05-29  
**Autor:** Claude Sonnet 4.6 + Luis Felipe de Moraes
