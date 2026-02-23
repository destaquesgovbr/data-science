# Benchmark para Curadoria Humana

Este guia explica como rodar o benchmark de curadoria e revisar manualmente as classificações das 3 abordagens.

## 🎯 Objetivo

Gerar uma planilha Excel com 50 notícias classificadas pelas 3 abordagens (Claude, RAG, BERT) para que você possa:
1. Comparar visualmente as classificações lado-a-lado
2. Avaliar qual abordagem teve melhor resultado em cada notícia
3. Documentar discordâncias e casos interessantes
4. Gerar dados para apresentação ao gestor

## 🚀 Como Usar

### 1. Instalar Dependências

```bash
# Da raiz do projeto
poetry install --extras "rag ml"
poetry install  # Para instalar openpyxl
```

**O que instala:**
- `sentence-transformers` - Para RAG
- `faiss-cpu` - Para RAG
- `torch` - Para BERT
- `openpyxl` - Para gerar Excel

### 2. Rodar o Benchmark

```bash
poetry run python source/news-enrichment/benchmarks/benchmark_curadoria.py
```

**Duração estimada:** 5-10 minutos
- Claude: ~4s por notícia (50 × 4s = 3-4min)
- RAG: ~5s por notícia (50 × 5s = 4-5min)
- BERT: ~0.1s por notícia (50 × 0.1s = 5s)
- Total: ~8-10 minutos

### 3. Arquivos Gerados

O script gera 3 arquivos no diretório `data/`:

#### 📊 `curadoria_3_abordagens_TIMESTAMP.xlsx`
**Arquivo principal para curadoria**

Colunas:
- `unique_id` - ID da notícia
- `titulo` - Título da notícia
- `conteudo_preview` - Primeiros 200 caracteres
- `claude_categoria` - Categoria mais específica (Claude)
- `claude_nivel_1` - Nível 1 da taxonomia (Claude)
- `claude_nivel_2` - Nível 2 da taxonomia (Claude)
- `rag_categoria` - Categoria mais específica (RAG)
- `rag_nivel_1` - Nível 1 da taxonomia (RAG)
- `rag_nivel_2` - Nível 2 da taxonomia (RAG)
- `bert_categoria` - Categoria mais específica (BERT)
- `bert_nivel_1` - Nível 1 da taxonomia (BERT)
- `bert_nivel_2` - Nível 2 da taxonomia (BERT)
- `concordancia` - Status de concordância
- `observacoes` - **Para você preencher**
- `avaliacao_curador` - **Para você preencher**

#### 📄 `curadoria_3_abordagens_TIMESTAMP.csv`
Backup em CSV (mesmas colunas)

#### 📦 `curadoria_3_abordagens_TIMESTAMP.json`
Conteúdo completo das notícias + classificações (para consulta)

## 📋 Como Fazer a Curadoria

### Passo 1: Abrir o Excel

```bash
# Localizar o arquivo mais recente
ls -lt data/curadoria_3_abordagens_*.xlsx | head -1

# Abrir no LibreOffice/Excel
libreoffice data/curadoria_3_abordagens_XXXXXXXX_XXXXXX.xlsx
```

### Passo 2: Revisar Cada Linha

Para cada notícia:

1. **Ler o título e conteúdo**
   - Use o conteúdo_preview para contexto rápido
   - Consulte o JSON se precisar do conteúdo completo

2. **Comparar as 3 classificações**
   - Claude, RAG e BERT escolheram categorias similares?
   - Se discordam, qual parece mais correta?

3. **Preencher "observacoes"**
   - Anote qual classificação está correta/incorreta
   - Documente por que houve discordância
   - Exemplos:
     - "Claude correto, BERT confundiu com categoria X"
     - "Todas corretas"
     - "RAG filtrou a categoria correta antes do LLM"

4. **Preencher "avaliacao_curador"**
   - Sua avaliação final: qual abordagem foi melhor?
   - Opções sugeridas:
     - "Claude melhor"
     - "RAG melhor"
     - "BERT melhor"
     - "Todas corretas"
     - "Todas incorretas"
     - "Ambíguo"

### Passo 3: Analisar Estatísticas

Após preencher todas as linhas, calcule:

```python
import polars as pl

# Carregar planilha preenchida
df = pl.read_excel("data/curadoria_3_abordagens_XXXXXXXX_XXXXXX.xlsx")

# Contar avaliações
df.group_by("avaliacao_curador").len().sort("len", descending=True)

# Exemplos:
# Claude melhor: 35 notícias (70%)
# Todas corretas: 10 notícias (20%)
# BERT melhor: 3 notícias (6%)
# RAG melhor: 2 notícias (4%)
```

## 📊 Métricas para Análise

### 1. Taxa de Concordância

```
Concordância Total: X% das notícias
  → Todas 3 abordagens concordaram

Discordância Parcial: Y% das notícias
  → 2 de 3 concordaram

Discordância Total: Z% das notícias
  → Todas diferentes
```

### 2. Acurácia por Abordagem

Após curadoria manual, calcule:

```
Claude correto: X/50 (Y%)
RAG correto: A/50 (B%)
BERT correto: M/50 (N%)
```

### 3. Tipos de Erro

Documente padrões:
- "BERT confunde Educação ↔ Cultura (5 casos)"
- "RAG filtra categoria correta em 3 casos"
- "Claude ambíguo em notícias políticas (2 casos)"

## 🎓 Usando os Dados na Apresentação

### Slide 1: Concordância

```
CONCORDÂNCIA ENTRE ABORDAGENS:

✓ Todas concordam: 75% (38/50)
  → Indica que as 3 abordagens são consistentes

⚠ Discordância parcial: 20% (10/50)
  → Casos ambíguos ou categorias próximas

✗ Todas diferentes: 5% (2/50)
  → Notícias difíceis de classificar
```

### Slide 2: Acurácia (após curadoria)

```
ACURÁCIA (50 notícias, curadoria humana):

Claude:  46/50 (92%) ✓ Melhor
RAG:     45/50 (90%)
BERT:    38/50 (76%) - Sem dados de treino
```

### Slide 3: Casos Interessantes

**Exemplo 1: RAG filtrou categoria correta**
- Notícia: "Ministério da Educação anuncia..."
- Claude: Educação > Ensino Superior ✓
- RAG: Educação > Ensino Médio ✗ (filtrou Ensino Superior)
- BERT: Educação > Ensino Superior ✓

**Conclusão:** RAG pode remover categorias corretas na filtragem.

### Slide 4: Recomendação

```
RESULTADO DA CURADORIA:

✅ Claude: Melhor acurácia (92%)
✅ Consistente com RAG (90% concordância)
⚠️ BERT: Precisa de dados de treino
❌ RAG: Complexidade sem ganhos
```

## 🔧 Customizações

### Alterar Número de Notícias

Editar `benchmark_curadoria.py`:

```python
# Linha ~408
N_NEWS = 50  # Alterar para 100, 200, etc.
```

### Alterar Seed (reprodutibilidade)

```python
# Linha ~409
SEED = 42  # Alterar para gerar amostra diferente
```

### Alterar Top-K do RAG

```python
# Linha ~370 (dentro da função classify_with_rag)
classifier = NewsClassifierRAG(
    taxonomy_path=str(arvore_path),
    top_k=30,  # Alterar de 50 para 30, por exemplo
    verbose=False
)
```

## 📝 Exemplo de Planilha Preenchida

| titulo | claude_categoria | rag_categoria | bert_categoria | concordancia | observacoes | avaliacao_curador |
|--------|------------------|---------------|----------------|--------------|-------------|-------------------|
| Governo anuncia reforma tributária | Economia > Impostos | Economia > Impostos | Política > Governo | ⚠ Discordância parcial | Claude/RAG corretos. BERT confundiu por mencionar "Governo" | Claude melhor |
| MEC lança programa de bolsas | Educação > Ensino Superior | Educação > Ensino Superior | Educação > Ensino Superior | ✓ Todas concordam | Todas corretas | Todas corretas |

## ⚠️ Troubleshooting

### Erro: "openpyxl não instalado"

```bash
poetry install
# ou
pip install openpyxl
```

### Erro: "Dataset não encontrado"

O script procura por:
1. `data/govbrnews_full.parquet` (preferencial)
2. `data/sample_enriched.parquet` (alternativa)
3. `data/sample_enriched_otimizado_500.parquet` (alternativa)

Certifique-se de ter pelo menos um desses arquivos.

### BERT não disponível

Se o modelo BERT não foi treinado:
```bash
poetry run python source/news-enrichment/train_bert_classifier.py
```

**Nota:** Treinar BERT requer > 20.000 notícias rotuladas.

### Planilha muito grande no Excel

Se 50 notícias tornam a planilha difícil de manusear:
- Use filtros do Excel para focar em discordâncias
- Ou reduza para N_NEWS = 20

## 📚 Arquivos Relacionados

- [benchmark_triplo.py](benchmark_triplo.py) - Benchmark automático completo
- [ABORDAGENS_COMPARADAS.md](../ABORDAGENS_COMPARADAS.md) - Análise técnica
- [GUIA_APRESENTACAO_GESTOR.md](../GUIA_APRESENTACAO_GESTOR.md) - Roteiro de apresentação
- [SUMARIO_EXECUTIVO_1PG.md](../SUMARIO_EXECUTIVO_1PG.md) - Resumo de 1 página

## ✅ Checklist

Antes de apresentar ao gestor:

- [ ] Benchmark rodado com 50 notícias
- [ ] Planilha Excel gerada
- [ ] Curadoria manual concluída (50/50 linhas)
- [ ] Estatísticas calculadas (concordância, acurácia)
- [ ] Casos interessantes documentados (3-5 exemplos)
- [ ] Gráficos/tabelas preparados para slides
- [ ] Recomendação clara com base nos dados

---

**Boa curadoria! 📊**

Os dados vão falar por você. 🎯
