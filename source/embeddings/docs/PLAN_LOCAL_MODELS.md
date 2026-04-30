# Plano: Avaliação de Modelos Open Source para Deployment Local

**Issue:** #3 (Fase 2) - Local Model Evaluation  
**Data:** Abril 2026  
**Objetivo:** Avaliar viabilidade técnica e econômica de modelos open source para classificação de notícias em infraestrutura própria (containers/VMs)

---

## 1. Contexto e Motivação

### 1.1 Resultados da Fase 1 (APIs Pagas)

**Melhor modelo identificado:**
- **Claude 3 Haiku** via AWS Bedrock
- Accuracy: 80.5% (L3)
- Custo: ~$97/mês (1000 notícias/dia)
- Latência: 2.7s por classificação

**Limitações:**
- ❌ Dependência de API externa (AWS)
- ❌ Custo recorrente (~$1,200/ano)
- ❌ Dados enviados para terceiros (compliance/privacidade)
- ❌ Sujeito a rate limits e indisponibilidade
- ❌ Sem controle sobre modelo (deprecação, mudanças de preço)

### 1.2 Cenários para Deployment Local

**Cenário A: Custo Operacional**
- Volume alto de classificações (>10k/dia)
- Custo de API se torna proibitivo (>$1k/mês)
- Break-even: infraestrutura própria mais barata

**Cenário B: Compliance/Privacidade**
- Restrições legais impedem envio de dados para APIs externas
- Necessidade de auditoria completa do processo
- Dados sensíveis/confidenciais

**Cenário C: Latência**
- SLA rigoroso (<500ms por classificação)
- APIs externas têm latência de rede (~100-200ms baseline)
- Deployment local elimina round-trip

**Cenário D: Independência Tecnológica**
- Controle total sobre ciclo de vida do modelo
- Possibilidade de fine-tuning customizado
- Não depender de provider único

### 1.3 Objetivos da Avaliação

**Primário:**
1. Identificar melhor modelo open source para classificação (accuracy vs recursos)
2. Calcular custo total de propriedade (TCO) de infraestrutura própria
3. Comparar TCO local vs custo API (break-even analysis)

**Secundário:**
4. Documentar requisitos de hardware (GPU/CPU/RAM)
5. Avaliar estratégias de otimização (quantização, fine-tuning)
6. Criar blueprint de deployment (Docker, Kubernetes)

---

## 2. Modelos Candidatos

### 2.1 Tier A - Modelos Grandes (>30B parâmetros)

| Modelo | Parâmetros | Contexto | Licença | GPU Mín. | Observação |
|--------|------------|----------|---------|----------|------------|
| **Llama 3.1 70B** | 70B | 128k | Llama 3 | A100 80GB | Meta, state-of-art open |
| **Mistral Large (weights)** | 123B | 32k | MRL | 2x A100 | Se disponível open weights |
| **Qwen 2.5 72B** | 72B | 128k | Apache 2.0 | A100 80GB | Alibaba, multilíngue forte |

**Prós:** Accuracy comparável a Claude Sonnet (~70-80%)  
**Contras:** Hardware caro (~$2-4/hora GPU), lento

### 2.2 Tier B - Modelos Médios (7-15B parâmetros)

| Modelo | Parâmetros | Contexto | Licença | GPU Mín. | Observação |
|--------|------------|----------|---------|----------|------------|
| **Llama 3.1 8B** | 8B | 128k | Llama 3 | RTX 4090 24GB | Baseline obrigatório |
| **Mistral 7B v0.3** | 7B | 32k | Apache 2.0 | RTX 3090 24GB | Rápido, eficiente |
| **Qwen 2.5 14B** | 14B | 128k | Apache 2.0 | A10 24GB | Ótimo custo-benefício |
| **Gemma 2 9B** | 9B | 8k | Gemma | RTX 4090 | Google, bom reasoning |
| **Phi-4 14B** | 14B | 16k | MIT | A10 24GB | Microsoft, compacto |

**Prós:** Hardware acessível (GPU consumidor/A10), rápido  
**Contras:** Accuracy provavelmente inferior (~40-60%)

### 2.3 Tier C - Modelos Pequenos (<7B parâmetros)

| Modelo | Parâmetros | Contexto | Licença | GPU Mín. | Observação |
|--------|------------|----------|---------|----------|------------|
| **Llama 3.2 3B** | 3B | 128k | Llama 3 | GTX 1080 8GB | CPU viável com quantização |
| **Phi-3.5 Mini** | 3.8B | 128k | MIT | GTX 1080 | Microsoft, SLM especializado |
| **Gemma 2 2B** | 2B | 8k | Gemma | CPU (4-8 cores) | Extremamente leve |

**Prós:** Roda em CPU/GPU consumidor, custo baixíssimo  
**Contras:** Accuracy provavelmente muito baixa (<30%)

---

## 3. Metodologia de Avaliação

### 3.1 Setup de Infraestrutura

**Opção 1: Ollama (simplicidade)**
```bash
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Baixar modelos
ollama pull llama3.1:8b
ollama pull llama3.1:70b
ollama pull mistral:7b
ollama pull qwen2.5:14b
ollama pull gemma2:9b
ollama pull phi3:14b
```

**Opção 2: vLLM (performance)**
```bash
# Melhor throughput para serving em produção
pip install vllm

# Serve modelo
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --tensor-parallel-size 1
```

**Opção 3: TGI (Hugging Face Text Generation Inference)**
```bash
# Otimizado para modelos HF
docker run --gpus all -p 8080:80 \
  -v $PWD/models:/data \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id meta-llama/Llama-3.1-8B-Instruct
```

**Decisão inicial:** Começar com **Ollama** (mais simples, ideal para experimentos) e migrar para **vLLM** se decidir por produção.

### 3.2 Adaptação do Pipeline de Avaliação

**Arquitetura:**
```
embeddings/
├── classifiers/
│   ├── local_classifier.py          # Novo: cliente Ollama/vLLM
│   └── base.py                       # Reutilizar interface
├── scripts/
│   ├── evaluate_local_models.py     # Novo: avalia modelos locais
│   └── compare_local_vs_api.py      # Novo: comparação
├── config/
│   └── local_models_config.yaml     # Novo: config dos modelos
└── results/
    └── local_models/                 # Novo: resultados separados
```

**Reutilização:**
- ✅ Dataset: `news_classification_test_annotated.csv` (mesmo de antes)
- ✅ Prompts: `classification_prompts_json.py` (reutilizar)
- ✅ Métricas: Mesma hierarquia (L1, L2, L3)
- ✅ Visualizações: Adaptar scripts existentes

### 3.3 Métricas Adicionais

Além das métricas de accuracy, precisamos medir:

**Performance:**
- **Throughput:** Classificações/segundo
- **Latência:** P50, P95, P99
- **Cold start:** Tempo até primeiro token
- **Memory usage:** RAM/VRAM durante inferência

**Recursos:**
- **GPU Memory:** Peak VRAM usage
- **GPU Utilization:** Percentual de uso
- **CPU cores:** Se rodar em CPU
- **Disk space:** Tamanho do modelo (pesos + runtime)

**Custo (Infraestrutura):**
- **EC2/GPU instance:** $/hora (ex: g5.xlarge, g5.2xlarge, p3.2xlarge)
- **Storage:** $/mês para armazenar modelos
- **Break-even:** Quantas classificações/dia para compensar vs API

---

## 4. Estratégias de Otimização

### 4.1 Quantização

**Reduz tamanho do modelo e aumenta velocidade:**

| Método | Size Reduction | Speed Up | Accuracy Loss | Ferramenta |
|--------|----------------|----------|---------------|------------|
| **FP16** | 2x | 1.5-2x | ~0% | Pytorch native |
| **INT8** | 4x | 2-3x | 1-3% | bitsandbytes |
| **INT4 (GPTQ)** | 8x | 3-4x | 2-5% | AutoGPTQ |
| **GGUF (Q4_K_M)** | 8x | 3-4x | 2-5% | llama.cpp |

**Recomendação inicial:** Testar **INT8** (bom trade-off) e **GPTQ 4-bit** (máxima compressão).

**Exemplo (Ollama já faz isso automaticamente):**
```bash
# Ollama baixa versão quantizada automaticamente
ollama pull llama3.1:8b-q4_K_M  # 4-bit quantizado
```

### 4.2 Fine-tuning (Opcional, Fase 3)

**Se modelos base não atingirem accuracy aceitável:**

**Método:** LoRA (Low-Rank Adaptation)
- Treina apenas ~0.1% dos parâmetros
- Custo: $50-200 (depende do tamanho)
- Tempo: 2-8 horas em A100

**Dataset:** Usar 200 notícias anotadas + data augmentation

**Ganho esperado:** +10-20% accuracy (baseado em literatura)

**Ferramentas:**
- Axolotl (framework completo)
- PEFT (Hugging Face)
- Unsloth (otimizado para velocidade)

---

## 5. Análise de Custo Total de Propriedade (TCO)

### 5.1 Custos de Infraestrutura (AWS)

**GPU Instances (on-demand pricing us-east-1):**

| Instance | GPU | VRAM | $/hora | $/mês (24/7) | Modelos Suportados |
|----------|-----|------|--------|--------------|-------------------|
| g5.xlarge | A10G | 24GB | $1.01 | $730 | Llama 8B, Mistral 7B, Qwen 14B |
| g5.2xlarge | A10G | 24GB | $1.21 | $875 | Idem acima |
| g5.12xlarge | 4x A10G | 96GB | $5.67 | $4,100 | Llama 70B |
| p3.2xlarge | V100 | 16GB | $3.06 | $2,214 | Llama 8B (mais lento) |
| p4d.24xlarge | 8x A100 | 320GB | $32.77 | $23,700 | Llama 70B (overkill) |

**Reserved Instances (1 ano, desconto ~30-40%):**
- g5.xlarge: ~$0.60/hora = $434/mês
- g5.12xlarge: ~$3.40/hora = $2,460/mês

**Spot Instances (desconto ~70%, mas pode ser interrompido):**
- g5.xlarge: ~$0.30/hora = $217/mês
- g5.12xlarge: ~$1.70/hora = $1,230/mês

### 5.2 Break-even Analysis

**Cenário Base:**
- Volume: 1000 classificações/dia (30k/mês)
- API (Claude Haiku): $97/mês
- Infraestrutura local: ?

**Modelo Llama 3.1 8B em g5.xlarge:**
- Custo infraestrutura: $730/mês (on-demand) ou $434/mês (reserved)
- Break-even: $434/mês → ~4,500 classificações/dia

**Modelo Llama 3.1 70B em g5.12xlarge:**
- Custo infraestrutura: $4,100/mês (on-demand) ou $2,460/mês (reserved)
- Break-even: $2,460/mês → ~25,000 classificações/dia

**Conclusão inicial:** Para 1000 news/dia, API é mais barata. Infraestrutura própria só compensa com volume >5k/dia (8B) ou >25k/dia (70B).

**Exceção:** Spot instances podem reduzir custo em ~70%, tornando viável para volumes menores (~2k/dia).

### 5.3 Custos Adicionais

**Armazenamento:**
- Modelos: 5-150GB cada
- EBS gp3: $0.08/GB/mês → $10-20/mês (negligível)

**Maintenance:**
- DevOps time: ~4-8h/mês
- Custo humano: $200-400/mês (estimativa)

**Monitoring:**
- CloudWatch/Prometheus/Grafana: $20-50/mês

**Total overhead:** +$250-500/mês (além da GPU)

---

## 6. Roadmap de Execução

### Fase 1: Setup e Benchmark Básico (1-2 dias)

**Tarefas:**
1. ✅ Criar `local_classifier.py` (cliente Ollama)
2. ✅ Configurar Ollama localmente ou em VM
3. ✅ Baixar 3 modelos iniciais (Llama 8B, Mistral 7B, Qwen 14B)
4. ✅ Adaptar script de avaliação
5. ✅ Rodar teste em 20 notícias (validação técnica)

**Output:** Confirmação de que pipeline funciona

### Fase 2: Avaliação Completa (2-3 dias)

**Tarefas:**
6. ⏳ Avaliar Tier B completo (6 modelos, 200 notícias cada)
7. ⏳ Medir métricas de performance (latência, throughput, VRAM)
8. ⏳ Gerar relatório comparativo
9. ⏳ Visualizações (accuracy vs recursos)

**Output:** Ranking de modelos open source

### Fase 3: Otimização (3-5 dias, opcional)

**Tarefas:**
10. ⏳ Testar quantização (INT8, GPTQ 4-bit)
11. ⏳ Fine-tuning do melhor modelo (LoRA)
12. ⏳ Re-avaliar modelos otimizados
13. ⏳ Atualizar análise de TCO

**Output:** Melhor configuração para produção

### Fase 4: Comparação Final e Recomendação (1 dia)

**Tarefas:**
14. ⏳ Comparar melhor modelo local vs Claude Haiku (API)
15. ⏳ Análise de break-even (volume de classificações)
16. ⏳ Documentar recomendação final (API vs local vs híbrido)
17. ⏳ Blueprint de deployment (Docker, K8s)

**Output:** Relatório técnico completo + recomendação executiva

---

## 7. Critérios de Sucesso

**Objetivo Primário:**
- ✅ Identificar pelo menos 1 modelo open source com accuracy >60% (L3)

**Objetivo Secundário:**
- ✅ TCO local <50% do custo API para volume relevante (5k+ news/dia)
- ✅ Latência <1s (batch) ou <3s (single)

**Objetivo Aspiracional:**
- 🎯 Modelo open source atinge accuracy >70% (competitivo com Sonnet)
- 🎯 TCO local break-even em <3k news/dia

---

## 8. Riscos e Mitigações

**Risco 1: Modelos open source têm accuracy muito baixa (<40%)**
- **Probabilidade:** Média (baseado em resultados Bedrock: Llama 0%)
- **Impacto:** Alto (invalida deployment local)
- **Mitigação:** Fine-tuning com LoRA, Few-shot dinâmico

**Risco 2: Hardware necessário é muito caro (break-even >50k/dia)**
- **Probabilidade:** Alta (GPUs são caras)
- **Impacto:** Médio (recomenda manter API)
- **Mitigação:** Spot instances, quantização agressiva (INT4), modelos menores

**Risco 3: Latência local é pior que API**
- **Probabilidade:** Baixa (local elimina network latency)
- **Impacto:** Médio
- **Mitigação:** Otimizações (vLLM, batch processing, quantização)

**Risco 4: Complexidade operacional é alta**
- **Probabilidade:** Alta (deploy, monitoring, updates)
- **Impacto:** Alto (custo humano)
- **Mitigação:** Usar soluções managed (SageMaker, Replicate) ou considerar híbrido

---

## 9. Entregáveis

**Documentação:**
1. ✅ Este plano (PLAN_LOCAL_MODELS.md)
2. ⏳ Relatório técnico comparativo (TECHNICAL_REPORT_LOCAL.md)
3. ⏳ Blueprint de deployment (DEPLOYMENT_GUIDE.md)

**Código:**
4. ⏳ `local_classifier.py` - Cliente universal (Ollama/vLLM/TGI)
5. ⏳ `evaluate_local_models.py` - Script de avaliação
6. ⏳ `compare_local_vs_api.py` - Comparação API vs local
7. ⏳ Dockerfile - Container pronto para deploy

**Resultados:**
8. ⏳ `results/local_models/comparison_summary.csv` - Ranking
9. ⏳ `results/local_models/performance_metrics.csv` - Latência, VRAM, etc
10. ⏳ `results/local_models/tco_analysis.csv` - Break-even analysis
11. ⏳ Visualizações (accuracy vs VRAM, accuracy vs custo, etc)

---

## 10. Próximos Passos Imediatos

**Para começar hoje:**

1. **Decisão de ambiente:**
   - [ ] Rodar localmente (precisa GPU? qual?)
   - [ ] Provisionar VM/GPU em cloud (AWS g5.xlarge?)
   - [ ] Usar máquina existente?

2. **Setup inicial:**
   - [ ] Instalar Ollama
   - [ ] Baixar Llama 3.1 8B (modelo baseline)
   - [ ] Testar classificação de 1 notícia

3. **Validação técnica:**
   - [ ] Adaptar `local_classifier.py`
   - [ ] Rodar em 20 notícias
   - [ ] Medir VRAM/latência

**Tempo estimado Fase 1:** 4-6 horas

---

## Apêndice: Referências

**Papers:**
- Llama 3: [Meta AI, 2024]
- vLLM: [UC Berkeley, 2023] - Fast inference engine
- GPTQ: [Frantar et al., 2023] - Quantization method

**Ferramentas:**
- Ollama: https://ollama.com/
- vLLM: https://github.com/vllm-project/vllm
- TGI: https://github.com/huggingface/text-generation-inference
- Axolotl: https://github.com/OpenAccess-AI-Collective/axolotl

**Pricing:**
- AWS EC2 GPU: https://aws.amazon.com/ec2/instance-types/
- Hugging Face Inference Endpoints: https://huggingface.co/pricing
