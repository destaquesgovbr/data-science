# Resumo: Issues de Implementação

**Base:** Issues #1-4 de Pesquisa (concluídas)  
**Data:** Maio 2026

---

## Issues de Implementação Planejadas

### ✅ Issue #5: Sumarização Abstrativa em Produção
- **Arquivo:** [ISSUES_IMPLEMENTACAO_SUMARIZACAO.md](ISSUES_IMPLEMENTACAO_SUMARIZACAO.md)
- **Base:** Issue #4 concluída
- **Modelo:** Amazon Nova Pro V2 (ROUGE-L 0.518, +17% vs benchmarks)
- **Alternativa:** Llama 3.3 70B V2 (100% aceitável, para break-even > 500k/mês)
- **Status:** Planejado
- **Estimativa:** 8-10 semanas

### ✅ Issue #6: Pipeline de Embeddings para Retrieval
- **Arquivo:** [ISSUES_IMPLEMENTACAO_EMBEDDINGS.md](ISSUES_IMPLEMENTACAO_EMBEDDINGS.md)
- **Base:** Issue #1 concluída
- **Modelo:** BGE-M3 zero-shot (não precisa fine-tuning - Issue #2)
- **Infra:** GPU L4 (24GB) disponível na EC2
- **Estratégia:** Migração gradual (30 dias, 10k docs/dia)
- **Status:** Planejado
- **Estimativa:** 5 semanas + 30 dias migração automática

### ❌ Issue #7: Fine-tuning de Embeddings
- **Status:** CANCELADA
- **Motivo:** Issue #2 provou que BGE-M3 zero-shot já é excelente
- **Conclusão:** Ganho de fine-tuning é irrisório vs esforço
- **Decisão:** Usar BGE-M3 out-of-the-box (sem fine-tuning)

### ✅ Issue #8: Classificação com LLMs
- **Arquivo:** [ISSUES_IMPLEMENTACAO_CLASSIFICACAO.md](ISSUES_IMPLEMENTACAO_CLASSIFICACAO.md)
- **Base:** Issue #3 concluída
- **Modelo:** [A definir: API (Claude/GPT) vs Local (Llama)]
- **Decisão:** Baseada em volume e custo
- **Status:** Planejado
- **Estimativa:** 6 semanas

---

## Priorização

### P0 - Crítico
1. **Issue #5** - Sumarização (demanda imediata)
2. **Issue #6** - Embeddings (fundação para busca)

### P1 - Alta
3. **Issue #8** - Classificação (complementa pipeline)

### ~~P2 - Cancelada~~
~~4. Issue #7 - Fine-tuning (não necessário)~~

---

## Aprendizados das Issues de Pesquisa

### Issue #1: Embeddings
- **Modelo vencedor:** BGE-M3 (multilingual, 1024 dim, 8192 tokens)
- **Qualidade:** NDCG@10 [resultado da Issue #1]
- **Decisão:** Zero-shot suficiente (Issue #2)

### Issue #2: Fine-tuning
- **Conclusão:** Fine-tuning NÃO vale a pena
- **Motivo:** BGE-M3 já generaliza muito bem
- **Ganho:** Irrisório vs esforço
- **Decisão:** Usar modelo out-of-the-box

### Issue #3: LLMs para Classificação
- **Modelos testados:** APIs (GPT-4, Claude, Gemini) + Locais (Llama)
- **Métricas:** Accuracy, F1, latência, custo
- **Decisão pendente:** API vs Local (baseado em volume)

### Issue #4: Sumarização
- **Modelo vencedor:** Amazon Nova Pro V2
- **Qualidade:** ROUGE-L 0.518 (+17% vs CNN/DailyMail 0.44)
- **Alternativa validada:** Llama 3.3 70B (break-even 500k/mês)
- **Problema identificado:** Verbosidade (47% têm 4-6 sentenças)
- **Solução:** Truncamento pós-processamento

---

## Roadmap de Implementação

```
Mês 1-2: Issue #5 (Sumarização)
  ├─ API de sumarização
  ├─ Fallback Enhanced TextRank
  └─ Monitoramento de qualidade

Mês 2-3: Issue #6 (Embeddings)
  ├─ Setup GPU L4 + dual index
  ├─ API de busca semântica
  └─ Migração gradual (paralelo)

Mês 3-4: Issue #8 (Classificação)
  ├─ Decisão API vs Local
  ├─ API de classificação
  └─ Fallback BERT

Total: ~4 meses para stack completo
```

---

**Última atualização:** 2026-05-21
