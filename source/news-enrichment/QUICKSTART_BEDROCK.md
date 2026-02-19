# 🚀 Quick Start - AWS Bedrock

## Por que usar Bedrock?

✅ **Você já tem acesso!** Sua conta AWS já está configurada
✅ **Modelos de ponta:** Claude Opus 4.5, Claude Sonnet 4.5, Claude Haiku 4.5
✅ **Custo corporativo:** Billing da empresa, sem precisar de API keys pessoais
✅ **Privacidade:** Dados ficam na AWS, não vão para Anthropic/OpenAI
✅ **Sem limites de rate:** Muito melhor que APIs públicas

---

## ⚡ Uso Rápido (3 passos)

### 1. Instalar boto3 (se ainda não tiver)

```bash
pip install boto3
```

### 2. Testar conexão

```bash
python exemplo_bedrock.py
```

### 3. Enriquecer suas notícias!

```python
import polars as pl
from llm_enricher import EnrichmentConfig, NewsEnricher
from llm_enricher_bedrock import create_enricher_with_bedrock

# Carregar dataset
df = pl.read_parquet("seu_dataset.parquet")

# Configurar (recomendado: Claude Haiku 4.5)
config = EnrichmentConfig(
    provider="bedrock",
    model="claude-haiku-4.5",  # Rápido e econômico!
    base_url="us-east-1",
    max_workers=10,
    batch_size=100
)

# Enriquecer
enricher = create_enricher_with_bedrock(config)
pipeline = NewsEnricher(enricher)

df_enriched = pipeline.enrich_dataframe(
    df,
    text_column="conteudo",
    enrichment_type="full"
)

# Salvar
df_enriched.write_parquet("dataset_enriquecido.parquet")
```

---

## 🎯 Modelos Recomendados

### Para Produção (Recomendado)

```python
# Claude Haiku 4.5 - Melhor custo-benefício
config = EnrichmentConfig(
    provider="bedrock",
    model="claude-haiku-4.5",
    base_url="us-east-1",
    max_workers=10,
    batch_size=100
)
```

**Por quê?**
- ⚡ Muito rápido
- 💰 Mais barato
- ✅ Qualidade excelente para enriquecimento
- 📊 Processa ~500-1000 notícias/minuto

**Estimativa de custo:**
- ~$0.25 por 1000 notícias (bem barato!)

---

### Para Máxima Qualidade

```python
# Claude Sonnet 4.5 - Análise mais profunda
config = EnrichmentConfig(
    provider="bedrock",
    model="claude-sonnet-4.5",
    base_url="us-east-1",
    max_workers=5,
    batch_size=50
)
```

**Quando usar?**
- Análise mais complexa
- Extração de entidades mais precisa
- Categorização de domínio específico

**Estimativa de custo:**
- ~$3.00 por 1000 notícias

---

### Para Casos Especiais

```python
# Claude Opus 4.5 - Máxima qualidade (mais caro)
config = EnrichmentConfig(
    provider="bedrock",
    model="claude-opus-4.5",
    base_url="us-east-1",
    max_workers=3,
    batch_size=20
)
```

**Quando usar?**
- Análise crítica de negócio
- Conteúdo sensível
- Máxima precisão necessária

---

## 📋 Via Linha de Comando

Para grandes volumes, use o script de produção:

```bash
# Enriquecer dataset completo
python -c "
from llm_enricher import EnrichmentConfig
from llm_enricher_bedrock import create_enricher_with_bedrock, BedrockEnricher
from enriquecer_producao import ProductionEnricher
import polars as pl

# Configurar
config = EnrichmentConfig(
    provider='bedrock',
    model='claude-haiku-4.5',
    base_url='us-east-1',
    max_workers=10,
    batch_size=100
)

# Processar
enricher = ProductionEnricher(config)
enricher.pipeline.enricher = create_enricher_with_bedrock(config)

df = enricher.enrich_dataset(
    'noticias.parquet',
    text_column='conteudo',
    enrichment_type='full'
)
print(f'Processadas {len(df)} notícias!')
"
```

Ou crie um script simples:

```python
# enriquecer_bedrock.py
import sys
from llm_enricher import EnrichmentConfig, NewsEnricher
from llm_enricher_bedrock import create_enricher_with_bedrock
import polars as pl

input_file = sys.argv[1]
output_file = sys.argv[2]

config = EnrichmentConfig(
    provider="bedrock",
    model="claude-haiku-4.5",
    base_url="us-east-1",
    max_workers=10,
    batch_size=100
)

enricher = create_enricher_with_bedrock(config)
pipeline = NewsEnricher(enricher)

df = pl.read_parquet(input_file)
df_enriched = pipeline.enrich_dataframe(df, "conteudo", "full")
df_enriched.write_parquet(output_file)

print(f"✅ {len(df_enriched)} notícias enriquecidas!")
```

Uso:
```bash
python enriquecer_bedrock.py input.parquet output.parquet
```

---

## 💡 Dicas de Otimização

### 1. Paralelização

Bedrock suporta alta paralelização:

```python
config = EnrichmentConfig(
    provider="bedrock",
    model="claude-haiku-4.5",
    base_url="us-east-1",
    max_workers=20,  # ← Pode aumentar muito!
    batch_size=200
)
```

### 2. Batch Size

Para Haiku (rápido), pode usar batches grandes:

```python
batch_size=200  # Haiku aguenta bem
```

Para Sonnet/Opus (mais lentos):

```python
batch_size=50  # Melhor para modelos maiores
```

### 3. Region

Use a region mais próxima:

```python
base_url="us-east-1"  # Ou "us-west-2", etc
```

---

## 📊 Comparação de Modelos

Teste com seu dataset real:

```bash
python exemplo_bedrock.py
# Escolha opção 2 (Comparar modelos)
```

Isso vai testar:
- Claude Haiku 4.5
- Claude Sonnet 4.5
- Mistral Large 3
- Amazon Titan

E mostrar:
- ⏱️ Tempo de processamento
- 📝 Qualidade dos resultados
- 💰 Estimativa de custo

---

## 🔧 Troubleshooting

### Erro: "AccessDeniedException"

```bash
# Verifique permissões do Bedrock
aws bedrock list-foundation-models --region us-east-1
```

Se der erro, peça ao admin AWS para adicionar permissões:
- `bedrock:InvokeModel`
- `bedrock:ListFoundationModels`

### Erro: "ModelNotFound"

O modelo pode não estar na region. Tente:

```python
base_url="us-west-2"  # Ou outra region
```

### Erro: "ThrottlingException"

Reduza paralelização:

```python
max_workers=5  # Reduzir
batch_size=50
```

---

## 📈 Performance Esperada

Com Claude Haiku 4.5:

| Notícias | Tempo | Velocidade |
|----------|-------|------------|
| 100 | ~30s | ~200/min |
| 1.000 | ~5min | ~200/min |
| 10.000 | ~50min | ~200/min |
| 100.000 | ~8h | ~200/min |

**Dica:** Para >10k notícias, rode em uma instância EC2 maior.

---

## 🎉 Próximos Passos

1. ✅ Teste com dataset pequeno (100 notícias)
2. ✅ Valide qualidade dos resultados
3. ✅ Compare Haiku vs Sonnet para seu caso
4. ✅ Rode em produção!

---

**Dúvidas?** Execute:
```bash
python exemplo_bedrock.py
```

E explore os exemplos interativos!
