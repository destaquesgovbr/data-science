# Issue #6: Análise de Sentimento em Notícias Governamentais

**Data de início:** 2026-06-30  
**Responsável:** Luis Felipe de Moraes  
**Status:** 🔄 Fase 1 em andamento (Baseline Léxico)  
**Branch:** `issue6`

---

## 📋 Visão Geral

### Objetivo

Desenvolver e avaliar sistema de análise de sentimento para notícias governamentais brasileiras, explorando abordagens léxicas, baseadas em BERT e LLMs, com foco em textos formais e predominantemente neutros.

### Hipótese Central

**Notícias governamentais apresentam desafio único para análise de sentimento devido à linguagem formal e predominância de tom neutro. Ensemble combinando análise léxica (termos específicos do domínio) + BERT (contexto local) + LLM (compreensão profunda) oferece melhor cobertura e precisão do que abordagens isoladas.**

### Desafio Principal

Diferentemente de domínios como redes sociais ou reviews (polarizados), notícias governamentais são:
- Majoritariamente neutras e factuais
- Linguagem formal e técnica
- Sentimento frequentemente sutil ou implícito
- Requerem compreensão de contexto governamental

### Deliverables (Requisitos da Issue)

1. ⬜ **Notebook comparativo** - Modelos léxicos, BERT e LLM testados
2. ⬜ **Relatório técnico** - 30-40 páginas de análise completa
3. ⬜ **Apresentação executiva** - 15-18 slides para gestores
4. ⬜ **Dataset anotado** - Gold standard para avaliação (200-300 notícias)
5. ⬜ **Modelo em produção** - Sistema escolhido integrado ao pipeline

---

## 🎯 Fundamentos Teóricos

### Referências Acadêmicas Principais

#### Sentiment Analysis - Foundation

**1. Liu, B. (2012) - "Sentiment Analysis and Opinion Mining"**
- Síntese Morgan & Claypool
- Fundamentos de SA: níveis (documento, sentença, aspecto)
- Abordagens: léxico, machine learning, híbrido

**2. Medhat, W., Hassan, A., Korashy, H. (2014) - "Sentiment analysis algorithms and applications: A survey"**
- Survey abrangente de técnicas
- https://doi.org/10.5121/aint.2014.4102
- Comparação: léxico vs ML vs híbrido

#### Portuguese Sentiment Analysis

**3. Souza, M., Vieira, R. (2012) - "Sentiment Analysis on Twitter Data for Portuguese Language"**
- Pioneiro em SA para PT-BR
- Construção de léxico (LIWC adaptado)
- Desafios de linguagem informal

**4. Freitas, L.A., Vieira, R. (2015) - "Ontology based feature level opinion mining for Portuguese reviews"**
- Análise de sentimento em nível de aspecto
- Ontologias para domínio específico
- Aplicação em reviews PT

**5. Brum, H., Nunes, M.G.V. (2018) - "Building a Sentiment Corpus of Tweets in Brazilian Portuguese"**
- TweetSentBR: 15k tweets anotados
- Baseline com léxico + SVM
- Desafios: sarcasmo, ironia, informalidade

#### BERT for Sentiment

**6. Devlin et al. (2019) - "BERT: Pre-training of Deep Bidirectional Transformers"**
- Arquitetura BERT
- https://arxiv.org/abs/1810.04805
- Fine-tuning para classification tasks

**7. Souza et al. (2020) - "BERTimbau: Pretrained BERT Models for Brazilian Portuguese"**
- Modelos BERT para PT-BR
- https://arxiv.org/abs/2010.05595
- Vocabulário adaptado, melhores resultados que multilingual

#### LLM-based Sentiment

**8. Wang et al. (2023) - "Is ChatGPT a Good Sentiment Analyzer?"**
- Avaliação zero-shot e few-shot
- https://arxiv.org/abs/2304.04339
- LLMs competem com modelos fine-tuned

**9. Zhu et al. (2023) - "Can ChatGPT Reproduce Human-Generated Labels?"**
- LLMs como anotadores
- Concordância alta em tarefas simples (sentiment)
- Limitações em nuance e ambiguidade

#### Domain-Specific Sentiment

**10. Hamborg et al. (2019) - "Automated identification of media bias in news articles"**
- Sentimento em notícias (domain similar)
- Desafios: objetividade vs viés sutil
- Abordagens multi-modal

### Best Practices Industriais

#### Hugging Face - Sentiment Models
- BERTimbau sentiment: `lm-finetune/bertimbau-sentiment`
- XLM-RoBERTa sentiment: `cardiffnlp/twitter-xlm-roberta-base-sentiment`
- Leaderboards e benchmarks para comparação

#### AWS Comprehend
- Sentiment analysis API (suporta PT-BR)
- Usado como baseline comercial

---

## 🏗️ Arquitetura do Sistema

### Visão Geral - Multi-Approach Ensemble

```
┌─────────────────────────────────────────────────────────────┐
│           Sentiment Analysis System Architecture            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input Text → [Preprocessing] → [Multi-Approach Analysis]  │
│                                         ↓                   │
│            ┌────────────────────────────┴────────────┐      │
│            │                                          │      │
│       [Approach 1]      [Approach 2]      [Approach 3]      │
│    Lexicon-based         BERT-based         LLM-based       │
│    ├─ OpLexicon         ├─ BERTimbau       ├─ Nova 2 Lite  │
│    ├─ SentiLex          ├─ XLM-RoBERTa     ├─ Claude       │
│    └─ Custom Gov        └─ Fine-tuned      └─ Llama        │
│            │                    │                   │        │
│            └────────────────────┴───────────────────┘        │
│                             ↓                                │
│                    [Ensemble Layer]                          │
│                    ├─ Voting (majority)                      │
│                    ├─ Weighted average                       │
│                    ├─ Stacking (meta-model)                  │
│                    └─ Conditional (léxico filter → ML)       │
│                             ↓                                │
│                    [Output]                                  │
│                    ├─ Label: pos/neu/neg                     │
│                    ├─ Score: -1.0 to 1.0                     │
│                    ├─ Confidence: 0.0 to 1.0                 │
│                    └─ Evidence: keywords/phrases             │
└─────────────────────────────────────────────────────────────┘
```

### Stack Tecnológico

#### Lexicon Resources
- **OpLexicon v3.0** - Léxico de polaridade PT-BR (33k termos)
- **SentiLex-PT** - Léxico para português europeu (adaptável)
- **LIWC-PT** - Linguistic Inquiry and Word Count (se disponível)
- **Custom Gov Lexicon** - Léxico específico domínio governamental

#### BERT Models
- **BERTimbau** - `neuralmind/bert-base-portuguese-cased` (base)
- **BERTimbau Sentiment** - `lm-finetune/bertimbau-sentiment` (fine-tuned)
- **XLM-RoBERTa** - `cardiffnlp/twitter-xlm-roberta-base-sentiment` (multilingual)

#### LLM Providers
- **AWS Bedrock** - Nova 2 Lite, Claude Haiku, Llama 3.3 70B
- **Ollama (local)** - Para experimentação rápida

#### Frameworks
- **Transformers** - Hugging Face (BERT models)
- **NLTK / spaCy** - Preprocessamento e léxico
- **Scikit-learn** - Ensemble methods, metrics
- **Polars / Pandas** - Data processing

#### Infrastructure
- **Compute:** GPU L4 (EC2) para fine-tuning BERT
- **Storage:** PostgreSQL para dataset anotado
- **Notebooks:** Jupyter para experimentação

---

## 📊 Métricas de Avaliação

### Métricas Primárias

**1. Accuracy**
- Percentual de classificações corretas (3 classes: pos/neu/neg)
- Target: > 75% (domínio difícil, baseline humano ~85%)

**2. F1-Score Macro**
- Média harmônica de precision/recall por classe
- Importante devido a desbalanceamento (maioria neutra)
- Target: > 0.70

**3. Confusion Matrix**
- Identificar padrões de erro (pos→neu, neg→neu?)
- Análise de confusão entre classes

### Métricas Secundárias

**4. Accuracy por Classe**
- F1 para positivo, neutro, negativo isoladamente
- Identificar pontos fracos

**5. Concordância Inter-Anotador (Kappa)**
- Cohen's Kappa para validar gold standard
- Target: > 0.65 (substantial agreement)

**6. Calibration (Confidence)**
- Correlação entre confidence score e accuracy
- Importante para thresholding em produção

### Métricas Operacionais

**7. Latência**
- Tempo médio por classificação
- Target: < 2s (LLM), < 100ms (BERT), < 10ms (léxico)

**8. Custo**
- Custo por 10k classificações
- Importante para viabilidade em produção

---

## 🗓️ Fases de Execução

### Fase 1: Baseline Léxico + LLM Quick Test (Semana 1) 🔄 EM ANDAMENTO

**Objetivo:** Estabelecer baseline léxico E testar LLM zero-shot para decisão estratégica

**Tasks:**

**A. Baseline Léxico**
- [x] Criar estrutura de diretórios e documentação
- [x] Pesquisar e baixar léxicos PT-BR disponíveis:
  - [x] OpLexicon v3.0
  - [x] SentiLex-PT
  - [x] LIWC-PT, NRC Emotion
- [ ] **Escolher léxico primário** (OpLexicon OU SentiLex)
- [ ] Implementar baseline léxico:
  - [ ] Preprocessamento (tokenização, normalização, stopwords)
  - [ ] Contagem de termos positivos/negativos
  - [ ] Normalização por tamanho de texto
  - [ ] Score agregado e classificação
- [ ] Criar dataset de teste inicial (50 notícias anotadas manualmente)
- [ ] Avaliar baseline: Accuracy, F1-macro, confusion matrix

**B. LLM Quick Test (NOVO)**
- [ ] Testar Nova 2 Lite zero-shot (prompt simples)
- [ ] Testar Claude Haiku 4.5 zero-shot
- [ ] Comparar com baseline léxico

**C. Decisão Estratégica**
- [ ] **SE LLM > 70%:** Priorizar Fase 3 (prompt engineering)
- [ ] **SE LLM < 70%:** Continuar para Fase 2 (BERT)
- [ ] Documentar decisão e justificativa

**Critério de sucesso:** 
- Baseline léxico implementado
- Dataset inicial anotado (50 notícias, Kappa > 0.65)
- LLM testado em mesmo dataset
- **Decisão tomada:** próximo passo (BERT ou LLM optimization)

**Arquivos esperados:**
- `src/lexicon_analyzer.py` - Implementação análise léxica
- `data/oplexicon.txt` - Léxico OpLexicon
- `data/test_dataset_50.csv` - Dataset teste inicial
- `scripts/test_lexicon.py` - Script de testes
- `docs/06_issue6_sentiment/fase1_lexicos.md` - Documentação

---

### Fase 2: Modelos BERT (Semana 2-3) - CONDICIONAL

**Objetivo:** Avaliar modelos BERT pré-treinados e fine-tuned para PT-BR

**⚠️ CONDIÇÃO DE EXECUÇÃO:**
Execute esta fase SE:
- LLM baseline (Fase 1) < 70% accuracy, OU
- Latência LLM for inviável (> 5s), OU
- Custo LLM for proibitivo (> $0.01/query)

Caso contrário: **PULE para Fase 3** (otimização LLM)

**Tasks (se executar):**
- [ ] Setup ambiente BERT (transformers, torch)
- [ ] Testar modelos pré-treinados:
  - [ ] BERTimbau sentiment (fine-tuned)
  - [ ] XLM-RoBERTa sentiment (multilingual)
- [ ] **DECISÃO:** Fine-tune necessário?
  - SE zero-shot < 70% → Fine-tune com dataset expandido (150-200 notícias)
  - SE zero-shot > 70% → Usar pré-treinado
- [ ] Avaliação comparativa:
  - [ ] Accuracy, F1-macro por modelo
  - [ ] Análise de erros vs baseline léxico e LLM
  - [ ] Latência e custo computacional
- [ ] Documentar Fase 2 (fase2_bert.md)

**Critério de sucesso:**
- BERT testado (zero-shot mínimo)
- Accuracy > Baseline léxico
- Trade-off BERT vs LLM documentado

**Arquivos esperados:**
- `src/bert_analyzer.py` - Implementação BERT
- `notebooks/bert_experiments.ipynb` - Experimentos
- `data/train_dataset_200.csv` - Dataset expandido
- `results/bert_metrics.csv` - Resultados
- `docs/06_issue6_sentiment/fase2_bert.md` - Documentação

---

### Fase 3: LLM-based Analysis (Semana 4)

**Objetivo:** Avaliar LLMs com prompt engineering (zero-shot e few-shot)

**Tasks:**
- [ ] Definir prompts para análise de sentimento:
  - [ ] Zero-shot (instruções simples)
  - [ ] Few-shot (3-5 exemplos)
  - [ ] Chain-of-thought (raciocínio explícito)
- [ ] Testar modelos via AWS Bedrock:
  - [ ] Amazon Nova 2 Lite
  - [ ] Claude Haiku 4.5
  - [ ] Llama 3.3 70B
- [ ] Avaliação:
  - [ ] Accuracy, F1-macro
  - [ ] Análise qualitativa de justificativas
  - [ ] Latência e custo
- [ ] Comparar zero-shot vs few-shot vs CoT
- [ ] Documentar Fase 3 (fase3_llm.md)

**Critério de sucesso:**
- LLMs testados com múltiplas estratégias de prompt
- Accuracy > 70% (target para melhor modelo)
- Trade-off custo/qualidade documentado

**Arquivos esperados:**
- `src/llm_analyzer.py` - Implementação LLM
- `prompts/sentiment_prompts.yaml` - Biblioteca de prompts
- `notebooks/llm_experiments.ipynb` - Experimentos
- `results/llm_comparison.csv` - Resultados
- `docs/06_issue6_sentiment/fase3_llm.md` - Documentação

---

### Fase 4: Ensemble Methods (Semana 5) - CONDICIONAL

**Objetivo:** Combinar abordagens SE ganhos justificarem complexidade

**⚠️ CONDIÇÃO DE EXECUÇÃO:**
Execute esta fase SE:
- Melhor modelo individual < 75% accuracy, E
- Ensemble promete ganho > 5% (testado em amostra)

Caso contrário: **PULE para Fase 5** e documente decisão de usar modelo único.

**Tasks (se executar):**
- [ ] Implementar estratégias de ensemble:
  - [ ] Voting (maioria simples)
  - [ ] Weighted voting (pesos otimizados via grid search)
  - [ ] Stacking (meta-learner: LR, RF, XGBoost)
  - [ ] Conditional (léxico filtra → ML decide casos ambíguos)
- [ ] Otimizar hiperparâmetros
- [ ] Avaliar trade-offs:
  - [ ] Ganho de accuracy
  - [ ] Latência (2-3 modelos vs 1)
  - [ ] Complexidade operacional
  - [ ] Custo
- [ ] **DECISÃO:** Ensemble vale a pena?
  - SE ganho > 5% E latência aceitável → Deploy ensemble
  - SE ganho < 5% OU latência alta → Usar melhor modelo único
- [ ] Documentar Fase 4 (fase4_ensemble.md)

**Critério de sucesso:**
- Ensemble testado (se executado)
- **Decisão fundamentada: ensemble vs modelo único**
- Trade-offs documentados (não importa qual escolha)

**Arquivos esperados:**
- `src/ensemble_analyzer.py` - Implementação ensemble
- `notebooks/ensemble_optimization.ipynb` - Otimização
- `results/final_comparison.csv` - Comparação final
- `docs/06_issue6_sentiment/fase4_ensemble.md` - Documentação

---

### Fase 5: Análises Avançadas (Semana 6)

**Objetivo:** Explorar análises específicas do domínio governamental

**Tasks:**
- [ ] **Sentimento por Entidade:**
  - [ ] Integrar com NER (Issue anterior)
  - [ ] Análise: "Ministro elogia campanha" → sentimento sobre "campanha"
- [ ] **Evolução Temporal:**
  - [ ] Sentimento sobre tópicos ao longo do tempo
  - [ ] Detecção de mudanças de tom
- [ ] **Sentimento por Órgão:**
  - [ ] Comparação entre agências governamentais
  - [ ] Identificação de padrões
- [ ] **Dashboard e Visualizações:**
  - [ ] Timeline de sentimento
  - [ ] Heatmap por órgão/tema
  - [ ] Word clouds por polaridade
- [ ] Documentar casos de uso
- [ ] Documentar Fase 5 (fase5_analises_avancadas.md)

**Critério de sucesso:**
- Análises específicas implementadas
- Casos de uso documentados com exemplos
- Visualizações geradas

**Arquivos esperados:**
- `src/entity_sentiment.py` - Sentimento por entidade
- `src/temporal_analysis.py` - Análise temporal
- `notebooks/advanced_analysis.ipynb` - Análises
- `results/visualizations/` - Gráficos e dashboards
- `docs/06_issue6_sentiment/fase5_analises_avancadas.md` - Documentação

---

### Fase 6: Integração e Produção (Semana 7)

**Objetivo:** Integrar modelo escolhido ao pipeline de enriquecimento

**Tasks:**
- [ ] Integração com `llm_client.py`:
  - [ ] Validar modelo atual (Nova 2 Lite)
  - [ ] Considerar fallback/ensemble se necessário
- [ ] Testes em produção:
  - [ ] Batch processing (1000 notícias)
  - [ ] Performance e latência
- [ ] Backfill de dados históricos (se aplicável)
- [ ] Monitoring e alertas:
  - [ ] Distribuição de sentimentos
  - [ ] Drift detection
- [ ] Documentar integração
- [ ] Documentar Fase 6 (fase6_integracao_producao.md)

**Critério de sucesso:**
- Modelo integrado ao pipeline
- Testes em produção validados
- Monitoring configurado

**Arquivos esperados:**
- `src/news_enrichment/sentiment_module.py` - Módulo produção
- `scripts/backfill_sentiment.py` - Script backfill
- `docs/06_issue6_sentiment/fase6_integracao_producao.md` - Documentação

---

### Fase 7: Documentação Final (Semana 8)

**Objetivo:** Produzir deliverables finais da issue

**Tasks:**
- [ ] **Relatório Técnico** (30-40 páginas):
  - [ ] Introdução e motivação
  - [ ] Revisão de literatura
  - [ ] Metodologia completa
  - [ ] Resultados de todas as fases
  - [ ] Análise comparativa
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

**Critério de sucesso:**
- Todos deliverables completos
- Revisão aprovada
- Issue fechada

**Arquivos esperados:**
- `docs/06_issue6_sentiment/relatorio_tecnico_completo.md` - Relatório (30-40 pág)
- `docs/06_issue6_sentiment/apresentacao_executiva.pdf` - Slides (15-18)
- `docs/06_issue6_sentiment/README_issue6.md` - README atualizado

---

## 📂 Estrutura de Arquivos

```
source/
├── sentiment-analysis/                 # ← NOVO (Issue #6)
│   ├── README.md                       # Overview e quick start
│   │
│   ├── notebooks/
│   │   ├── lexicon_baseline.ipynb     # Fase 1
│   │   ├── bert_experiments.ipynb     # Fase 2
│   │   ├── llm_experiments.ipynb      # Fase 3
│   │   ├── ensemble_optimization.ipynb # Fase 4
│   │   └── advanced_analysis.ipynb    # Fase 5
│   │
│   ├── scripts/
│   │   ├── annotate_dataset.py        # UI para anotação manual
│   │   ├── test_lexicon.py            # Teste baseline léxico
│   │   ├── test_bert.py               # Teste modelos BERT
│   │   ├── test_llm.py                # Teste LLMs
│   │   ├── test_ensemble.py           # Teste ensemble
│   │   └── analyze_results.py         # Análise de resultados
│   │
│   ├── src/
│   │   ├── __init__.py
│   │   ├── lexicon_analyzer.py        # Análise léxica
│   │   ├── bert_analyzer.py           # Análise BERT
│   │   ├── llm_analyzer.py            # Análise LLM
│   │   ├── ensemble_analyzer.py       # Ensemble methods
│   │   ├── entity_sentiment.py        # Sentimento por entidade
│   │   ├── temporal_analysis.py       # Análise temporal
│   │   └── utils/
│   │       ├── preprocessing.py       # Preprocessamento texto
│   │       ├── metrics.py             # Métricas de avaliação
│   │       └── visualization.py       # Gráficos e dashboards
│   │
│   ├── data/
│   │   ├── lexicons/
│   │   │   ├── oplexicon.txt          # OpLexicon v3.0
│   │   │   ├── sentilexpt.txt         # SentiLex-PT
│   │   │   └── custom_gov.txt         # Léxico customizado
│   │   ├── datasets/
│   │   │   ├── test_50.csv            # Dataset inicial (Fase 1)
│   │   │   ├── train_200.csv          # Dataset treino (Fase 2)
│   │   │   ├── validation_50.csv      # Validação
│   │   │   └── test_50_final.csv      # Teste final
│   │   └── annotations/
│   │       ├── annotation_guide.md    # Guia de anotação
│   │       └── inter_annotator.csv    # Cálculo de concordância
│   │
│   ├── prompts/
│   │   └── sentiment_prompts.yaml     # Biblioteca de prompts
│   │
│   ├── results/
│   │   ├── metrics/
│   │   │   ├── lexicon_results.csv
│   │   │   ├── bert_results.csv
│   │   │   ├── llm_results.csv
│   │   │   ├── ensemble_results.csv
│   │   │   └── final_comparison.csv
│   │   ├── predictions/
│   │   │   └── model_predictions.csv  # Predições por modelo
│   │   └── visualizations/
│   │       ├── confusion_matrices/
│   │       ├── temporal_plots/
│   │       └── dashboards/
│   │
│   └── models/
│       ├── bert_finetuned/            # BERT fine-tuned (se aplicável)
│       └── ensemble_weights.pkl       # Pesos otimizados ensemble
│
└── docs/06_issue6_sentiment/
    ├── README_issue6.md                # Este arquivo
    ├── fase1_lexicos.md                # Documentação Fase 1
    ├── fase2_bert.md                   # Documentação Fase 2
    ├── fase3_llm.md                    # Documentação Fase 3
    ├── fase4_ensemble.md               # Documentação Fase 4
    ├── fase5_analises_avancadas.md     # Documentação Fase 5
    ├── fase6_integracao_producao.md    # Documentação Fase 6
    ├── relatorio_tecnico_completo.md   # Relatório final (30-40 pág)
    └── apresentacao_executiva.pdf      # Slides (15-18)
```

---

## 📈 Timeline Estimado

| Fase | Duração | Período Estimado | Status |
|------|---------|------------------|--------|
| **Fase 1:** Baseline Léxico | 1 semana | 30 Jun - 06 Jul | 🔄 Em andamento |
| **Fase 2:** Modelos BERT | 2 semanas | 07 Jul - 20 Jul | 📋 Planejada |
| **Fase 3:** LLM-based Analysis | 1 semana | 21 Jul - 27 Jul | 📋 Planejada |
| **Fase 4:** Ensemble Methods | 1 semana | 28 Jul - 03 Ago | 📋 Planejada |
| **Fase 5:** Análises Avançadas | 1 semana | 04 Ago - 10 Ago | 📋 Planejada |
| **Fase 6:** Integração Produção | 1 semana | 11 Ago - 17 Ago | 📋 Planejada |
| **Fase 7:** Documentação Final | 1 semana | 18 Ago - 24 Ago | 📋 Planejada |

**Total:** ~8 semanas (~2 meses)

---

## 🎓 Aprendizados Esperados

Ao final desta issue, esperamos documentar:

1. **Desafios de Sentimento em Textos Formais:**
   - Diferenças vs redes sociais/reviews
   - Importância de contexto governamental
   - Prevalência de neutralidade

2. **Comparação Léxico vs BERT vs LLM:**
   - Trade-offs: accuracy, latência, custo, interpretabilidade
   - Quando usar cada abordagem
   - Complementaridade entre métodos

3. **Ensemble Methods:**
   - Ganhos de combinar approaches
   - Estratégias de fusão eficazes
   - Calibration e confidence

4. **Aplicações Específicas:**
   - Sentimento por entidade
   - Análise temporal de tópicos
   - Benchmark de comunicação entre órgãos

5. **Fine-tuning BERT:**
   - Viabilidade para domínio governamental
   - Transfer learning PT-BR
   - Trade-off custo/benefício

6. **Prompt Engineering:**
   - Zero-shot vs few-shot para SA
   - Chain-of-thought para explicabilidade
   - Calibration de LLMs

---

## ⚠️ Riscos Identificados

| Risco | Probabilidade | Impacto | Mitigação | Status |
|-------|---------------|---------|-----------|--------|
| Dataset majoritariamente neutro (>70%) | Alta | Médio | Sobreamostragem pos/neg, métricas balanceadas | 📋 Monitorar |
| Baixa concordância inter-anotador (<0.6) | Média | Alto | Guia detalhado, reuniões de calibração | 📋 Monitorar |
| Léxicos PT-BR insuficientes | Média | Médio | Criar léxico customizado gov.br | 📋 Monitorar |
| Fine-tuning BERT sem GPU adequada | Baixa | Médio | Usar EC2 L4 (já disponível) | ✅ Mitigado |
| LLM custo alto para produção | Baixa | Médio | Ensemble com BERT como fallback | 📋 Monitorar |
| Modelo não supera baseline léxico | Baixa | Alto | BERT/LLM historicamente superiores | 📋 Monitorar |

---

## 📚 Referências Completas

### Papers Fundamentais

1. Liu, B. (2012) - Sentiment Analysis and Opinion Mining - Morgan & Claypool
2. Medhat et al. (2014) - Sentiment analysis algorithms and applications survey - https://doi.org/10.5121/aint.2014.4102
3. Souza & Vieira (2012) - Sentiment Analysis on Twitter Data for Portuguese Language
4. Freitas & Vieira (2015) - Ontology based feature level opinion mining for Portuguese reviews
5. Brum & Nunes (2018) - Building a Sentiment Corpus of Tweets in Brazilian Portuguese
6. Devlin et al. (2019) - BERT - https://arxiv.org/abs/1810.04805
7. Souza et al. (2020) - BERTimbau - https://arxiv.org/abs/2010.05595
8. Wang et al. (2023) - Is ChatGPT a Good Sentiment Analyzer? - https://arxiv.org/abs/2304.04339
9. Zhu et al. (2023) - Can ChatGPT Reproduce Human-Generated Labels?
10. Hamborg et al. (2019) - Automated identification of media bias in news articles

### Recursos e Datasets

- **OpLexicon v3.0:** http://ontolp.inf.pucrs.br/Recursos/downloads-OpLexicon.php
- **SentiLex-PT:** http://b2find.eudat.eu/dataset/b1bf8c0a-9c64-5a37-a1df-f0f34c3d20bc
- **TweetSentBR:** https://bitbucket.org/HBrum/tweetsentbr/src/master/
- **BERTimbau Models:** https://huggingface.co/neuralmind/bert-base-portuguese-cased

### Frameworks e Tools

- **Transformers (Hugging Face):** https://huggingface.co/docs/transformers/
- **NLTK:** https://www.nltk.org/
- **spaCy:** https://spacy.io/
- **Scikit-learn:** https://scikit-learn.org/
- **AWS Bedrock:** https://aws.amazon.com/bedrock/

---

## 🔗 Links Úteis

**Issue GitHub:**
- [Issue #6](https://github.com/destaquesgovbr/data-science/issues/6)

**Documentação relacionada:**
- [Issue #1 - Embeddings](../01_issue1_embeddings/relatorio_final_issue1.md)
- [Issue #3 - Classificação](../03_issue3_classification/relatorio_tecnico_completo.md)
- [Issue #4 - Sumarização](../04_issue4_summarization/relatorio_final_issue4.md)

---

## 📊 Status de Progresso

### Geral: 🔄 5% (Fase 1 Iniciada)

| Fase | Status | Progresso | Data Início | Data Fim |
|------|--------|-----------|-------------|----------|
| Fase 1: Baseline Léxico | 🔄 Em andamento | 10% | 30 Jun 2026 | - |
| Fase 2: Modelos BERT | 🔴 Planejada | 0% | - | - |
| Fase 3: LLM-based | 🔴 Planejada | 0% | - | - |
| Fase 4: Ensemble | 🔴 Planejada | 0% | - | - |
| Fase 5: Análises Avançadas | 🔴 Planejada | 0% | - | - |
| Fase 6: Integração Produção | 🔴 Planejada | 0% | - | - |
| Fase 7: Documentação Final | 🔴 Planejada | 0% | - | - |

**Legenda:**
- 🔴 Não iniciada / Planejada
- 🔄 Em progresso
- 🟢 Concluída

**Fase atual:** Fase 1 - Explorando léxicos PT-BR disponíveis  
**Próxima milestone:** Baseline léxico implementado e dataset inicial anotado

---

## 👥 Time e Responsabilidades

**Líder Técnico:** Luis Felipe de Moraes  
**Implementação:** Luis Felipe de Moraes  
**Ontologia/Léxico:** Consulta ao responsável de ontologia  
**Revisão:** A definir

---

## 📝 Histórico de Atualizações

| Data | Versão | Mudanças | Autor |
|------|--------|----------|-------|
| 2026-06-30 | 1.0 | Criação do documento de planejamento completo | Claude Code |

---

## 🚀 Próximos Passos Imediatos

**Fase 1 - Tasks em andamento:**

1. [x] Estrutura de diretórios criada
2. [x] README principal escrito
3. [ ] **Pesquisar e baixar léxicos PT-BR** ← PRÓXIMO
4. [ ] Implementar baseline léxico
5. [ ] Criar dataset inicial (50 notícias)
6. [ ] Avaliar baseline
7. [ ] Documentar Fase 1

---

**Documento preparado por:** Claude Code  
**Última atualização:** 2026-06-30  
**Próxima revisão:** Após conclusão da Fase 1

---

_Este é um documento vivo que será atualizado conforme o progresso da Issue #6._
