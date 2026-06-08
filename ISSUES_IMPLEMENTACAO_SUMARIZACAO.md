# Issues: Implementação do Sistema de Sumarização em Produção

**Base:** Resultados da Issue #4 - Experimento de Sumarização  
**Status:** Backlog para implementação pós-pesquisa  
**Data:** Maio 2026

---

## Issue #5: Pipeline de Sumarização Abstrativa para Produção

**Tipo:** Implementação / Engenharia de Produção  
**Status:** 🟡 Planejado  
**Prioridade:** Alta  
**Complexidade:** 8-10 semanas  
**Dependências:** Issue #4 (concluída)

### Contexto e Motivação

Com a conclusão da Issue #4, temos:
- Modelo selecionado: **Amazon Nova Pro V2** (ROUGE-L 0.518, +17% vs benchmarks públicos)
- Alternativa validada: **Llama 3.3 70B V2** (ROUGE-L 0.308, mas 100% aceitável qualitativamente)
- Prompt otimizado: **Prompt V2 com 3-shot learning**
- Fallback definido: **Enhanced TextRank** (ROUGE-L 0.381)

Agora precisamos **transformar esse protótipo de pesquisa em sistema de produção**, com API, monitoramento, qualidade garantida e escalabilidade.

### Objetivo Geral

Implementar sistema de sumarização abstrativa em produção, capaz de:
- ✅ Processar notícias em tempo real via API REST
- ✅ Manter qualidade: ROUGE-L > 0.48 (com margem de segurança de 7%)
- ✅ Garantir disponibilidade: 99%+ com sistema de fallback
- ✅ Controlar custos: monitoramento e break-even analysis para decisão Bedrock vs self-hosted
- ✅ Observabilidade: métricas, logs, alertas, dashboards

### Abordagem Técnica

#### 1. Arquitetura do Sistema

```
┌─────────────┐
│   Cliente   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│  API REST (FastAPI)             │
│  - Autenticação (API key)       │
│  - Rate limiting                │
│  - Validação input/output       │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  SummarizationService           │
│  - Pré-processamento            │
│  - Retry logic / circuit breaker│
└────────┬───────────┬────────────┘
         │           │
         │           │ (fallback automático)
         ▼           ▼
┌─────────────┐  ┌──────────────────┐
│ Nova Pro V2 │  │ Enhanced TextRank│
│  (Bedrock)  │  │   (local)        │
└─────────────┘  └──────────────────┘
         │           │
         └──────┬────┘
                ▼
┌─────────────────────────────────┐
│  Pós-processamento              │
│  - Truncamento (verbosidade)    │
│  - Validação final              │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Observabilidade                │
│  - Métricas (Prometheus)        │
│  - Logs (JSON estruturado)      │
│  - Alertas (Slack)              │
│  - Dashboard (Grafana)          │
└─────────────────────────────────┘
```

#### 2. Stack Tecnológica

- **API:** FastAPI (Python 3.10+)
- **LLM:** AWS Bedrock (amazon.nova-pro-v1:0)
- **Fallback:** Bibliotecas locais (NetworkX, NLTK, spaCy)
- **Cache:** Redis (opcional, para otimização)
- **Métricas:** Prometheus + Grafana
- **Logging:** Python logging (JSON) → CloudWatch/ELK
- **Deploy:** Docker + AWS ECS/EKS ou EC2
- **CI/CD:** GitHub Actions

#### 3. Tratamento de Verbosidade

**Problema identificado:** 47% dos resumos têm 4-6 sentenças (target: 2-3)

**Solução:**
```python
def truncate_summary(text: str, max_sentences: int = 3) -> str:
    """
    Trunca resumo mantendo completude semântica.
    Evita truncamento no meio de citações/parênteses.
    """
    sentences = split_sentences(text)  # NLTK ou regex robusto
    if len(sentences) <= max_sentences:
        return text
    
    # Truncar para max_sentences
    truncated = sentences[:max_sentences]
    
    # Validar: não deixar citação/parêntese aberto
    result = ' '.join(truncated)
    if is_semantically_incomplete(result):
        # Tentar com max_sentences-1
        result = ' '.join(truncated[:-1])
    
    return result
```

**Flag configurável:** `enable_truncation` (default: True)

#### 4. Monitoramento de Qualidade

**ROUGE mensal automatizado:**
- Amostra: 100 resumos aleatórios/mês
- Referências: geradas via Claude Haiku (mesmo método Issue #4)
- Baseline: ROUGE-L 0.518
- **Alerta:** se ROUGE-L < 0.48 (drift > 7%)

**Métricas de produção:**
- Latência: P50, P95, P99 (target P95 < 3s)
- Taxa de sucesso: % requisições OK (target > 99%)
- Taxa de fallback: % uso Enhanced TextRank (target < 1%)
- Custo: por requisição e total/dia
- Verbosidade: % resumos com > 3 sentenças
- Taxa de truncamento: quando ativo

#### 5. Decisão Infraestrutura: Bedrock vs Self-Hosted

**Análise de break-even:**

| Cenário | Bedrock (Nova Pro) | Self-Hosted (Llama 70B) |
|---------|--------------------|-----------------------|
| **Custo fixo/mês** | $0 | $4,082 (g5.12xlarge) |
| **Custo variável** | $0.008/resumo | ~$0 |
| **Break-even** | - | ~500k resumos/mês |
| **Qualidade (ROUGE-L)** | 0.518 | 0.308 (-42.7%) |
| **Qualidade (humana)** | 100% aceitável | 100% aceitável |

**Decisão:**
- **Volume < 100k/mês:** Usar Bedrock Nova Pro (custo ~$800/mês)
- **Volume 100k-500k/mês:** Avaliar Nova 2 Lite (92% mais barato, ROUGE 0.502)
- **Volume > 500k/mês:** Migrar para Llama 70B self-hosted (ROI positivo)

**Implementação:** Issue #5.15 avaliará necessidade após 3 meses em produção

### Entregas Planejadas (Deliverables)

#### Core (obrigatório para produção):

1. **`summarization_service.py`** - Serviço encapsulado com Nova Pro + fallback
2. **`api/main.py`** - API REST com FastAPI
3. **`tests/test_regression.py`** - 20 notícias com golden summaries
4. **`monitoring/metrics.py`** - Coleta de métricas Prometheus
5. **`monitoring/logging_config.py`** - Logging estruturado JSON
6. **`docs/API.md`** - Documentação completa da API
7. **`docs/OPERATIONS.md`** - Playbooks de troubleshooting
8. **`.github/workflows/deploy.yml`** - CI/CD pipeline
9. **`dashboards/grafana.json`** - Dashboard de monitoramento
10. **`docker-compose.yml`** - Setup completo para staging/prod

#### Otimizações (pós-MVP):

11. **Cache Redis** - Para notícias repetidas (~20% economia)
12. **Batch endpoint** - Processar múltiplas notícias
13. **A/B test Nova Pro vs Nova 2 Lite** - Otimização de custo
14. **Feedback loop** - Thumbs up/down dos usuários

### Métricas de Sucesso

**Qualidade:**
- ✅ ROUGE-L médio > 0.48 (mensal)
- ✅ 0 alucinações críticas (testes de regressão)
- ✅ Taxa de verbosidade < 10% (com truncamento)

**Performance:**
- ✅ Latência P95 < 3s
- ✅ Disponibilidade > 99%
- ✅ Taxa de fallback < 1%

**Custo:**
- ✅ Custo/resumo conhecido e monitorado
- ✅ Decisão Bedrock vs self-hosted baseada em volume real
- ✅ Não ultrapassar budget sem alerta prévio

### Cronograma Estimado

**Sprint 1-2 (Setup e Core):** 4 semanas
- Credenciais AWS, SummarizationService, API REST, fallback

**Sprint 3 (Observabilidade):** 2 semanas
- Métricas, logs, alertas, dashboard

**Sprint 4 (Qualidade):** 2 semanas
- Validação ROUGE, testes de regressão, análise verbosidade

**Sprint 5 (Deploy):** 2 semanas
- CI/CD, staging, deploy produção, documentação

**Total:** 10 semanas (core) + 2-4 semanas (otimizações)

### Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **Throttling Bedrock** | Média | Alto | Implementar retry exponencial + circuit breaker + fallback |
| **Degradação qualidade** | Baixa | Alto | Monitoramento ROUGE mensal + alertas |
| **Custo inesperado** | Média | Médio | Alertas de custo + break-even analysis proativa |
| **Verbosidade persistente** | Média | Baixo | Truncamento pós-processamento (já planejado) |
| **Latência alta** | Baixa | Médio | Cache Redis + monitoramento P95 |

### Referências

- **Documento de pesquisa:** `source/summarization/docs/EXPERIMENTO_SUMARIZACAO.md`
- **Código base:** `source/summarization/summarizers_abstractive_v2.py`
- **Validação Llama:** `source/summarization/results/llama_70b_human_sample_evaluation.csv`
- **Dataset validação:** `source/summarization/data/human_evaluation_sample.csv`

### Aprovações Necessárias

- [ ] Aprovação de orçamento para Bedrock (estimativa inicial: $800-1000/mês)
- [ ] Definição de SLA com stakeholders (latência, disponibilidade)
- [ ] Acesso IAM para credenciais Bedrock produção
- [ ] Infraestrutura: ECS/EKS ou EC2 para API

---

## Sub-Issues Detalhadas

### Issue #5.1: Setup e Credenciais
**Objetivo:** Configurar credenciais AWS Bedrock seguras para produção  
**Estimativa:** 2h  
**Entrega:** IAM role, secrets manager, teste de acesso

### Issue #5.2: SummarizationService
**Objetivo:** Criar serviço encapsulado com Nova Pro + retry logic  
**Estimativa:** 4h  
**Entrega:** Classe `SummarizationService` testada

### Issue #5.3: Sistema de Fallback
**Objetivo:** Implementar fallback automático para Enhanced TextRank  
**Estimativa:** 3h  
**Entrega:** Circuit breaker funcional

### Issue #5.4: Pós-processamento
**Objetivo:** Truncamento inteligente para verbosidade  
**Estimativa:** 2h  
**Entrega:** Função `truncate_summary()` + testes

### Issue #5.5: API REST
**Objetivo:** Endpoint `/api/v1/summarize` com FastAPI  
**Estimativa:** 6h  
**Entrega:** API completa + Swagger docs

### Issue #5.6: Métricas Prometheus
**Objetivo:** Coleta de latência, sucesso, fallback, custo  
**Estimativa:** 4h  
**Entrega:** Endpoint `/metrics`

### Issue #5.7: Logging Estruturado
**Objetivo:** Logs JSON com metadata (sem conteúdo LGPD)  
**Estimativa:** 2h  
**Entrega:** Config de logging + rotação

### Issue #5.8: Sistema de Alertas
**Objetivo:** Alertas para erro, latência, fallback, custo  
**Estimativa:** 3h  
**Entrega:** Integração Slack/PagerDuty

### Issue #5.9: Validação ROUGE Mensal
**Objetivo:** Pipeline automático de amostra + ROUGE  
**Estimativa:** 4h  
**Entrega:** Script agendado + relatório

### Issue #5.10: Testes de Regressão
**Objetivo:** 20 notícias golden + CI check  
**Estimativa:** 4h  
**Entrega:** Suite de testes + dataset

### Issue #5.11: Cache Redis
**Objetivo:** Cache por hash SHA256 (TTL 7 dias)  
**Estimativa:** 3h  
**Entrega:** Integração Redis + métricas hit ratio

### Issue #5.12: CI/CD Pipeline
**Objetivo:** GitHub Actions: lint, test, deploy  
**Estimativa:** 4h  
**Entrega:** `.github/workflows/deploy.yml`

### Issue #5.13: Documentação
**Objetivo:** API, arquitetura, operations, deployment  
**Estimativa:** 4h  
**Entrega:** 4 documentos markdown

### Issue #5.14: Staging Environment
**Objetivo:** Ambiente idêntico a prod para testes  
**Estimativa:** 3h  
**Entrega:** Infra staging + deploy automático

### Issue #5.15: Deploy Produção
**Objetivo:** Canary release + monitoramento  
**Estimativa:** 4h  
**Entrega:** Sistema em produção estável

### Issue #5.16: Dashboard Grafana
**Objetivo:** Painéis: throughput, qualidade, custo, erros  
**Estimativa:** 3h  
**Entrega:** Dashboard configurado

### Issue #5.17: Batch Processing
**Objetivo:** Endpoint para múltiplas notícias paralelas  
**Estimativa:** 4h  
**Entrega:** `/api/v1/summarize/batch`

### Issue #5.18: Avaliação Migração Llama 70B
**Objetivo:** Break-even analysis com dados reais  
**Estimativa:** 8h  
**Dependência:** 3+ meses em produção  
**Entrega:** Documento de decisão

### Issue #5.19: A/B Test Nova Pro vs Nova 2 Lite
**Objetivo:** Testar modelo 92% mais barato  
**Estimativa:** 6h  
**Dependência:** 1+ mês em produção  
**Entrega:** Análise estatística + decisão

### Issue #5.20: Feedback Loop Usuários
**Objetivo:** Thumbs up/down para qualidade percebida  
**Estimativa:** 4h  
**Entrega:** Coleta + dashboard satisfação

### Issue #5.21: Fine-tuning Nova 2 Lite
**Objetivo:** Fine-tune para igualar Nova Pro com custo menor  
**Estimativa:** 40h  
**Condição:** Se #5.19 mostrar gap de qualidade  
**Entrega:** Modelo custom + comparação

---

## Priorização

### P0 - Crítico (MVP)
#5.1, #5.2, #5.3, #5.4, #5.5, #5.12, #5.13, #5.14, #5.15

### P1 - Alta (Produção robusta)
#5.6, #5.7, #5.8, #5.9, #5.10, #5.16

### P2 - Média (Otimizações)
#5.11, #5.17

### P3 - Baixa (Futuro/Backlog)
#5.18, #5.19, #5.20, #5.21

---

**Estimativa Total:**  
- Core (P0+P1): ~60h → 2 meses (1 dev full-time)  
- Com otimizações (P2): +10h  
- Backlog (P3): +60h (condicional)

**Time to Production:** 8-10 semanas
