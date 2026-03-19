# Roteiro de Testes e Validações - Issue #1
## Comparativo de Modelos de Embedding PT-BR para Notícias Governamentais

> **Objetivo**: Identificar o melhor modelo de embedding para notícias governamentais brasileiras, considerando qualidade semântica, performance com jargão específico e custo-benefício computacional.
>
> **Timeline**: 3 semanas
>
> **Responsável**: Luis Felipe de Moraes, Cientista de Dados (Inspire 7)

---

## **Índice**

1. [Contexto e Motivação](#1-contexto-e-motivação)
2. [Modelos a Testar](#2-modelos-a-testar)
3. [Dimensões de Avaliação](#3-dimensões-de-avaliação)
4. [Datasets e Queries de Teste](#4-datasets-e-queries-de-teste)
5. [Métricas Quantitativas](#5-métricas-quantitativas)
6. [Avaliação Qualitativa](#6-avaliação-qualitativa)
7. [Benchmark de Performance](#7-benchmark-de-performance)
8. [Cronograma Detalhado](#8-cronograma-detalhado)
9. [Critérios de Decisão](#9-critérios-de-decisão)
10. [Entregáveis](#10-entregáveis)

---

## 1. Contexto e Motivação

### **O Problema:**
- **300k+ notícias** governamentais brasileiras já catalogadas no banco de dados
- Mais de **uma centena** de novas notícias raspadas diariamente dos órgãos de notícias
- **410 categorias** hierárquicas (3 níveis) - podendo aumentar em tamanho e complexidade
- Alto uso de **jargão específico** (MEC, SUS, INSS, PNLD, FUNDEB, etc)
- Necessidade de **busca semântica** eficiente e precisa

### **Casos de Uso Futuros:**
1. **Busca semântica** em corpus de notícias
2. **Clustering** automático por temas
3. **RAG** (Retrieval-Augmented Generation) - Issue #5
4. **Detecção de tendências** - Issue #10
5. **Classificação automática** (via embeddings)

### **Trade-offs Identificados:**

| Tipo | Vantagem | Desvantagem |
|------|----------|-------------|
| **Multilíngue** (BGE-M3, mE5) | Cobertura ampla, cross-lingual | Dilui capacidade entre 100 línguas, pode perder nuances PT-BR |
| **PT-específico** (Serafim, BERTimbau) | 100% capacidade para PT-BR, captura jargão brasileiro | Sem cross-lingual, menor diversidade de treino |

**Nossa hipótese:** Para jargão governamental denso, **PT-específico** pode ter vantagem sobre multilíngue.

---

## 2. Modelos a Testar

### **Grupo A: Multilíngues (Distilled)**

| Modelo | Dimensões | Max Tokens | Parâmetros | Características |
|--------|-----------|------------|------------|-----------------|
| **BAAI/bge-m3** | 1024 | 8192 | 568M | **3 tipos**: dense + sparse + colbert |
| **intfloat/multilingual-e5-large** | 1024 | 512 | 560M | Contrastive learning forte |
| **sentence-transformers/LaBSE** | 768 | 512 | 471M | Google, 109 línguas |

**Por que testar:**
- Estado da arte em benchmarks multilíngues
- BGE-M3: multi-functionality (dense/sparse/colbert) → ideal para jargão!
- E5: contrastive learning avançado
- LaBSE: baseline Google estabelecido
- Passíveis de **fine tunning** que pode mudar os resultados 

---

### **Grupo B: PT-BR Específicos** 

| Modelo | Dimensões | Max Tokens | Parâmetros | Características |
|--------|-----------|------------|------------|-----------------|
| **maritaca-ai/serafim-900m-portuguese** | 1536 | 512 | 900M | **Maior modelo PT-BR** |
| **neuralmind/bert-base-portuguese-cased** | 768 | 512 | 110M | BERTimbau clássico + pooling |
| **rufimelo/Legal-BERTimbau-sts-base** | 768 | 512 | 110M | Fine-tunado em STS PT |

**Por que testar:**
- Serafim: maior e mais recente modelo PT-BR (2024)
- BERTimbau: baseline estabelecido PT-BR
- Legal-BERTimbau: fine-tunado para similaridade (pode ser vantagem!)

---

### **Grupo C: Modelos Menores (Rápidos)** ⚡

| Modelo | Dimensões | Max Tokens | Parâmetros | Características |
|--------|-----------|------------|------------|-----------------|
| **sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2** | 384 | 512 | 118M | Pequeno, rápido |
| **intfloat/multilingual-e5-small** | 384 | 512 | 118M | E5 compacto |

**Por que testar:**
- Avaliar trade-off tamanho vs qualidade
- Opção para deployment com recursos limitados

---

### **Total: 8 modelos**

**Estratégia:**
1. Testar todos os 8 (fase exploratória)
2. Selecionar top-3 (k) para análise profunda
3. Fine-tuning do vencedor (opcional, Issue #2)

---

## 3. Dimensões de Avaliação

### **3.1 Qualidade Semântica** (peso: 40%)
- Capacidade de capturar significado semântico profundo
- Similaridade entre sinônimos ("governo" ↔ "executivo")
- Compreensão de contexto governamental

### **3.2 Jargão Governamental** (peso: 35%) **CRÍTICO!**
- Reconhecimento de siglas (MEC, SUS, INSS, FUNDEB, PNLD)
- Relações: "MEC" ↔ "Ministério da Educação" ↔ "educação"
- Termos técnicos (portaria, decreto, medida provisória)

### **3.3 Performance Computacional** (peso: 15%)
- Throughput (docs/segundo)
- Latência (tempo por documento)
- Uso de memória
- Escalabilidade

### **3.4 Documentos Longos** (peso: 10%)
- Como lida com notícias >512 tokens
- Qualidade de truncamento/janelamento


---

## 4. Datasets e Queries de Teste

### **4.1 Corpus de Notícias (para indexação)**

```python
# Usar subset representativo do corpus real
corpus_size = 10_000  # 10k notícias para testes iniciais

# Seleção estratificada:
# - 7% Economia
# - 7% Saúde
# - 7% Educação
# - 7% Segurança
# - 7% Meio Ambiente e Sustentabilidade
# - 7% Ciência, Tecnologia e Inovação
# - 7% Infraestrutura e Transportes
# - 7% Cultura, Artes e Patrimônio
# - 7% Esportes e Lazer
# - 7% Agricultura, Pecuária e Abastecimento
# - 30% Outros (Mix)

# Características:
# - Mix de notícias curtas (100-300 tokens) e longas (500-1500 tokens)
# - Alta densidade de jargão governamental
# - Diversidade de órgãos (MEC, MS, MJ, INSS, etc)
```

---

### **4.2 Queries de Teste - Categoria 1: Conceitos Universais**

**Objetivo:** Avaliar compreensão semântica geral

```python
queries_universais = [
    # Economia
    "políticas econômicas do governo federal",
    "investimentos em infraestrutura nacional",
    "controle de inflação e taxa de juros",

    # Saúde
    "programas de saúde pública",
    "distribuição de medicamentos hospitais",
    "campanhas de vacinação população",

    # Educação
    "políticas educacionais ensino básico",
    "investimento em escolas públicas",
    "formação de professores",

    # Social
    "benefícios sociais famílias baixa renda",
    "programas de transferência de renda",
    "combate à pobreza extrema",
]
```

**Esperado:** Multilíngues e PT-específicos devem ter performance similar (~85-90%)

---

### **4.3 Queries de Teste - Categoria 2: Jargão Governamental BR**

**Objetivo:** Avaliar captura de siglas e termos específicos brasileiros

```python
queries_jargao_br = [
    # Siglas de órgãos
    "portarias do MEC sobre educação",
    "programas do INSS para aposentados",
    "campanhas do SUS de vacinação",
    "medidas do Banco Central sobre Selic",

    # Siglas de programas
    "recursos do FUNDEB para municípios",
    "distribuição PNLD escolas públicas",
    "beneficiários do Bolsa Família",
    "financiamento FIES estudantes universitários",

    # Mix siglas + contexto
    "MEC anuncia mudanças no ENEM 2024",
    "INSS libera pagamento décimo terceiro",
    "Ministério da Saúde divulga dados COVID SUS",
    "Governo federal investe BNDES infraestrutura",

    # Termos técnicos jurídico-administrativos
    "portaria normativa ministério educação",
    "decreto presidencial medida provisória",
    "resolução conselho nacional política",
    "lei complementar reforma tributária",
]
```

**Hipótese:**
- PT-específicos: 85-90% (conhecem siglas brasileiras)
- Multilíngues com sparse (BGE-M3): 80-85% (sparse captura termos exatos)
- Multilíngues dense-only: 70-75% (lutam com siglas)

---

### **4.4 Queries de Teste - Categoria 3: Ambiguidades PT-BR**

**Objetivo:** Testar desambiguação em contexto brasileiro

```python
queries_ambiguas = [
    # "Banco" - instituição financeira vs assento vs margem
    "banco do governo políticas econômicas",  # Financeiro
    "banco de dados sistema informação",      # Dados

    # "Programa" - software vs iniciativa gov
    "programa governo combate pobreza",       # Iniciativa
    "programa computador sistema operacional", # Software

    # "Ministério" vs sigla
    "Ministério da Educação anuncia",         # Por extenso
    "MEC anuncia",                            # Sigla (deve achar mesmo doc!)

    # "Federal" vs "Estadual" vs "Municipal"
    "governo federal políticas nacionais",
    "governo estadual São Paulo medidas",
    "prefeitura municipal recursos locais",
]
```

**Esperado:** Modelos devem desambiguar por contexto

---

### **4.5 Queries de Teste - Categoria 4: Documentos Longos**

**Objetivo:** Avaliar performance com notícias extensas

```python
queries_docs_longos = [
    # Queries que requerem contexto longo
    "detalhes implementação programa educacional etapas cronograma recursos",
    "análise completa impacto reforma tributária setores economia",
    "histórico discussões aprovação lei complementar tramitação",
]

# Buscar em corpus com notícias >800 tokens
# Modelos com max_tokens=512 vão truncar
# BGE-M3 (8192 tokens) tem vantagem!
```

---

### **4.6 Ground Truth (Relevância Anotada)**

**Abordagem Híbrida:**

1. **Automática (70%)** - Usar Claude/LLMs para gerar relevância inicial
```python
# Para cada query + documento:
prompt = f"""
Query: {query}
Documento: {documento}

Qual a relevância deste documento para a query?
0 = Irrelevante
1 = Pouco relevante (menciona tema mas não responde)
2 = Relevante (responde parcialmente)
3 = Muito relevante (responde completamente)

Responda apenas o número.
"""

relevancia_automatica = claude(prompt)
```

2. **Manual (30%)** - Validação humana de subset crítico
```python
# Validar manualmente:
# - Top-10 resultados por query (5 queries × 10 docs = 50 docs)
# - Casos ambíguos (flagged por discrepância entre modelos)
# - Queries de jargão (críticas!)

# Total: ~150-200 anotações manuais (viável!)
```

---

## 5. Métricas Quantitativas

### **5.1 Métricas de Retrieval**

#### **NDCG@K (Normalized Discounted Cumulative Gain)**
```python
# Métrica PRINCIPAL para ranking

NDCG@5  # Top-5 resultados
NDCG@10 # Top-10 resultados (primária!)
NDCG@20 # Top-20 resultados

# Por que NDCG?
# - Considera POSIÇÃO do resultado (top-1 vale mais que top-10)
# - Aceita relevância GRADUADA (0,1,2,3) não apenas binária
# - Normalizado (comparável entre queries)

# Meta: NDCG@10 > 0.85 (85%)
```

#### **MAP (Mean Average Precision)**
```python
# Precisão média em todos os pontos de recall

MAP = mean([
    average_precision(query_1),
    average_precision(query_2),
    # ... todas as queries
])

# Complementa NDCG
# Meta: MAP > 0.80 (80%)
```

#### **MRR (Mean Reciprocal Rank)**
```python
# Posição do PRIMEIRO resultado relevante

# Query 1: primeiro relevante em posição 1 → 1/1 = 1.0
# Query 2: primeiro relevante em posição 3 → 1/3 = 0.33
# MRR = mean([1.0, 0.33, ...])

# Útil para avaliar: modelo coloca relevantes NO TOPO?
# Meta: MRR > 0.85
```

#### **Recall@K**
```python
# Dos N documentos relevantes, quantos estão no top-K?

Recall@10 = (relevantes no top-10) / (total relevantes)

# Meta: Recall@10 > 0.75 (75%)
```

---

### **5.2 Métricas por Categoria de Query**

```python
# Quebrar métricas por tipo de query:

resultados = {
    'universais': {
        'ndcg@10': [...],
        'map': [...],
        'mrr': [...],
    },
    'jargao_br': {  # ← CRÍTICO!
        'ndcg@10': [...],
        'map': [...],
        'mrr': [...],
    },
    'ambiguas': {
        'ndcg@10': [...],
        'map': [...],
        'mrr': [...],
    },
    'docs_longos': {
        'ndcg@10': [...],
        'map': [...],
        'mrr': [...],
    },
}

# Identificar em qual categoria cada modelo brilha/sofre
```

---

### **5.3 Análise Estatística**

```python
# Significância estatística das diferenças

from scipy.stats import wilcoxon, ttest_rel

# Comparar modelo A vs modelo B
# H0: Não há diferença significativa
# H1: Há diferença significativa

p_value = ttest_rel(scores_modelo_A, scores_modelo_B)

if p_value < 0.05:
    print("Diferença estatisticamente significativa!")
else:
    print("Diferença pode ser por acaso")

# Importante: não declarar "vencedor" se p > 0.05!
```

---

## 6. Avaliação Qualitativa

### **6.1 Análise de Casos Específicos**

Para cada modelo, analisar **manualmente** top-10 resultados de 5-10 queries críticas:

```python
query_critica = "programas do MEC para PNLD e FUNDEB"

# Para cada modelo:
# 1. Listar top-10 resultados
# 2. Anotar:
#    - Documento realmente relevante? (sim/não)
#    - Por que foi rankeado alto/baixo?
#    - Falso positivo? Falso negativo?
#    - Modelo entendeu siglas? (MEC, PNLD, FUNDEB)

# Exemplo de análise:
"""
BGE-M3:
Top-1: "MEC anuncia distribuição PNLD..." ✅ Perfeito! Sparse capturou siglas
Top-2: "Educação básica recebe recursos FUNDEB..." ✅ Bom! Dense capturou contexto
Top-3: "Ministério divulga calendário PNAE..." ⚠️ Relevante mas não PNLD/FUNDEB
...

Serafim:
Top-1: "Ministério da Educação lança PNLD..." ✅ Perfeito! Entendeu MEC=Ministério
Top-2: "FUNDEB amplia recursos municípios..." ✅ Excelente!
Top-3: "Governo federal investe educação..." ⚠️ Genérico demais
...
"""
```

---

### **6.2 Mapeamento de Embeddings (t-SNE/UMAP)** 🗺️

```python
# Visualizar embeddings em 2D para entender agrupamentos

from sklearn.manifold import TSNE
import matplotlib.pyplot as plt

# Gerar embeddings de sentenças chave
sentencas_teste = [
    "MEC anuncia",
    "Ministério da Educação divulga",
    "Educação básica",
    "SUS distribui vacinas",
    "Ministério da Saúde",
    "Saúde pública",
    "INSS paga benefícios",
    "Previdência Social",
    # ...
]

embeddings = model.encode(sentencas_teste)

# Reduzir para 2D
tsne = TSNE(n_components=2)
coords_2d = tsne.fit_transform(embeddings)

# Plotar
plt.scatter(coords_2d[:, 0], coords_2d[:, 1])
for i, txt in enumerate(sentencas_teste):
    plt.annotate(txt, (coords_2d[i, 0], coords_2d[i, 1]))

plt.title(f"Embeddings - {model_name}")
plt.savefig(f"viz_{model_name}.png")
```

**Análise:**
- "MEC" e "Ministério da Educação" estão próximos?
- Siglas ficam próximas dos termos por extenso?
- Domínios separados (saúde vs educação)?

---

### **6.3 Matriz de Confusão de Domínios**

```python
# Verificar se modelo confunde domínios similares

dominios = {
    'Educação': ["MEC", "PNLD", "FUNDEB", "ensino", "escolas"],
    'Saúde': ["SUS", "MS", "vacinação", "hospitais", "médicos"],
    'Previdência': ["INSS", "aposentadoria", "benefícios", "RGPS"],
    'Economia': ["Banco Central", "Selic", "inflação", "PIB"],
}

# Para query de Educação:
query_edu = "políticas do MEC"

# Top-10 resultados:
# - 7 são Educação
# - 2 são Saúde (confusão!)
# - 1 é Economia

# Construir matriz:
"""
                Educação  Saúde  Previdência  Economia
Query Educação      7       2        0           1
Query Saúde         1       8        0           1
...
"""
```

---

## 7. Benchmark de Performance

### **7.1 Throughput (docs/segundo)** ⚡

```python
# Medir velocidade de encoding

import time

corpus_test = ["texto exemplo..."] * 10_000  # 10k documentos

# Para cada modelo:
start = time.time()
embeddings = model.encode(
    corpus_test,
    batch_size=32,  # Fixar para comparação justa
    show_progress_bar=False
)
elapsed = time.time() - start

throughput = len(corpus_test) / elapsed
print(f"{model_name}: {throughput:.1f} docs/segundo")

# Meta: > 100 docs/segundo (aceitável para batch processing)
```

---

### **7.2 Latência (tempo por documento)** 

```python
# Medir latência individual (importante para tempo real)

import numpy as np

latencies = []
for doc in corpus_test[:100]:  # 100 docs
    start = time.time()
    emb = model.encode(doc)
    latency = time.time() - start
    latencies.append(latency)

# Estatísticas:
print(f"Média: {np.mean(latencies)*1000:.1f}ms")
print(f"Mediana: {np.median(latencies)*1000:.1f}ms")
print(f"P95: {np.percentile(latencies, 95)*1000:.1f}ms")
print(f"P99: {np.percentile(latencies, 99)*1000:.1f}ms")

# Meta: P99 < 500ms (para experiência interativa)
```

---

### **7.3 Uso de Memória**

```python
import psutil
import os

process = psutil.Process(os.getpid())

# Antes de carregar modelo
mem_before = process.memory_info().rss / 1024**2  # MB

# Carregar modelo
model = SentenceTransformer(model_name)

# Depois de carregar
mem_after = process.memory_info().rss / 1024**2  # MB

mem_model = mem_after - mem_before
print(f"{model_name}: {mem_model:.1f} MB")

# Também medir uso de GPU (se aplicável):
if torch.cuda.is_available():
    mem_gpu = torch.cuda.memory_allocated() / 1024**2
    print(f"GPU: {mem_gpu:.1f} MB")
```

---

### **7.4 Batch Size Scaling**

```python
# Como throughput escala com batch size?

batch_sizes = [1, 4, 8, 16, 32, 64, 128]

for bs in batch_sizes:
    start = time.time()
    embeddings = model.encode(corpus_test[:1000], batch_size=bs)
    elapsed = time.time() - start
    throughput = 1000 / elapsed

    print(f"Batch {bs:3d}: {throughput:6.1f} docs/s")

# Identificar batch size ótimo para cada modelo
```

---

### **7.5 Comparação CPU vs GPU**

```python
# Alguns modelos podem rodar bem em CPU
# Importante para deployment sem GPU

# CPU
model_cpu = SentenceTransformer(model_name, device='cpu')
throughput_cpu = benchmark(model_cpu)

# GPU (se disponível)
if torch.cuda.is_available():
    model_gpu = SentenceTransformer(model_name, device='cuda')
    throughput_gpu = benchmark(model_gpu)

    speedup = throughput_gpu / throughput_cpu
    print(f"GPU speedup: {speedup:.1f}x")
```

---

## 8. Cronograma Detalhado

### **Semana 1: Setup e Exploração Inicial** (5 dias úteis)

#### **Dia 1-2: Setup e Carregamento**
```
☐ Preparar ambiente (GPU, bibliotecas)
☐ Carregar e testar os 8 modelos
☐ Verificar compatibilidade e funcionamento básico
☐ Preparar corpus de 10k notícias
☐ Criar queries de teste (4 categorias)
```

#### **Dia 3-4: Testes Preliminares**
```
☐ Gerar embeddings do corpus (10k docs × 8 modelos)
☐ Implementar busca semântica básica
☐ Testar queries em cada modelo
☐ Primeiras impressões qualitativas
☐ Identificar problemas técnicos
```

#### **Dia 5: Análise Inicial**
```
☐ Comparar top-10 resultados entre modelos
☐ Identificar 3-4 modelos mais promissores
☐ Documentar descobertas iniciais
☐ Ajustar estratégia se necessário
```

**Entregável Semana 1:** Relatório preliminar + Top-4 modelos selecionados

---

### **Semana 2: Avaliação Quantitativa Profunda** (5 dias úteis)

#### **Dia 6-7: Ground Truth**
```
☐ Gerar relevância automática (Claude) para 50 queries
☐ Anotar manualmente subset crítico (150-200 docs)
☐ Validar consistência das anotações
☐ Criar dataset final de avaliação
```

#### **Dia 8-9: Métricas de Retrieval**
```
☐ Implementar NDCG@10, MAP, MRR, Recall@K
☐ Calcular métricas para 8 modelos
☐ Quebrar por categoria de query
☐ Análise estatística (significância)
☐ Gerar tabelas comparativas
```

#### **Dia 10: Benchmark de Performance** ⚡
```
☐ Throughput e latência
☐ Uso de memória (CPU/GPU)
☐ Batch size scaling
☐ Trade-off qualidade vs velocidade
```

**Entregável Semana 2:** Tabelas de métricas + Benchmarks + Top-3 finalistas

---

### **Semana 3: Avaliação Qualitativa e Síntese** (5 dias úteis)

#### **Dia 11-12: Análise Qualitativa**
```
☐ Análise manual de casos específicos (5-10 queries críticas)
☐ Visualizações (t-SNE/UMAP de embeddings)
☐ Matriz de confusão de domínios
☐ Análise de jargão (MEC, SUS, INSS, etc)
☐ Documentar pontos fortes/fracos de cada modelo
```

#### **Dia 13: Testes com BGE-M3 Multi-Functionality**
```
☐ Testar Dense vs Sparse vs ColBERT separadamente
☐ Testar combinações híbridas (pesos diferentes)
☐ Comparar com outros modelos dense-only
☐ Avaliar ganho do multi-functionality
```

#### **Dia 14: Síntese e Recomendação**
```
☐ Consolidar todos os resultados
☐ Criar visualizações finais (gráficos, tabelas)
☐ Escrever RESEARCH_EMBEDDING_MODELS.md
☐ Definir recomendação técnica
☐ Preparar apresentação executiva
```

#### **Dia 15: Buffer e Refinamento**
```
☐ Revisar documentação
☐ Ajustar visualizações
☐ Preparar apresentação
☐ Responder dúvidas finais
```

**Entregável Semana 3:** Documento final + Apresentação + Recomendação técnica

---

## 9. Critérios de Decisão

### **Sistema de Pontuação (0-100 pontos)**

| Critério | Peso | Como Medir |
|----------|------|------------|
| **NDCG@10 Geral** | 25 pts | Média de todas as queries |
| **NDCG@10 Jargão BR** | 25 pts | Média de queries com siglas (CRÍTICO) |
| **MAP** | 10 pts | Mean Average Precision |
| **MRR** | 5 pts | Mean Reciprocal Rank |
| **Performance (Throughput)** | 15 pts | docs/segundo (normalizado) |
| **Latência P99** | 10 pts | Tempo p99 (quanto menor, melhor) |
| **Documentos Longos** | 10 pts | NDCG@10 em docs >512 tokens |

**Total:** 100 pontos

### **Cálculo de Score:**

```python
def calcular_score(modelo):
    score = 0

    # NDCG@10 Geral (25 pts)
    # 0.85+ = 25pts, 0.75-0.85 = 15-25pts, <0.75 = 0-15pts
    score += normalize(modelo.ndcg_geral, min=0.70, max=0.90) * 25

    # NDCG@10 Jargão BR (25 pts) CRÍTICO - Peso aumentado!
    score += normalize(modelo.ndcg_jargao, min=0.70, max=0.90) * 25

    # MAP (10 pts)
    score += normalize(modelo.map, min=0.70, max=0.90) * 10

    # MRR (5 pts)
    score += normalize(modelo.mrr, min=0.75, max=0.95) * 5

    # Throughput (15 pts)
    # 100+ docs/s = 15pts, 50-100 = 10pts, <50 = 5pts
    score += normalize(modelo.throughput, min=50, max=150) * 15

    # Latência P99 (10 pts)
    # <100ms = 10pts, 100-500ms = 5-10pts, >500ms = 0-5pts
    score += normalize(modelo.latency_p99, min=500, max=100, reverse=True) * 10

    # Docs longos (10 pts)
    score += normalize(modelo.ndcg_longos, min=0.60, max=0.85) * 10

    return round(score, 1)
```

---

### **Thresholds de Decisão:**

```
95-100 pontos: EXCELENTE - Deploy imediato
85-94 pontos: MUITO BOM - Deploy recomendado
75-84 pontos: BOM - Considerar fine-tuning
65-74 pontos: RAZOÁVEL - Fine-tuning necessário
<65 pontos: INSUFICIENTE - Não recomendado
```

---

### **Critérios de Desempate:**

Se dois modelos ficarem próximos (diferença <5 pontos):

1. **Priorizar NDCG@10 Jargão BR** (mais crítico para o caso de uso)
2. **Priorizar Facilidade de Manutenção** (PT-específico vs multilíngue)
3. **Considerar Roadmap Futuro** (fine-tuning, expansão cross-lingual)

---

### **Cenários de Decisão:**

#### **Cenário A: BGE-M3 vence em tudo**
```
Score: 92/100
NDCG@10: 0.88 (geral), 0.86 (jargão)
Throughput: 120 docs/s

Decisão: Deploy BGE-M3 
Justificativa: Melhor overall, multi-functionality é vantagem
```

#### **Cenário B: Serafim melhor em jargão, BGE-M3 melhor em geral**
```
Serafim: Score 86/100, NDCG jargão: 0.89 
BGE-M3:  Score 88/100, NDCG jargão: 0.84

Decisão: Serafim (jargão é crítico!)
Justificativa: Priorizar jargão BR > overall performance
```

#### **Cenário C: Empate técnico**
```
Serafim: Score 85/100 (PT-específico)
BGE-M3:  Score 86/100 (multilíngue)

Decisão: Testar ambos em produção (A/B test)
OU: Escolher Serafim (mais fácil fine-tuning futuro)
```

#### **Cenário D: Nenhum alcança meta (NDCG < 0.80)**
```
Melhor modelo: Score 72/100, NDCG@10: 0.78

Decisão: Partir para Issue #2 (Fine-tuning)
Baseline: melhor modelo atual
Target: NDCG@10 > 0.85 após fine-tuning
```

---

## 10. Entregáveis

### **10.1 Documento de Pesquisa**

**Arquivo:** `RESEARCH_EMBEDDING_MODELS.md`

**Estrutura:**
```markdown
# Comparativo de Modelos de Embedding PT-BR

## Executive Summary
- Recomendação: [Modelo X]
- Score: [Y/100]
- Justificativa em 3 linhas

## Introdução
- Contexto do projeto
- Objetivo da pesquisa
- Hipóteses

## Metodologia
- Modelos testados
- Datasets e queries
- Métricas utilizadas

## Resultados Quantitativos
- Tabela comparativa (8 modelos)
- Gráficos de performance
- Análise estatística

## Resultados Qualitativos
- Casos específicos
- Visualizações de embeddings
- Análise de jargão

## Benchmark de Performance
- Throughput e latência
- Trade-offs identificados

## Discussão
- Pontos fortes/fracos de cada modelo
- Trade-off multilíngue vs PT-específico
- Implicações para o projeto

## Conclusões e Recomendações
- Modelo recomendado
- Justificativa detalhada
- Próximos passos (fine-tuning?)

## Apêndices
- Detalhes técnicos
- Queries completas
- Configurações de treino/teste
```

---

### **10.2 Notebook Jupyter**

**Arquivo:** `embedding_comparison.ipynb` (já criado!)

**Conteúdo:**
- Código completo e reproduzível
- Visualizações inline
- Análises exploratórias
- Células de markdown explicativas

**Formato:**
- Runnable end-to-end
- Outputs salvos (gráficos, tabelas)
- Comentários detalhados

---

### **10.3 Apresentação Executiva**

**Arquivo:** `APRESENTACAO_EMBEDDINGS.pdf` (ou .qmd → .html)

**Slides (15-20):**
1. Contexto e Objetivos
2. Desafio Técnico (jargão, 300k docs, etc)
3. Modelos Avaliados (8 modelos, 3 categorias)
4. Metodologia de Teste
5. Resultados Quantitativos (tabela comparativa)
6. Análise de Jargão Governamental
7. Performance Computacional
8. Trade-offs Identificados
9. Casos de Uso Específicos (exemplos qualitativos)
10. **Recomendação Técnica** (modelo vencedor)
11. Justificativa da Escolha
12. Próximos Passos (deployment, fine-tuning?)
13. Q&A

---

### **10.4 Datasets e Artefatos**

```
source/embeddings/
├── data/
│   ├── corpus_10k.parquet              # Corpus de teste
│   ├── queries_test.json               # Queries categorizadas
│   └── ground_truth.json               # Relevância anotada
│
├── results/
│   ├── embeddings/
│   │   ├── bge_m3_corpus.npy           # Embeddings por modelo
│   │   ├── serafim_corpus.npy
│   │   └── ...
│   │
│   ├── metrics/
│   │   ├── ndcg_results.csv            # Métricas detalhadas
│   │   ├── map_results.csv
│   │   ├── mrr_results.csv
│   │   └── benchmark_performance.csv
│   │
│   └── visualizations/
│       ├── ndcg_comparison.png         # Gráficos
│       ├── tsne_embeddings_bge_m3.png
│       ├── confusion_matrix_domains.png
│       └── throughput_comparison.png
│
└── notebooks/
    └── embedding_comparison.ipynb       # Notebook completo
```

---

### **10.5 Script de Reprodução**

**Arquivo:** `run_full_evaluation.py`

```python
"""
Script para reproduzir avaliação completa de embeddings.

Usage:
    python run_full_evaluation.py --models all --output results/

Options:
    --models: 'all', 'multilingual', 'pt-specific', ou lista específica
    --corpus-size: Tamanho do corpus (padrão: 10000)
    --queries: Arquivo JSON com queries de teste
    --output: Diretório para salvar resultados
    --device: 'cuda' ou 'cpu'
"""

# Permite reproduzir toda a avaliação com um comando!
```

---

## **Checklist Final**

Antes de considerar Issue #1 completa:

### **Execução:**
- [ ] 8 modelos testados
- [ ] 50+ queries avaliadas (4 categorias)
- [ ] Ground truth criado (automático + manual)
- [ ] Métricas calculadas (NDCG, MAP, MRR, Recall)
- [ ] Benchmark de performance realizado
- [ ] Análise qualitativa completa

### **Análise:**
- [ ] Comparação estatisticamente significativa
- [ ] Trade-offs identificados e documentados
- [ ] Casos específicos analisados
- [ ] Visualizações criadas (t-SNE, gráficos)
- [ ] Jargão governamental avaliado em detalhe

### **Documentação:**
- [ ] RESEARCH_EMBEDDING_MODELS.md completo
- [ ] Notebook com código reproduzível
- [ ] Apresentação executiva preparada
- [ ] Datasets e artefatos salvos
- [ ] Script de reprodução criado

### **Decisão:**
- [ ] Modelo recomendado definido
- [ ] Justificativa técnica clara
- [ ] Score calculado (0-100)
- [ ] Próximos passos mapeados
- [ ] Aprovação do time técnico

---

## **Expectativa de Resultados**

### **Hipótese Central:**

```python
# Ranking esperado (hipótese a validar):

1. Serafim-900M ou BGE-M3          # 88-92/100 ⭐⭐⭐
   - Excelente em jargão BR
   - Alta qualidade geral

2. mE5-large                        # 82-86/100 ⭐⭐
   - Bom equilíbrio overall
   - Luta com siglas específicas

3. LaBSE                            # 78-82/100 ⭐
   - Baseline sólido
   - Sem diferenciais marcantes

4-6. BERTimbau, Legal-BERT, outros # 72-78/100 ⚠️
   - Modelos menores/mais antigos
   - Podem surpreender em PT

7-8. MiniLM, E5-small              # 68-74/100 ⚠️
   - Trade-off tamanho/qualidade
   - Bons para recursos limitados
```

### **Descobertas Esperadas:**

1. **BGE-M3 multi-functionality** será vantagem clara para jargão (sparse captura siglas)
2. **Serafim** terá melhor compreensão de nuances PT-BR específicas
3. **Gap** entre multilíngue e PT-específico será **menor que 5%** em geral, mas **>10%** em jargão
4. **Documentos longos** (>512 tokens) favorecerão BGE-M3 (8192 max tokens)
5. **Performance** será similar entre modelos grandes (50-150 docs/s)

### **Perguntas a Responder:**

1. Multilíngue é "suficiente" para gov.br ou PT-específico é necessário?
2. Multi-functionality (BGE-M3) compensa complexidade adicional?
3. Modelos menores (MiniLM, E5-small) são viáveis para produção?
4. Fine-tuning será necessário ou modelos prontos bastam?
5. Qual modelo tem melhor custo-benefício overall?

---

## **Próximos Passos Após Issue #1**

### **Se modelo alcançar meta (NDCG@10 > 0.85):**
```
Issue #1: COMPLETA
→  Issue #8: Integração com Vector DB (Typesense/ChromaDB)
→  Issue #5: Sistema RAG com embedding vencedor
→  Deploy em produção!
```

### **Se modelo não alcançar meta (NDCG@10 < 0.85):**
```
Issue #1: BASELINE estabelecido
→  Issue #2: Fine-tuning do melhor modelo
   - Dados: Coletar 5k-50k pares de similaridade
   - Objetivo: NDCG@10 > 0.85
   - Timeline: 2-3 semanas
→  Re-avaliar após fine-tuning
```

### **Investigações Adicionais (Opcional):**
```
Hybrid Search (embeddings + BM25)
Query expansion com LLMs
Hard negative mining
Domain-specific tokenizer
```

---

## **Referências e Recursos**

### **Papers Fundamentais:**
1. Sentence-BERT (Reimers & Gurevych, 2019)
2. Making Monolingual Embeddings Multilingual (Reimers, 2020)
3. BGE-M3 (BAAI, 2024)
4. Text Embeddings by Weakly-Supervised Contrastive Pre-training (E5, 2022)

### **Benchmarks:**
1. MTEB (Massive Text Embedding Benchmark)
2. BEIR (Benchmark for Information Retrieval)
3. STS Benchmark (Semantic Textual Similarity)

### **Ferramentas:**
1. HuggingFace Transformers & sentence-transformers
2. FAISS (vector search)
3. Pandas/Polars (data manipulation)
4. Matplotlib/Seaborn (visualização)

---

**Última atualização:** 2026-03-12
**Versão:** 1.0
