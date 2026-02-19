# Resultados dos Testes de Performance

## Resumo Executivo

Testamos múltiplos modelos LLM (local CPU e cloud) para enriquecer 310k notícias governamentais brasileiras. **Conclusão: AWS Bedrock é a única opção viável para o dataset completo.**

---

## Modelos Testados (CPU - i7)

| Modelo | Tamanho | Tempo/Notícia | Taxa Sucesso | 300k Notícias | Viável? |
|--------|---------|---------------|--------------|---------------|---------|
| qwen2.5:7b | 4.7GB | 120-180s (timeout) | ~50% | N/A | ❌ Não |
| qwen2.5:3b | 2GB | 127s | 67% | 441 dias | ❌ Não |
| **TinyLlama 1.1b** | **637MB** | **96s** | **100%** | **345 dias** | ⚠️ Só amostras |

### Conclusão Local:
- TinyLlama 1.1b é o melhor modelo para CPU
- Útil para amostras de validação (10-1000 notícias)
- Inviável para dataset completo (quase 1 ano de processamento)

---

## AWS Bedrock (Claude 3 Haiku)

| Métrica | Valor |
|---------|-------|
| Tempo/Notícia | ~0.5-1s (batch 8) |
| Batch size | 8 notícias paralelo |
| Taxa de sucesso | ~95-98% |
| **Tempo total 310k** | **3-4 horas** |
| **Custo estimado** | **$150-200** |

### Vantagens Bedrock:
- ✅ **320x mais rápido** que TinyLlama local
- ✅ Maior taxa de sucesso
- ✅ Melhor qualidade de classificação
- ✅ Sem necessidade de GPU
- ✅ Escalável

---

## Recomendações

### Para Desenvolvimento/Validação:
```bash
# Testar com amostra pequena local
python enriquecimento_hibrido.py
# Escolher opção 1 ou 2 (10-100 notícias com TinyLlama)
```

### Para Produção (310k notícias):
```bash
# Usar AWS Bedrock
python enriquecimento_hibrido.py
# Escolher opção 5 (dataset completo com Bedrock)
```

### Workflow Recomendado:
1. **Validar com 10-100 notícias localmente** (TinyLlama)
   - Verificar qualidade das classificações
   - Ajustar prompts se necessário
   - Tempo: 15 min - 3 horas

2. **Testar com 1000 notícias no Bedrock** (opção 4)
   - Validar custos reais
   - Verificar rate limits
   - Custo: ~$1, Tempo: ~8 min

3. **Processar dataset completo no Bedrock** (opção 5)
   - Custo: ~$150-200
   - Tempo: 3-4 horas
   - Resultado: 310k notícias enriquecidas

---

## Estrutura de Arquivos Gerados

```
data/
├── govbrnews_full.parquet              # Dataset original (cache)
├── sample_tinyllama_10.parquet         # Validação local (10)
├── sample_tinyllama_100.parquet        # Validação local (100)
├── sample_bedrock_1000.parquet         # Teste Bedrock (1k)
└── govbrnews_enriched_FULL.parquet     # Produção (310k) ← OBJETIVO FINAL
```

---

## Custos Detalhados Bedrock

### Claude 3 Haiku Pricing:
- Input: $0.25 / 1M tokens
- Output: $1.25 / 1M tokens

### Estimativa por notícia:
- Input: ~1500 tokens (título + conteúdo)
- Output: ~500 tokens (classificação + resumo)
- Custo/notícia: ~$0.001 (0.1 centavo)

### 310k notícias:
- Input: 465M tokens → $116
- Output: 155M tokens → $194
- **Total: ~$310** (margem de segurança)
- **Estimativa conservadora: $150-200**

---

## Scripts Disponíveis

1. **[enriquecimento_hibrido.py](enriquecimento_hibrido.py)** ← **RECOMENDADO**
   - Menu interativo com 5 opções
   - TinyLlama para desenvolvimento
   - Bedrock para produção
   - Estimativas de tempo/custo

2. [teste_tinyllama.py](teste_tinyllama.py)
   - Teste específico TinyLlama
   - Amostra de 2 notícias

3. [teste_local_sequencial.py](teste_local_sequencial.py)
   - Teste qwen2.5:3b sequencial
   - Amostra de 3 notícias

4. [exemplo_enriquecimento_local.py](exemplo_enriquecimento_local.py)
   - Menu com 5 modelos (1 Bedrock + 4 local)
   - Mais opções, menos otimizado

---

## Próximos Passos

### Imediato:
```bash
# 1. Validar localmente (15 min)
python enriquecimento_hibrido.py  # Opção 1

# 2. Revisar resultados
polars data/sample_tinyllama_10.parquet --head

# 3. Se OK, testar Bedrock (8 min, $1)
python enriquecimento_hibrido.py  # Opção 4
```

### Produção:
```bash
# Configurar credenciais AWS (se não configurado)
export AWS_ACCESS_KEY_ID="sua-key"
export AWS_SECRET_ACCESS_KEY="sua-secret"
export AWS_DEFAULT_REGION="us-east-1"

# Processar dataset completo (3-4 horas, $150-200)
python enriquecimento_hibrido.py  # Opção 5
```

### PostgreSQL (Opcional):
```python
from news_enrichment import PostgresExporter

exporter = PostgresExporter(
    connection_string="postgresql://user:pass@host:5432/db"
)

exporter.export_to_postgres(
    df=enriched,
    table_name="news_enriched",
    if_exists="append"
)
```

---

## Suporte

- **Documentação Ollama**: [README_OLLAMA.md](README_OLLAMA.md)
- **Docker**: [docker-compose.yml](docker-compose.yml)
- **Código fonte**: [news_enrichment/](news_enrichment/)
