# Guia de Fases - Issue #6: Análise de Sentimento

**Responsável:** Luis Felipe de Moraes  
**Data início:** 2026-06-30  
**Estimativa total:** 8 semanas

---

## 📊 Visão Geral das Fases

```
Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6 → Fase 7
Léxico   BERT     LLM      Ensemble  Análises  Produção  Docs
         (cond.)  (early)  (cond.)   Avançadas          Final

1 sem    1.5 sem  1 sem    1 sem     1 sem     1 sem     1 sem
```

**Legenda:**
- **(cond.)** = Condicional - executa se necessário
- **(early)** = Teste antecipado - pode mudar ordem

---

## 🎯 Fase 1: Baseline Léxico + LLM Quick Test

**Duração:** 1 semana  
**Status:** 🔄 Em andamento  
**Objetivo:** Estabelecer baseline e identificar se LLM resolve problema

### Tasks

#### A. Baseline Léxico
- [x] Pesquisar léxicos PT-BR (OpLexicon, SentiLex, LIWC, NRC)
- [x] Revisar literatura acadêmica
- [ ] **Escolher léxico primário** (OpLexicon OU SentiLex)
- [ ] Implementar analisador léxico
- [ ] Criar dataset inicial: 50 notícias anotadas
- [ ] Avaliar baseline: accuracy, F1-macro, confusion matrix
- [ ] Análise de erros

#### B. LLM Quick Test (NOVO)
- [ ] Testar Nova 2 Lite zero-shot (prompt simples)
- [ ] Testar Claude Haiku 4.5 zero-shot
- [ ] Comparar com baseline léxico
- [ ] **DECISÃO:** Se LLM > 70%, priorizar Fase 3 (prompt engineering)

### Critérios de Sucesso
- ✅ Baseline léxico implementado
- ✅ Dataset 50 notícias com Kappa > 0.65
- ✅ LLM testado em mesmo dataset
- ✅ Decisão documentada: continuar Fase 2 (BERT) ou pular para Fase 3 (LLM)

### Deliverables
- `data/datasets/annotated_50.csv` - Dataset anotado
- `results/metrics/fase1_results.csv` - Métricas léxico + LLM
- `docs/06_issue6_sentiment/fase1_lexicos.md` - Documentação completa
- **DECISÃO:** Próximo passo (BERT vs LLM prompt optimization)

### Tempo estimado
- Anotação manual: 2-3 dias (50 notícias)
- Implementação léxico: 1 dia
- Teste LLM: 0.5 dia
- Análise e documentação: 1 dia

---

## 🤖 Fase 2: Modelos BERT (CONDICIONAL)

**Duração:** 1.5 semanas  
**Status:** 📋 Planejada (condicional)  
**Objetivo:** Avaliar BERT zero-shot e fine-tuned

### Condição de Execução
Execute esta fase SE:
- LLM baseline (Fase 1) < 70% accuracy, OU
- Latência LLM for inviável (> 5s), OU
- Custo LLM for proibitivo (> $0.01/query)

Caso contrário: **PULE para Fase 3** (otimização LLM)

### Tasks (se executar)
- [ ] Setup transformers + torch
- [ ] Testar BERTimbau sentiment (zero-shot)
- [ ] Testar XLM-RoBERTa sentiment (zero-shot)
- [ ] **DECISÃO:** Fine-tune necessário?
  - SE zero-shot < 70% → Fine-tune com dataset expandido (150-200 notícias)
  - SE zero-shot > 70% → Usar pré-treinado
- [ ] Comparar latência BERT vs LLM
- [ ] Comparar accuracy BERT vs LLM vs Léxico
- [ ] Análise de erros por classe (pos/neu/neg)

### Critérios de Sucesso
- BERT testado (zero-shot mínimo)
- Accuracy > Baseline léxico
- Trade-off BERT vs LLM documentado (accuracy, latência, custo)

### Deliverables
- `results/metrics/fase2_bert_results.csv`
- `notebooks/bert_experiments.ipynb`
- `docs/06_issue6_sentiment/fase2_bert.md`

### Tempo estimado
- Zero-shot tests: 1 dia
- Fine-tuning (se necessário): 5-7 dias (dataset + treino + eval)
- Análise: 1 dia

---

## 🧠 Fase 3: LLM-based Analysis

**Duração:** 1 semana  
**Status:** 📋 Planejada  
**Objetivo:** Otimizar prompt engineering para melhor LLM

### Tasks
- [ ] Definir prompts:
  - [ ] Zero-shot (baseline da Fase 1)
  - [ ] Few-shot (3-5 exemplos)
  - [ ] Chain-of-thought (raciocínio explícito)
  - [ ] Domain-specific (contexto governamental)
- [ ] Testar modelos Bedrock:
  - [ ] Nova 2 Lite (custo-efetivo)
  - [ ] Claude Haiku 4.5 (rápido)
  - [ ] Llama 3.3 70B (alternativa)
- [ ] Análise comparativa:
  - [ ] Accuracy por estratégia de prompt
  - [ ] Confidence calibration
  - [ ] Análise qualitativa de justificativas
  - [ ] Trade-off latência/custo/accuracy
- [ ] Selecionar melhor configuração (modelo + prompt)

### Critérios de Sucesso
- Melhor LLM > 70% accuracy
- Confidence calibration documentada
- Trade-off custo/qualidade claro

### Deliverables
- `prompts/sentiment_prompts.yaml` - Biblioteca de prompts
- `results/metrics/fase3_llm_results.csv`
- `notebooks/llm_experiments.ipynb`
- `docs/06_issue6_sentiment/fase3_llm.md`

### Tempo estimado
- Desenvolvimento prompts: 2 dias
- Testes comparativos: 2 dias
- Análise e seleção: 1 dia

---

## 🔀 Fase 4: Ensemble Methods (CONDICIONAL)

**Duração:** 1 semana  
**Status:** 📋 Planejada (condicional)  
**Objetivo:** Combinar abordagens SE ganhos justificarem complexidade

### Condição de Execução
Execute esta fase SE:
- Melhor modelo individual < 75% accuracy, E
- Ensemble promete ganho > 5% (testado em amostra)

Caso contrário: **PULE para Fase 5** e documente decisão de usar modelo único.

### Tasks (se executar)
- [ ] Implementar estratégias:
  - [ ] Voting (maioria simples)
  - [ ] Weighted voting (otimizar pesos)
  - [ ] Stacking (meta-learner: LR, RF, XGBoost)
  - [ ] Conditional (léxico filtra → ML decide ambíguos)
- [ ] Otimizar hiperparâmetros
- [ ] Avaliar trade-offs:
  - [ ] Ganho de accuracy
  - [ ] Latência (2-3 modelos vs 1)
  - [ ] Complexidade operacional
  - [ ] Custo
- [ ] **DECISÃO:** Ensemble vale a pena?
  - SE ganho > 5% E latência aceitável → Deploy ensemble
  - SE ganho < 5% OU latência alta → Usar melhor modelo único

### Critérios de Sucesso
- Ensemble testado
- Decisão fundamentada: ensemble vs modelo único
- Trade-offs documentados (não importa qual escolha)

### Deliverables
- `src/ensemble_analyzer.py` (se implementado)
- `results/metrics/fase4_ensemble_results.csv`
- `docs/06_issue6_sentiment/fase4_ensemble.md`
- **DECISÃO CRÍTICA:** Modelo final escolhido com justificativa

### Tempo estimado
- Implementação: 2 dias
- Otimização: 2 dias
- Análise e decisão: 1 dia

---

## 📈 Fase 5: Análises Avançadas

**Duração:** 1 semana  
**Status:** 📋 Planejada  
**Objetivo:** Explorar aplicações específicas do domínio

### Tasks
- [ ] Sentimento por entidade:
  - [ ] Integrar com NER (issues anteriores)
  - [ ] Análise: "Ministro elogia X" → sentimento sobre X
- [ ] Evolução temporal:
  - [ ] Sentimento sobre tópicos ao longo do tempo
  - [ ] Detecção de mudanças de tom
- [ ] Benchmark por órgão:
  - [ ] Comparação entre agências
  - [ ] Identificação de padrões
- [ ] Dashboard e visualizações:
  - [ ] Timeline de sentimento
  - [ ] Heatmap por órgão/tema
  - [ ] Word clouds por polaridade
- [ ] Documentar casos de uso

### Critérios de Sucesso
- Pelo menos 3 análises específicas implementadas
- Casos de uso documentados com exemplos
- Visualizações geradas

### Deliverables
- `src/entity_sentiment.py`
- `src/temporal_analysis.py`
- `notebooks/advanced_analysis.ipynb`
- `results/visualizations/` (gráficos)
- `docs/06_issue6_sentiment/fase5_analises_avancadas.md`

### Tempo estimado
- Implementação análises: 3 dias
- Visualizações: 2 dias
- Documentação casos de uso: 1 dia

---

## 🚀 Fase 6: Integração e Produção

**Duração:** 1 semana  
**Status:** 📋 Planejada  
**Objetivo:** Integrar modelo escolhido ao pipeline

### Tasks
- [ ] Integração com pipeline:
  - [ ] Avaliar integração no prompt único (classificação + resumo + sentimento)
  - [ ] OU: Chamada separada se arquitetura exigir
- [ ] Validar modelo escolhido:
  - [ ] SE LLM único → Configurar em `llm_client.py`
  - [ ] SE BERT → Implementar módulo separado
  - [ ] SE Ensemble → Orquestração de modelos
- [ ] Testes em produção:
  - [ ] Batch processing (1000 notícias)
  - [ ] Performance e latência
  - [ ] Custo real
- [ ] Monitoring:
  - [ ] Distribuição de sentimentos
  - [ ] Drift detection
  - [ ] Alertas de anomalias

### Critérios de Sucesso
- Modelo integrado ao pipeline
- Testes em produção validados
- Monitoring configurado

### Deliverables
- `src/news_enrichment/sentiment_module.py` (ou integração no prompt)
- `scripts/backfill_sentiment.py` (se necessário)
- `docs/06_issue6_sentiment/fase6_integracao_producao.md`

### Tempo estimado
- Integração: 2 dias
- Testes: 2 dias
- Monitoring: 1 dia

---

## 📚 Fase 7: Documentação Final

**Duração:** 1 semana  
**Status:** 📋 Planejada  
**Objetivo:** Consolidar aprendizados e deliverables

### Tasks
- [ ] **Relatório Técnico** (30-40 páginas):
  - [ ] Introdução e motivação
  - [ ] Revisão de literatura
  - [ ] Metodologia completa
  - [ ] Resultados de todas as fases executadas
  - [ ] Análise comparativa (léxico vs BERT vs LLM vs ensemble)
  - [ ] Modelo selecionado e justificativa
  - [ ] Análises avançadas e casos de uso
  - [ ] Limitações e trabalhos futuros
- [ ] **Apresentação Executiva** (15-18 slides):
  - [ ] Contexto e objetivos
  - [ ] Metodologia (resumida)
  - [ ] Principais resultados
  - [ ] Modelo recomendado
  - [ ] Casos de uso
  - [ ] ROI e próximos passos
- [ ] **README consolidado**
- [ ] **Revisão e fechamento da issue**

### Critérios de Sucesso
- Todos deliverables completos
- Conhecimento documentado (não só solução)
- Issue fechada

### Deliverables
- `docs/06_issue6_sentiment/relatorio_tecnico_completo.md`
- `docs/06_issue6_sentiment/apresentacao_executiva.pdf`
- `docs/06_issue6_sentiment/README_issue6.md` (atualizado)

### Tempo estimado
- Relatório: 3 dias
- Apresentação: 1 dia
- Revisão final: 1 dia

---

## 🎯 Critérios Globais de Qualidade

### Documentação (padrão Issue #5)
- ✅ Decisões técnicas justificadas com "Why" e "How to apply"
- ✅ Resultados mensuráveis e reproduzíveis
- ✅ Comparações quantitativas (tabelas, gráficos)
- ✅ Análise de trade-offs (não apenas "o que funciona melhor")
- ✅ Limitações documentadas honestamente

### Conhecimento Gerado
- ✅ Entendimento de sentimento em textos governamentais (vs redes sociais)
- ✅ Comparação fundamentada léxico vs BERT vs LLM
- ✅ Trade-offs accuracy vs latência vs custo vs complexidade
- ✅ Quando usar ensemble vs modelo único
- ✅ Aplicações específicas ao domínio

### Reprodutibilidade
- ✅ Código comentado e modular
- ✅ Scripts de teste documentados
- ✅ Dataset anotado com guidelines
- ✅ Notebooks com análises passo a passo
- ✅ Resultados em formato estruturado (CSV, JSON)

---

## 🚨 Pontos de Decisão Críticos

### Decisão 1: Fase 1 → Fase 2 ou Fase 3?
**Quando:** Fim da Fase 1  
**Critério:** Accuracy LLM > 70%?
- **SE SIM:** Pular para Fase 3 (otimizar LLM)
- **SE NÃO:** Ir para Fase 2 (testar BERT)

### Decisão 2: BERT Zero-shot ou Fine-tuning?
**Quando:** Durante Fase 2 (se executada)  
**Critério:** BERT zero-shot > 70%?
- **SE SIM:** Usar pré-treinado
- **SE NÃO:** Fine-tune com dataset expandido

### Decisão 3: Ensemble ou Modelo Único?
**Quando:** Fim da Fase 3 (antes da Fase 4)  
**Critério:** Melhor modelo < 75% E ensemble ganha > 5%?
- **SE SIM:** Implementar ensemble (Fase 4)
- **SE NÃO:** Usar melhor modelo único, documentar decisão

### Decisão 4: Integração no Prompt Único ou Separado?
**Quando:** Início da Fase 6  
**Critério:** Modelo escolhido é LLM (Nova/Claude)?
- **SE SIM:** Considerar integração no prompt único
- **SE NÃO (BERT):** Chamada separada

---

## 📊 Tracking de Progresso

### Status Atual
| Fase | Status | Progresso | Início | Fim Previsto | Fim Real |
|------|--------|-----------|--------|--------------|----------|
| Fase 1 | 🔄 Em andamento | 30% | 2026-06-30 | 2026-07-06 | - |
| Fase 2 | 📋 Condicional | 0% | TBD | TBD | - |
| Fase 3 | 📋 Planejada | 0% | TBD | TBD | - |
| Fase 4 | 📋 Condicional | 0% | TBD | TBD | - |
| Fase 5 | 📋 Planejada | 0% | TBD | TBD | - |
| Fase 6 | 📋 Planejada | 0% | TBD | TBD | - |
| Fase 7 | 📋 Planejada | 0% | TBD | TBD | - |

### Legenda
- 🔴 Não iniciada
- 📋 Planejada
- 🔄 Em andamento
- ⏸️ Pausada
- ✅ Concluída
- ⏭️ Pulada (com justificativa)

---

## 🔗 Links Rápidos

- [README Principal](README_issue6.md)
- [Fase 1: Baseline Léxico](fase1_lexicos.md)
- [Fase 2: BERT](fase2_bert.md) (quando criado)
- [Fase 3: LLM](fase3_llm.md) (quando criado)
- [Fase 4: Ensemble](fase4_ensemble.md) (quando criado)
- [Fase 5: Análises Avançadas](fase5_analises_avancadas.md) (quando criado)
- [Fase 6: Produção](fase6_integracao_producao.md) (quando criado)
- [Relatório Final](relatorio_tecnico_completo.md) (quando criado)

---

**Documento preparado por:** Claude Code  
**Última atualização:** 2026-07-02  
**Próxima revisão:** Após conclusão da Fase 1

---

_Este guia é um documento vivo. Atualize conforme progresso e decisões tomadas._
