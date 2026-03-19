# Corpus de Teste - Embeddings

Este diretório contém o corpus de teste para avaliação dos modelos de embedding.

## Estrutura

```
data/
├── documents/           # 250 notícias do gov.br (10 categorias × 25 docs)
│   ├── doc_00_00.json
│   ├── doc_00_01.json
│   └── ...
├── queries/             # 60 queries de busca
│   ├── q001.json       # Queries gerais
│   ├── q002.json       # Queries com jargão BR
│   └── ...
├── annotations/         # Anotações de relevância query-documento
│   ├── query_q001.jsonl
│   ├── query_q002.jsonl
│   └── ...
└── README.md           # Este arquivo
```

## 1. Documentos (250 notícias)

### Distribuição por categoria

Conforme planejamento atualizado do Issue #1:

| Categoria            | Quantidade | Percentual |
|----------------------|------------|------------|
| Saúde                | 25         | 10%        |
| Educação             | 25         | 10%        |
| Economia             | 25         | 10%        |
| Meio Ambiente        | 25         | 10%        |
| Segurança Pública    | 25         | 10%        |
| Assistência Social   | 25         | 10%        |
| Infraestrutura       | 25         | 10%        |
| Cultura              | 25         | 10%        |
| Ciência e Tecnologia | 25         | 10%        |
| Agricultura          | 25         | 10%        |
| **TOTAL**            | **250**    | **100%**   |

### Formato do documento

```json
{
  "id": "doc_00_00",
  "title": "Ministério da Saúde lança campanha de vacinação",
  "content": "O Ministério da Saúde anunciou nesta terça-feira (15) o lançamento de uma nova campanha nacional de vacinação contra a gripe. A iniciativa visa imunizar 90% do público-alvo, que inclui idosos, crianças, gestantes e profissionais de saúde...",
  "category": "Saúde",
  "length": 245,
  "metadata": {
    "source_url": "https://www.gov.br/saude/...",
    "published_date": "2024-03-15",
    "author": "Ministério da Saúde"
  }
}
```

### Critérios para seleção

1. **Diversidade temática**: cobrir todas as 10 categorias igualmente
2. **Variação de tamanho**:
   - 30% curtos (100-300 palavras)
   - 50% médios (300-600 palavras)
   - 20% longos (600-1200 palavras)
3. **Representatividade**: notícias reais do portal gov.br
4. **Atualidade**: preferencialmente dos últimos 12 meses

### Nomenclatura

- Formato: `doc_CC_NN.json`
- `CC`: código da categoria (00-09)
- `NN`: número do documento na categoria (00-09)

Exemplos:
- `doc_00_00.json`: primeira notícia de Saúde
- `doc_01_05.json`: sexta notícia de Educação
- `doc_09_09.json`: décima notícia de Agricultura

## 2. Queries (60 buscas)

### Distribuição por tipo

| Tipo          | Quantidade | Percentual | Descrição                                  |
|---------------|------------|------------|--------------------------------------------|
| Geral         | 25         | ~42%       | Linguagem natural, sem termos técnicos     |
| Jargão BR     | 25         | ~42%       | Siglas e termos técnicos do gov BR         |
| Docs Longos   | 10         | ~16%       | Queries que remetem a documentos extensos  |
| **TOTAL**     | **60**     | **100%**   |                                            |

### Formato da query

```json
{
  "id": "q001",
  "text": "novas medidas para educação básica",
  "query_type": "geral",
  "expected_category": "Educação",
  "metadata": {
    "difficulty": "easy",
    "num_expected_results": 3
  }
}
```

### Tipos de query

**Queries Gerais (`geral`):** 25 queries
- Linguagem natural sem jargões
- Exemplos:
  - "políticas de saúde pública"
  - "programas de educação infantil"
  - "incentivos para agricultura familiar"
  - "campanhas de vacinação nacional"
  - "combate à desigualdade social"
  - "investimentos em infraestrutura"

**Queries com Jargão BR (`jargao_br`):** 25 queries
- Siglas e termos técnicos do governo brasileiro
- Exemplos:
  - "IPCA inflação meta fiscal"
  - "PAC infraestrutura obras"
  - "SUS APS atenção primária"
  - "FUNDEB recursos educação"
  - "INSS aposentadoria BPC"
  - "MEC ENEM FIES universidades"

**Queries para Docs Longos (`doc_longo`):** 10 queries
- Buscam documentos extensos e detalhados
- Exemplos:
  - "relatório completo orçamento federal"
  - "análise detalhada políticas ambientais"
  - "documento técnico reforma tributária"
  - "plano nacional desenvolvimento sustentável"

## 3. Anotações (ground truth)

### Formato da anotação

Arquivo: `annotations/query_q001.jsonl` (uma linha por documento anotado)

```jsonl
{"query_id": "q001", "doc_id": "doc_01_00", "relevance": 3, "notes": "Muito relevante - responde completamente"}
{"query_id": "q001", "doc_id": "doc_01_01", "relevance": 2, "notes": "Relevante - informação parcial"}
{"query_id": "q001", "doc_id": "doc_01_02", "relevance": 1, "notes": "Pouco relevante - menciona tema marginalmente"}
{"query_id": "q001", "doc_id": "doc_00_00", "relevance": 0, "notes": "Irrelevante - categoria diferente"}
```

### Escala de relevância

| Score | Descrição         | Critério                                           |
|-------|-------------------|----------------------------------------------------|
| 3     | Muito relevante   | Responde diretamente à query, alta utilidade       |
| 2     | Relevante         | Contém informação relacionada, útil                |
| 1     | Pouco relevante   | Menciona o tema tangencialmente                    |
| 0     | Irrelevante       | Não relacionado à query                            |

### Diretrizes para anotação

1. **Abrangência**: Anotar pelo menos 15 documentos por query (incluindo irrelevantes)
2. **Balanceamento**: Incluir documentos de todas as faixas de relevância
3. **Consistência**: Usar os mesmos critérios para todas as queries
4. **Documentação**: Campo `notes` com justificativa da relevância

**Estimativa de anotações:** 60 queries × 15 docs/query = **~900 anotações totais**

### Exemplo de anotação completa

Para a query `q003: "IPCA inflação meta fiscal"` (15 docs anotados):

```jsonl
{"query_id": "q003", "doc_id": "doc_02_00", "relevance": 3, "notes": "Discute IPCA e meta fiscal diretamente"}
{"query_id": "q003", "doc_id": "doc_02_01", "relevance": 3, "notes": "Análise detalhada da inflação e política monetária"}
{"query_id": "q003", "doc_id": "doc_02_02", "relevance": 3, "notes": "Banco Central anuncia meta IPCA para 2024"}
{"query_id": "q003", "doc_id": "doc_02_03", "relevance": 2, "notes": "Menciona IPCA mas foca em outro aspecto econômico"}
{"query_id": "q003", "doc_id": "doc_02_04", "relevance": 2, "notes": "Fala de meta fiscal, não menciona IPCA"}
{"query_id": "q003", "doc_id": "doc_02_05", "relevance": 2, "notes": "Política monetária e controle inflacionário"}
{"query_id": "q003", "doc_id": "doc_02_06", "relevance": 1, "notes": "Economia geral, menciona inflação superficialmente"}
{"query_id": "q003", "doc_id": "doc_02_07", "relevance": 1, "notes": "Orçamento federal com breve menção fiscal"}
{"query_id": "q003", "doc_id": "doc_00_00", "relevance": 0, "notes": "Saúde - totalmente não relacionado"}
{"query_id": "q003", "doc_id": "doc_01_00", "relevance": 0, "notes": "Educação - não relacionado"}
{"query_id": "q003", "doc_id": "doc_03_00", "relevance": 0, "notes": "Meio Ambiente - não relacionado"}
{"query_id": "q003", "doc_id": "doc_04_00", "relevance": 0, "notes": "Segurança Pública - não relacionado"}
{"query_id": "q003", "doc_id": "doc_06_00", "relevance": 1, "notes": "Infraestrutura menciona custo fiscal marginalmente"}
{"query_id": "q003", "doc_id": "doc_02_15", "relevance": 1, "notes": "Economia, contexto distante de IPCA"}
{"query_id": "q003", "doc_id": "doc_02_19", "relevance": 0, "notes": "Economia mas sobre comércio exterior"}
```

## 4. Preparação do Corpus

### Opção 1: Criar corpus de exemplo

```bash
cd ../scripts
python prepare_corpus.py --create-sample
```

Gera estrutura com dados placeholder para teste rápido.

### Opção 2: Preparar corpus real (RECOMENDADO)

**Passo 1: Coletar notícias**

1. Acessar portal gov.br
2. Selecionar 10 notícias de cada categoria
3. Copiar título e conteúdo completo
4. Criar arquivos JSON em `documents/`

**Passo 2: Criar queries**

1. Analisar as notícias coletadas
2. Formular 40 queries (15 gerais + 15 jargão + 10 docs longos)
3. Criar arquivos JSON em `queries/`

**Passo 3: Anotar relevâncias**

1. Para cada query, identificar documentos relevantes
2. Atribuir scores 0-3
3. Documentar justificativas
4. Criar arquivos JSONL em `annotations/`

### Script auxiliar

```python
# create_document.py - auxiliar para criar JSONs
import json

doc = {
    "id": "doc_00_00",
    "title": "Seu título aqui",
    "content": "Conteúdo completo da notícia...",
    "category": "Saúde",
    "length": len("Conteúdo completo da notícia...".split()),
    "metadata": {
        "source_url": "https://www.gov.br/...",
        "published_date": "2024-03-15"
    }
}

with open('documents/doc_00_00.json', 'w', encoding='utf-8') as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
```

## 5. Validação do Corpus

### Checklist

- [ ] 250 documentos criados (25 por categoria)
- [ ] 60 queries criadas (25 geral + 25 jargão + 10 longos)
- [ ] Anotações para todas as queries (mínimo 15 docs por query)
- [ ] Formato JSON válido em todos os arquivos
- [ ] IDs únicos e consistentes
- [ ] Categorias consistentes com as 10 definidas
- [ ] Mix de tamanhos: ~30% curtos, ~50% médios, ~20% longos

### Comandos para validar

```bash
cd ../scripts

# Ver estatísticas
python prepare_corpus.py --stats

# Exportar para CSV (facilita revisão)
python prepare_corpus.py --export ../data/corpus_validation

# Verificar arquivos
ls -l ../data/documents/ | wc -l  # Deve ser 251 (250 docs + 1 linha de cabeçalho)
ls -l ../data/queries/ | wc -l    # Deve ser 61 (60 queries + 1 linha de cabeçalho)
```

## 6. Próximos Passos

Após preparar o corpus:

1. **Validar dados**: `python prepare_corpus.py --stats`
2. **Executar avaliação**: `python run_evaluation.py`
3. **Analisar resultados**: ver `../results/`

## Referências

- [ROTEIRO_TESTES_EMBEDDINGS.md](../ROTEIRO_TESTES_EMBEDDINGS.md) - Especificação completa
- [prepare_corpus.py](../scripts/prepare_corpus.py) - Script de preparação
- [Portal Gov.br](https://www.gov.br/pt-br/noticias) - Fonte de notícias
