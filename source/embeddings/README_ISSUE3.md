# Issue #3: Avaliação Comparativa de LLMs para Classificação de Notícias

## 🎯 Objetivo

Avaliar se modelos LLM (APIs comerciais e open source locais) podem classificar notícias governamentais brasileiras em taxonomia hierárquica de 500 categorias (3 níveis) com accuracy viável para produção.

## ✅ Status Final

**CONCLUÍDO** - Decisão tomada com base em exploração exaustiva.

**Resultado:** Usar **Claude Haiku via AWS Bedrock** em produção.

---

## 📊 Resumo das 3 Fases

### Fase 1: APIs Comerciais - Taxonomia Simples ✅
**Data:** 2026-04  
**Testado:** 7 modelos AWS Bedrock, 200 notícias, 10 categorias simples  
**Melhor:** Claude 3 Sonnet (51% accuracy, $0.46/200 notícias)  
**Limitação:** Taxonomia muito simples, não reflete produção

### Fase 2: APIs - Taxonomia Hierárquica Completa ✅
**Data:** 2026-04  
**Testado:** 11 modelos AWS Bedrock, 200 notícias, **500 categorias hierárquicas**  
**Melhor:** **Claude Haiku - 80.5% accuracy L3**, $97/mês (@1k classificações/dia)  
**Insight:** Haiku (médio) > Sonnet (premium) em 2.4x  
**Baseline estabelecido:** 80.5% L3 é o target a bater

### Fase 3: Modelos Open Source Locais ✅
**Data:** 2026-05-04 a 2026-05-06  
**Testado:** 8 modelos locais, 2 quantizações, 2 abordagens, GPU L4  
**Melhor:** Llama 3.1 8B Q4 - **16% accuracy L3**, 2.6s latência  
**Gap:** 64.5 pontos vs Claude Haiku (5x pior)  
**Conclusão:** Modelos locais < 70B não são viáveis para esta tarefa

---

## 🏆 Resultado Final - Fase 3 (Modelos Locais)

### Ranking Completo (8 modelos testados)

| Pos | Modelo | Accuracy L3 | Latência | Observação |
|-----|--------|-------------|----------|------------|
| 🥇 | **Llama 3.1 8B Q4** | **16%** | 2.6s | Campeão local |
| 🥈 | Llama 3.1 8B Q6 | 12% | 2.9s | Q6 piorou |
| 🥉 | Nemotron 3 33B | 10% | 38.7s | Offloading lento |
| 4º | Qwen 2.5 32B | 8% | 8.3s | Perde contexto L3 |
| 5º | Gemma 2 2B | 6% | 1.6s | Pequeno eficiente |
| 5º | DeepSeek-R1 14B | 6% | 47.7s | Chain-of-thought overhead |
| 5º | Phi-4 14B | 6% | 3.8s | Reasoning sem vantagem |
| 8º | Qwen 2.5 14B | 0% | 6.0s | Pior absoluto |

**Baseline:** Claude Haiku - **80.5%** L3, ~2-3s

### Gap Intransponível

```
Claude Haiku (API):  ████████████████████████████████████████ 80.5%
Llama 8B (Local):    ████████ 16%
                     ↑______________________________________↑
                              GAP: 64.5 pontos (5x pior)
```

---

## 💰 Análise Econômica

### Comparação de Custos

| Solução | Accuracy L3 | Custo @1k/dia | Custo @10k/dia | Viável? |
|---------|-------------|---------------|----------------|---------|
| **Claude Haiku (API)** | **80.5%** | **$97/mês** | $970/mês | ✅ |
| Llama 8B (Local) | 16% | $434/mês* | $434/mês* | ❌ |

*EC2 g5.xlarge reserved + manutenção

**Conclusão:** API é mais barata E 5x melhor em volumes realistas.

---

## 🔬 Metodologia - Exploração Exaustiva

### O que foi testado na Fase 3:

✅ **8 modelos:** 2B → 8B → 14B → 32B → 33B  
✅ **6 famílias:** Llama, Qwen, Gemma, Phi, DeepSeek, Nemotron  
✅ **2 quantizações:** Q4_K_M, Q6_K  
✅ **2 abordagens:** Hierárquica (3 etapas), Direta (500 categorias)  
✅ **Especialistas:** Reasoning (Phi-4), Chain-of-thought (DeepSeek-R1)  
✅ **Infraestrutura:** GPU L4 23GB + offloading até 33GB  

**Total:** 16+ configurações testadas

---

## 📚 Principais Descobertas

### 1. Tamanho ≠ Qualidade
- Llama 8B (16%) > Nemotron 33B (10%) > Qwen 32B (8%)
- Arquitetura importa mais que parâmetros brutos

### 2. Hierárquica >> Direta (sempre)
- Todos modelos falharam na direta (0-4% L3)
- Prompt de 500 categorias sobrecarrega até modelos grandes

### 3. Reasoning specialists não ajudam
- DeepSeek-R1: 6% L3, 18x mais lento
- Phi-4: 6% L3, sem vantagem vs general purpose

### 4. Quantização Q4 é suficiente
- Q6 não melhorou (até piorou: 12% vs 16%)
- Q4 oferece melhor custo-benefício

### 5. Offloading mata performance
- Nemotron 33GB em GPU 23GB → 15x mais lento
- Modelos devem caber INTEIROS na GPU

### 6. APIs têm vantagem intransponível
- Claude treinado para tarefas complexas
- Open source está anos atrás (gap de 64+ pontos)

---

## ✅ Decisão Final

### Usar Claude Haiku via AWS Bedrock em produção

**Justificativa (5 pilares):**

1. ✅ **Accuracy superior:** 80.5% vs 16% (5x melhor)
2. ✅ **Custo menor:** $97/mês vs $434/mês + overhead
3. ✅ **Latência competitiva:** ~2-3s (similar)
4. ✅ **Zero manutenção:** Infraestrutura gerenciada
5. ✅ **Exploração exaustiva:** Certeza científica absoluta

### Implementação Recomendada

```
Notícia → AWS Bedrock (Claude Haiku) → Classificação L3
              ↓
         Cache Redis (opcional)
```

**SLAs esperados:**
- Accuracy: 80%+ L3
- Latência: <3s p95
- Disponibilidade: 99.9%
- Custo: ~$100/mês (@1k/dia)

---

## 📂 Estrutura de Arquivos

```
embeddings/
├── classifiers/
│   ├── bedrock_classifier_json.py     # AWS Bedrock (Fase 1, 2)
│   ├── local_classifier.py            # Ollama (Fase 3)
│   └── base.py                        # Interface comum
├── prompts/
│   ├── classification_prompts_json.py       # JSON estruturado (direto)
│   └── classification_prompts_hierarchical.py # 3 etapas (hierárquico)
├── scripts/
│   ├── evaluate_llm_apis_json.py      # Fase 2 (11 modelos API)
│   ├── evaluate_hierarchical_medium.py # Fase 3 (5 modelos base)
│   ├── evaluate_direct_medium.py      # Fase 3 (direta)
│   ├── test_phi4_hierarchical.py      # Testes específicos
│   ├── test_deepseek_r1_*.py          # Chain-of-thought
│   ├── test_nemotron3_33b_*.py        # Modelos grandes
│   └── test_*.py                      # Outros testes
├── data/classification/
│   ├── arvore.yaml                    # Taxonomia 500 categorias
│   └── news_classification_test_annotated.csv # 200 notícias
├── config/
│   ├── models_config.yaml             # 11 modelos API
│   └── local_models_config.yaml       # 8 modelos locais
├── results/
│   ├── llm_evaluation/                # Fase 1 (APIs simples)
│   ├── comparison_summary_json.csv    # Fase 2 (taxonomia)
│   ├── hierarchical_medium/           # Fase 3 (hierárquica)
│   └── direct_medium/                 # Fase 3 (direta)
└── docs/
    ├── PHASE3_LOCAL_EXPERIMENTS_LOG.md  # Log técnico detalhado
    ├── FINAL_REPORT_ISSUE3.md           # Relatório executivo ✨
    ├── TECHNICAL_REPORT_ISSUE3.md       # Report fases 1 e 2
    └── PLAN_LOCAL_MODELS.md             # Plano original fase 3
```

---

## 🚀 Como Reproduzir

### Fase 2 - APIs (Claude Haiku vencedor)

```bash
cd source/embeddings

# Avaliar 11 modelos AWS Bedrock
python scripts/evaluate_llm_apis_json.py

# Ver resultados
cat results/comparison_summary_json.csv
```

### Fase 3 - Modelos Locais (Llama 8B campeão local)

**Pré-requisitos:**
- GPU com 23GB+ VRAM (testamos L4)
- Ollama instalado
- Modelos baixados (~40GB)

```bash
# Baixar modelos (no EC2)
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull gemma2:2b-instruct-q4_K_M
ollama pull qwen2.5:14b-instruct-q4_K_M
# ... etc

# Teste médio hierárquico (50 notícias, 3 modelos)
cd source/embeddings
python scripts/evaluate_hierarchical_medium.py

# Teste médio direto (50 notícias, 3 modelos)
python scripts/evaluate_direct_medium.py

# Testes específicos
python scripts/test_phi4_hierarchical.py
python scripts/test_deepseek_r1_hierarchical.py
python scripts/test_nemotron3_33b_hierarchical.py
```

**Tempo estimado:**
- Teste médio: 10-15 min
- Teste completo (200 notícias): 30-45 min
- Todos modelos: 2-3 horas

---

## 📖 Documentação Completa

### Relatórios Principais

1. **[FINAL_REPORT_ISSUE3.md](docs/FINAL_REPORT_ISSUE3.md)** ⭐
   - Relatório executivo final
   - Recomendações e justificativas
   - Análise econômica completa

2. **[PHASE3_LOCAL_EXPERIMENTS_LOG.md](docs/PHASE3_LOCAL_EXPERIMENTS_LOG.md)**
   - Log técnico detalhado de todos experimentos
   - Metodologia, resultados, lições aprendidas
   - Documentação exaustiva

3. **[TECHNICAL_REPORT_ISSUE3.md](docs/TECHNICAL_REPORT_ISSUE3.md)**
   - Relatório técnico fases 1 e 2
   - Experimentos com APIs

### Guias e Planos

- `docs/PLAN_LOCAL_MODELS.md` - Plano original fase 3
- `docs/SOLUTION_SUMMARY.md` - Resumo da solução técnica
- `README_LOCAL_MODELS.md` - Guia modelos locais

---

## 🎓 Lições Aprendidas

### Para futuras issues

**Quando testar modelos locais:**
- ✅ Tarefa simples (accuracy não crítica)
- ✅ Volume altíssimo (>50k/dia)
- ✅ Dados sensíveis (não podem sair servidor)

**Quando confiar em APIs:**
- ✅ Tarefa complexa (accuracy crítica)
- ✅ APIs funcionam bem (>70%)
- ✅ Volume moderado (<10k/dia)
- ✅ Time pequeno (overhead importa)

### Top 10 aprendizados

1. Tamanho ≠ Qualidade (Llama 8B > Qwen 32B)
2. Hierárquica >> Direta (sem exceções)
3. Quantização Q4 é suficiente
4. Reasoning specialists não ajudam classificação
5. Offloading mata performance
6. Context window ≠ capacidade de processar
7. APIs comerciais têm vantagem intransponível
8. GPU resolve latência, não capacidade
9. Exploração exaustiva previne decisões ruins
10. TCO importa mais que custo de infra

---

## 🔗 Links Úteis

**Documentação externa:**
- [AWS Bedrock Model IDs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [Anthropic Claude](https://docs.anthropic.com/claude/docs)

**Repo GitHub:**
- [Issues](https://github.com/destaquesgovbr/data-science/issues/3)
- [Pull Requests](https://github.com/destaquesgovbr/data-science/pulls)

---

## 👥 Contribuidores

**Autor:** Luis Felipe de Moraes (lpmoraes@cpqd.com.br)  
**Organização:** CPQD / Governo Federal (Destaques Gov.br)  
**Data:** 2026-04 a 2026-05-06  

---

**Issue #3 oficialmente concluída. Decisão: Claude Haiku em produção.** ✅

_Última atualização: 2026-05-06_
