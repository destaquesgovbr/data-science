# Avaliação de Modelos Open Source Locais

**Fase 2 do Issue #3** - Avaliação de modelos open source para deployment local/containerizado

## 🎯 Objetivo

Avaliar viabilidade técnica e econômica de modelos open source rodando em infraestrutura própria (vs APIs pagas como Claude Haiku).

## 📊 Contexto

**Fase 1 (APIs):** Claude Haiku venceu com 80.5% accuracy a $97/mês

**Fase 2 (Local):** Avaliar se modelos open source podem:
- Atingir accuracy competitiva (>60%)
- Ter custo total de propriedade (TCO) menor
- Permitir independência de APIs externas

## 🤖 Modelos Avaliados (8 total)

### Tier B - Médios (7-15B parâmetros)
1. **Llama 3.1 8B** - Meta, baseline obrigatório
2. **Mistral 7B v0.3** - Rápido e eficiente
3. **Qwen 2.5 14B** - Alibaba, excelente multilíngue
4. **Gemma 2 9B** - Google, bom reasoning
5. **Phi-4 14B** - Microsoft, compacto

### Tier C - Pequenos (2-4B parâmetros)
6. **Llama 3.2 3B** - Meta small
7. **Phi-3.5 Mini** (3.8B) - Microsoft SLM
8. **Gemma 2 2B** - Google, extremamente leve

**Por que não modelos grandes (70B+)?**
> Experiência com APIs mostrou que Haiku (médio) superou Sonnet (grande) por 2.4x. Modelos maiores nem sempre são melhores, e o hardware é muito mais caro.

## 🚀 Quick Start

### 1. Instalar Ollama

```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Iniciar servidor
ollama serve
```

### 2. Baixar Modelos

```bash
cd source/embeddings

# Baixar todos os 8 modelos (Tier B + C)
./scripts/setup_local_models.sh

# Ou baixar individualmente
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull mistral:7b-instruct-v0.3-q4_K_M
# ... etc
```

**Espaço em disco necessário:** ~40-60GB total

### 3. Teste Rápido (Validação Técnica)

```bash
# Testa 3 modelos em 10 notícias (~2-5 min)
python scripts/test_local_quick.py
```

**O que o teste valida:**
- ✅ Ollama está funcionando
- ✅ Modelos foram baixados corretamente
- ✅ Parsing JSON está ok
- ✅ Estimativa de tempo para avaliação completa

### 4. Avaliação Completa

```bash
# Avalia todos os 8 modelos em 200 notícias (~2-4h)
python scripts/evaluate_local_models.py
```

**Outputs gerados:**
- `results/local_models/comparison_summary.csv` - Ranking
- `results/local_models/detailed_results.json` - Detalhes completos

## 📁 Estrutura de Arquivos

```
embeddings/
├── classifiers/
│   └── local_classifier.py          # Cliente Ollama (novo)
├── config/
│   └── local_models_config.yaml     # Config dos 8 modelos
├── scripts/
│   ├── setup_local_models.sh        # Baixar modelos
│   ├── test_local_quick.py          # Teste rápido
│   └── evaluate_local_models.py     # Avaliação completa
├── docs/
│   ├── PLAN_LOCAL_MODELS.md         # Plano detalhado
│   └── README_LOCAL_MODELS.md       # Este arquivo
└── results/
    └── local_models/                # Resultados (gerados)
```

## 📊 Métricas Avaliadas

**Accuracy (comparável com APIs):**
- Level 1 (Grande Área): XX%
- Level 2 (Subcategoria): XX%
- Level 3 (Tópico): XX%

**Performance:**
- Latência média (segundos)
- Throughput (classificações/segundo)
- Taxa de erro (parsing JSON)

**Recursos:**
- VRAM peak (GB)
- Tokens médios (input/output)

**Custo (estimado):**
- Infraestrutura necessária (tipo de GPU)
- Custo mensal (AWS EC2 ou similar)
- Break-even vs API (em classificações/dia)

## 💰 Análise de Custo (Preliminar)

### Infraestrutura AWS

| Instance | GPU | VRAM | $/mês (on-demand) | Modelos Suportados |
|----------|-----|------|-------------------|-------------------|
| g5.xlarge | A10G | 24GB | $730 | Tier B + C (todos) |
| g5.2xlarge | A10G | 24GB | $875 | Tier B + C (todos) |

**Reserved Instance (1 ano, -40%):**
- g5.xlarge: ~$434/mês

**Spot Instance (-70%, pode interromper):**
- g5.xlarge: ~$217/mês

### Break-even vs API (Claude Haiku)

**Cenário atual:** 1000 classificações/dia
- API (Haiku): $97/mês
- Local (g5.xlarge reserved): $434/mês
- **Conclusão:** API é mais barata até ~4.5k/dia

**Para volume alto:** 10k classificações/dia
- API (Haiku): $970/mês
- Local (g5.xlarge reserved): $434/mês
- **Conclusão:** Local compensa a partir desse volume

## 🔬 Metodologia

**Reutilização da Fase 1:**
- ✅ Mesmo dataset (200 notícias anotadas)
- ✅ Mesmos prompts JSON
- ✅ Mesmas métricas (L1, L2, L3)
- ✅ Mesma taxonomia (500 categorias)

**Diferenças:**
- 🆕 Serving: Ollama (local) vs Bedrock (API)
- 🆕 Métricas adicionais: VRAM, throughput
- 🆕 Análise de TCO (Total Cost of Ownership)

## 📈 Resultados Esperados

**Cenário otimista:**
- Melhor modelo local: 60-70% L3
- TCO competitivo para volumes >5k/dia
- Latência <1s (melhor que API)

**Cenário realista:**
- Melhor modelo local: 40-50% L3
- TCO só compensa para volumes >10k/dia
- Latência similar à API (~2s)

**Cenário pessimista:**
- Todos modelos <40% L3
- TCO sempre mais caro que API
- Recomendação: manter API

## ⚠️ Limitações Conhecidas

1. **Llama via Bedrock teve 0% accuracy** - Suspeita de problema de API compatibility
   - Solução: Testar via Ollama (controle total)

2. **Quantização pode afetar accuracy** - Todos modelos em Q4_K_M (4-bit)
   - Trade-off: -75% VRAM, ~2-5% accuracy loss

3. **Ground truth bias** - Dataset anotado pelo Haiku
   - Modelos locais podem ter "interpretação diferente" válida
   - Necessário validação humana futura

## 🎯 Critérios de Sucesso

**Mínimo viável:**
- ✅ Pelo menos 1 modelo com >60% L3
- ✅ Pipeline funcional e documentado

**Sucesso pleno:**
- ✅ Modelo com >70% L3 (competitivo com Sonnet)
- ✅ TCO <50% da API para volume relevante
- ✅ Latência <1s

**Aspiracional:**
- 🎯 Modelo com >80% L3 (comparável ao Haiku)
- 🎯 TCO break-even em <3k/dia

## 🐛 Troubleshooting

**Erro: "Ollama não está rodando"**
```bash
# Iniciar em terminal separado
ollama serve

# Ou verificar se já está rodando
curl http://localhost:11434/api/tags
```

**Erro: "Modelo não encontrado"**
```bash
# Listar modelos instalados
ollama list

# Baixar modelo específico
ollama pull llama3.1:8b-instruct-q4_K_M
```

**Erro: "Out of memory / CUDA error"**
- Reduzir concorrência: `max_concurrent_requests: 1`
- Usar modelos menores (Tier C)
- Aumentar VRAM (upgrade GPU)

**Latência muito alta (>10s)**
- Verificar se está usando GPU (não CPU)
- Checar temperatura/throttling
- Testar modelo menor

## 📚 Referências

**Ollama:**
- Site: https://ollama.com/
- Modelos disponíveis: https://ollama.com/library
- API: https://github.com/ollama/ollama/blob/main/docs/api.md

**Modelos:**
- Llama 3.1: https://ai.meta.com/blog/meta-llama-3-1/
- Mistral: https://mistral.ai/
- Qwen 2.5: https://qwenlm.github.io/
- Gemma 2: https://ai.google.dev/gemma
- Phi-4: https://www.microsoft.com/en-us/research/blog/phi-4/

**AWS Pricing:**
- EC2 GPU Instances: https://aws.amazon.com/ec2/instance-types/

## 🤝 Próximos Passos

1. ✅ Setup e teste rápido
2. ⏳ Avaliação completa (8 modelos, 200 news)
3. ⏳ Análise comparativa (local vs API)
4. ⏳ Documentação técnica final
5. ⏳ Recomendação executiva (API vs local vs híbrido)

## 💡 Insights

**Por que focar em modelos médios/pequenos?**
> Claude Haiku (modelo médio/econômico) teve 80.5% vs Claude Sonnet (premium) com 33.5%. Isso sugere que modelos menores podem ter melhor "fit" para tarefas específicas, e são muito mais baratos para servir.

**Quantização é segura?**
> Q4_K_M reduz VRAM em 8x com apenas ~2-5% de perda de accuracy segundo literatura. Para classificação (vs generation), o impacto é ainda menor.

**Quando local compensa?**
> Break-even depende do volume. Regra geral: <5k/dia use API, >10k/dia considere local, entre 5-10k depende de outros fatores (compliance, latência, etc).
