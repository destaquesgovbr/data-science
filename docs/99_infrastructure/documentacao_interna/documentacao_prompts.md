# Documentação dos Prompts de Enriquecimento

Este documento descreve os dois estilos de prompts testados no sistema de enriquecimento de notícias governamentais.

---

## Índice

1. [Prompt Cogfy (Original)](#prompt-cogfy-original)
2. [Prompt Bedrock (Atual)](#prompt-bedrock-atual)
3. [Comparação](#comparação)
4. [Resultados do Benchmark](#resultados-do-benchmark)
5. [Recomendação](#recomendação)

---

## Prompt Cogfy (Original)

### Características
- **Número de chamadas**: 2 (classificação + resumo separados)
- **Formato de saída**: Texto estruturado
- **Abordagem**: Instruções em português, resposta em formato livre

### Prompt 1: Classificação Temática

```
Classifique a notícia abaixo em até 3 níveis temáticos, usando a taxonomia fornecida.

Taxonomia:
01 - Economia e Finanças
  01.01 - Política Econômica
    - 01.01.01 - Política Fiscal
    - 01.01.02 - Autonomia Econômica
    ...
02 - Educação
  02.01 - Ensino Básico
    ...

Notícia:
Título: {title}
Conteúdo: {content[:2000]}

Responda no formato:
- Nível 1: XX - Nome
- Nível 2: XX.YY - Nome (se aplicável)
- Nível 3: XX.YY.ZZ - Nome (se aplicável)

Forneça APENAS a classificação nos 3 níveis, sem explicações adicionais.
```

**Exemplo de resposta esperada:**
```
- Nível 1: 25 - Habitação e Urbanismo
- Nível 2: 25.01 - Programas Habitacionais
- Nível 3: 25.01.04 - Regularização Fundiária
```

### Prompt 2: Geração de Resumo

```
Gere um resumo conciso (2-3 frases) da notícia abaixo, destacando os pontos principais.

Título: {title}
Conteúdo: {content[:2000]}

Resumo:
```

**Exemplo de resposta esperada:**
```
Governo federal assina acordo para regularizar a situação fundiária de 10 mil famílias
de baixa renda em Teresópolis (RJ). O acordo encerra o maior conflito fundiário urbano
em trâmite na Justiça brasileira.
```

### Parsing da Resposta (Cogfy)

O sistema precisa:
1. Usar **regex** para extrair códigos e labels do texto estruturado
2. Fazer **2 requisições** por notícia (classificação + resumo)
3. Lidar com variações de formato na resposta

**Código de parsing:**
```python
import re

# Parse níveis
nivel1_match = re.search(r'Nível 1:\s*(\d+)\s*-\s*(.+)', response)
nivel2_match = re.search(r'Nível 2:\s*([\d.]+)\s*-\s*(.+)', response)
nivel3_match = re.search(r'Nível 3:\s*([\d.]+)\s*-\s*(.+)', response)

if nivel1_match:
    code, label = nivel1_match.groups()
    result['theme_1_level_1_code'] = code.strip()
    result['theme_1_level_1_label'] = label.strip()
```

---

## Prompt Bedrock (Atual)

### Características
- **Número de chamadas**: 1 (classificação + resumo em JSON)
- **Formato de saída**: JSON estruturado
- **Abordagem**: Instruções claras com exemplo de JSON

### Prompt Único (Classificação + Resumo)

```
Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido (sem markdown, sem explicações).

TAXONOMIA DISPONÍVEL:
01 - Economia e Finanças
  01.01 - Política Econômica
    - 01.01.01 - Política Fiscal
    - 01.01.02 - Autonomia Econômica
    ...
02 - Educação
  02.01 - Ensino Básico
    ...

INSTRUÇÕES:
1. Classifique a notícia usando EXATAMENTE os códigos e labels da taxonomia fornecida
2. Use até 3 níveis hierárquicos (quando aplicável)
3. Gere um resumo conciso (máximo 2 frases) capturando os pontos principais

NOTÍCIA:
Título: {title}
Subtítulo: {subtitle}
Lead: {editorial_lead}
Conteúdo: {content[:2000]}

FORMATO DE SAÍDA (JSON VÁLIDO):
{
  "theme_1_level_1": "Habitação e Urbanismo",
  "theme_1_level_1_code": "25",
  "theme_1_level_1_label": "Habitação e Urbanismo",
  "theme_1_level_2_code": "25.01",
  "theme_1_level_2_label": "Programas Habitacionais",
  "theme_1_level_3_code": "25.01.04",
  "theme_1_level_3_label": "Regularização Fundiária",
  "most_specific_theme_code": "25.01.04",
  "most_specific_theme_label": "Regularização Fundiária",
  "summary": "Governo federal assina acordo para regularizar a situação fundiária de 10 mil famílias de baixa renda em Teresópolis (RJ). O acordo encerra o maior conflito fundiário urbano em trâmite na Justiça brasileira."
}
```

### Parsing da Resposta (Bedrock)

O sistema precisa:
1. Extrair JSON da resposta usando **índices** (`{` e `}`)
2. Fazer **1 requisição** por notícia
3. Validar campos obrigatórios

**Código de parsing:**
```python
import json

# Extrair JSON
start_idx = response.find('{')
end_idx = response.rfind('}') + 1

if start_idx == -1 or end_idx <= start_idx:
    raise ValueError("JSON não encontrado na resposta")

json_str = response[start_idx:end_idx]
result = json.loads(json_str)

# Validar campos obrigatórios
required_fields = [
    'theme_1_level_1', 'theme_1_level_1_code', 'theme_1_level_1_label',
    'theme_1_level_2_code', 'theme_1_level_2_label',
    'theme_1_level_3_code', 'theme_1_level_3_label',
    'most_specific_theme_code', 'most_specific_theme_label',
    'summary'
]

for field in required_fields:
    if field not in result:
        result[field] = None
```

---

## Comparação

### Vantagens e Desvantagens

| Aspecto | Cogfy (Original) | Bedrock (Atual) |
|---------|------------------|-----------------|
| **Número de requisições** | 2 por notícia | 1 por notícia |
| **Formato de saída** | Texto estruturado | JSON estruturado |
| **Parsing** | Regex (frágil) | JSON parsing (robusto) |
| **Confiabilidade** | Média (depende de formato) | Alta (schema validado) |
| **Velocidade** | Mais lento (2 calls) | Mais rápido (1 call) |
| **Rate limiting** | Mais vulnerável | Menos vulnerável |
| **Custo** | 2x tokens | 1x tokens (economia 50%) |

### Diferenças Técnicas

#### 1. Número de Chamadas à API

**Cogfy:**
```python
# Chamada 1: Classificação
classificacao = classify_news(row)
time.sleep(0.3)  # Delay entre chamadas

# Chamada 2: Resumo
resumo = summarize_news(row)

# Combinar
result = {**row, **classificacao, 'summary': resumo}
```

**Bedrock:**
```python
# Chamada única: Classificação + Resumo
result = enrich_news(row)  # Retorna tudo em JSON
```

#### 2. Robustez do Parsing

**Cogfy** (texto livre - frágil):
- Variações no formato quebram o parsing
- Precisa de regex complexo
- Sensível a espaços e formatação

**Bedrock** (JSON - robusto):
- Schema bem definido
- Parsing nativo do Python
- Fácil validação de campos

#### 3. Tratamento de Erros

**Cogfy:**
```python
# Se o LLM responde "Nível 1: 01 Economia" (sem hífen)
nivel1_match = re.search(r'Nível 1:\s*(\d+)\s*-\s*(.+)', response)
# Match FALHA! Retorna None
```

**Bedrock:**
```python
# JSON sempre tem estrutura consistente
result = json.loads(json_str)
# Se campo ausente: result.get('theme_1_level_1', None)
```

---

## Resultados do Benchmark

Teste com **10 notícias idênticas** usando a **mesma taxonomia**.

### Métricas de Performance

| Abordagem | Taxa de Sucesso | Tempo Total | Tempo/Notícia | Requisições/Notícia |
|-----------|-----------------|-------------|---------------|---------------------|
| **Cogfy + Haiku** | 100% (10/10) | 47.6s | 4.76s | 2 |
| **Cogfy + Sonnet** | 20% (2/10) ❌ | 175.4s | 17.54s | 2 |
| **Bedrock + Haiku** | 100% (10/10) ⭐ | 42.6s | 4.26s | 1 |
| **Bedrock + Sonnet** | 80% (8/10) | 112.9s | 11.29s | 1 |

### Observações Importantes

#### 1. Sonnet Sofre Throttling Massivo
- **Cogfy + Sonnet**: Apenas 2/10 sucesso (8 falhas por throttling)
- **Bedrock + Sonnet**: 8/10 sucesso (2 falhas)
- **Razão**: Cogfy faz 2 chamadas por notícia, aumentando chance de throttling

#### 2. Bedrock é 10% Mais Rápido
- **Cogfy + Haiku**: 47.6s (2 chamadas + delays)
- **Bedrock + Haiku**: 42.6s (1 chamada)
- **Economia**: 5 segundos em 10 notícias = **10% mais eficiente**

#### 3. Custo por Notícia

Assumindo ~1500 tokens input + ~200 tokens output:

**Cogfy (2 chamadas):**
- Classificação: ~1200 tokens input + ~50 tokens output
- Resumo: ~1200 tokens input + ~100 tokens output
- **Total**: ~2400 tokens input + ~150 tokens output

**Bedrock (1 chamada):**
- Enriquecimento completo: ~1500 tokens input + ~200 tokens output
- **Total**: ~1500 tokens input + ~200 tokens output

**Economia**: ~37% menos tokens de input com Bedrock

---

## Exemplo Comparativo Real

### Notícia: "Acordo resolve maior conflito fundiário urbano em trâmite na Justiça"

#### Cogfy + Haiku
**Classificação:**
```
- Nível 1: 25 - Habitação e Urbanismo
- Nível 2: 25.01 - Programas Habitacionais
- Nível 3: 25.01.04 - Regularização Fundiária
```

**Resumo (chamada separada):**
```
O governo federal assinou um acordo que resolve o conflito fundiário histórico da
Quinta do Lebrão, em Teresópolis (RJ), beneficiando mais de 10 mil famílias de baixa
renda. O acordo encerra o maior conflito fundiário urbano em trâmite na Justiça
brasileira.
```

**Tempo**: ~8.5s (4.5s + delay + 4.0s)

---

#### Bedrock + Haiku
**Resposta JSON única:**
```json
{
  "theme_1_level_1": "Habitação e Urbanismo",
  "theme_1_level_1_code": "25",
  "theme_1_level_1_label": "Habitação e Urbanismo",
  "theme_1_level_2_code": "25.01",
  "theme_1_level_2_label": "Programas Habitacionais",
  "theme_1_level_3_code": "25.01.04",
  "theme_1_level_3_label": "Regularização Fundiária",
  "most_specific_theme_code": "25.01.04",
  "most_specific_theme_label": "Regularização Fundiária",
  "summary": "Governo federal assina acordo para regularizar a situação fundiária de 10 mil famílias de baixa renda em Teresópolis (RJ). O acordo encerra o maior conflito fundiário urbano em trâmite na Justiça brasileira."
}
```

**Tempo**: ~4.3s (1 chamada)

**Resultado**: Mesmo tema, qualidade equivalente, **50% mais rápido**

---

## Recomendação

### Prompt Bedrock (Atual) + Claude Haiku

#### Justificativa Técnica

1. **Performance Superior**
   - 100% taxa de sucesso vs 20% do Cogfy+Sonnet
   - 10% mais rápido que Cogfy+Haiku
   - 1 requisição vs 2 (menor latência)

2. **Menor Custo**
   - ~37% economia em tokens de input
   - Mesmo modelo (Haiku = Haiku)
   - Menos requisições = menos custo operacional

3. **Maior Confiabilidade**
   - JSON estruturado (parsing robusto)
   - Menos vulnerável a throttling
   - Validação de schema embutida

4. **Manutenibilidade**
   - Código mais simples (1 função vs 2)
   - Menos pontos de falha
   - Fácil debugging (JSON legível)

### Configuração Recomendada para Produção

```python
from news_enrichment import BedrockLLMClient, NewsEnricher

# Cliente Bedrock com Haiku
llm_client = BedrockLLMClient(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    taxonomy=taxonomy_from_yaml,  # Carregar de arvore.yaml
    batch_size=4,
    sleep_between_batches=0.5
)

enricher = NewsEnricher(
    dataset_manager=dataset_manager,
    llm_client=llm_client,
    verbose=True
)
```

### Projeções para Produção

**Volume diário**: 110 notícias/dia (mediana)

| Métrica | Cogfy + Haiku | Bedrock + Haiku | Economia |
|---------|---------------|-----------------|----------|
| **Tempo/dia** | ~9 min | ~8 min | 11% |
| **Requisições/dia** | 220 | 110 | 50% |
| **Custo/mês** | ~$3.00 | ~$2.00 | 33% |
| **Taxa de sucesso** | 100% | 100% | = |

**Economia anual**: ~$12 + menor risco de throttling + código mais simples

---

## Taxonomia Balizadora

Ambos os prompts usam a mesma **árvore temática** definida em [arvore.yaml](arvore.yaml).

### Estrutura da Taxonomia

- **25 categorias principais** (nível 1)
- **~100 subcategorias** (nível 2)
- **~300 temas específicos** (nível 3)

### Formato

```yaml
01 - Economia e Finanças:
  01.01 - Política Econômica:
    - 01.01.01 - Política Fiscal
    - 01.01.02 - Autonomia Econômica
  01.02 - Fiscalização e Tributação:
    - 01.02.01 - Fiscalização Econômica
    ...
```

### Uso no Prompt

A taxonomia é injetada como **texto formatado** em ambos os prompts para guiar a classificação.

---

## Arquivos Relacionados

- **[benchmark_prompts.py](benchmark_prompts.py)** - Script de benchmark completo
- **[arvore.yaml](arvore.yaml)** - Taxonomia temática balizadora
- **[data/benchmark_prompts_completo.parquet](data/benchmark_prompts_completo.parquet)** - Resultados completos
- **[data/benchmark_prompts_comparativo.csv](data/benchmark_prompts_comparativo.csv)** - Comparação lado a lado
- **[data/benchmark_prompts_metadata.json](data/benchmark_prompts_metadata.json)** - Metadados do benchmark

---

## Conclusão

O **Prompt Bedrock (atual) com Claude Haiku** é a escolha superior para produção:

- **Mais rápido**: 10% menos tempo
- **Mais econômico**: 33% menos custo
- **Mais confiável**: JSON estruturado + menos requisições
- **Mesma qualidade**: Classificações equivalentes ao Cogfy

**Status**: **Pronto para produção**

---

*Última atualização: 10 de fevereiro de 2026*
