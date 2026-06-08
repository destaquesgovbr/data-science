# Issue #4: Estratégias de Sumarização de Notícias Governamentais

**Data de início:** 2026-05-07  
**Responsável:** Luis Felipe de Moraes  
**Status:** 🚀 Planejamento Concluído

---

## 📋 Visão Geral

### Objetivo
Explorar e comparar técnicas de sumarização (extractive, abstractive, hybrid) aplicadas a notícias governamentais brasileiras, avaliando trade-offs entre fidelidade, fluência e custo.

### Hipótese Central
**Técnicas hybrid** (extractive + abstractive) oferecem melhor balanço entre fidelidade e fluência para sumarização de notícias governamentais, superando tanto extractive puro (baixa fluência) quanto abstractive puro (risco de hallucination).

### Deliverables (Requisitos da Issue)
1. ✅ **Notebook** - POCs de todas técnicas implementadas
2. ✅ **Documento técnico** - 40-50 páginas de análise completa
3. ✅ **Apresentação** - 18-20 slides executivos

---

## 🎯 Técnicas a Implementar

### Grupo A: Extractive Summarization (3 técnicas)

| # | Técnica | Descrição | Biblioteca | Vantagem | Desvantagem |
|---|---------|-----------|------------|----------|-------------|
| 1 | **TextRank** | Graph-based, PageRank sobre sentenças | `sumy` | Rápido, sem treinamento | Sentenças desconexas |
| 2 | **LexRank** | Similar ao TextRank com TF-IDF | `sumy` | Mais robusto | Ainda extractive |
| 3 | **BERT Extractive** | Embeddings semânticos | `summarizer` | Contexto semântico | Requer GPU |

### Grupo B: Abstractive Summarization (3 técnicas)

| # | Técnica | Modelo | Vantagem | Desvantagem |
|---|---------|--------|----------|-------------|
| 4 | **mT5** | `google/mt5-base` | Gera texto novo, coeso | Pode inventar fatos |
| 5 | **BART** | `facebook/bart-large-cnn` | Estado da arte (EN) | Ruim em PT-BR |
| 6 | **LLM (Claude)** | Claude Haiku via Bedrock | Excelente qualidade | Custo alto |

### Grupo C: Hybrid Approaches (1 técnica)

| # | Técnica | Pipeline | Vantagem | Trade-off |
|---|---------|----------|----------|-----------|
| 7 | **Extract-then-Abstract** | Extractive → Abstractive | Reduz custo, mantém fidelidade | Complexidade |

**Total:** 7 técnicas a explorar

---

## 📊 Métricas de Avaliação

### Automáticas
- **ROUGE** (ROUGE-1, ROUGE-2, ROUGE-L) - Overlap léxico
- **BERTScore** - Similaridade semântica via embeddings

### Avaliação Humana (Escala 1-5)
- **Fidelidade** - Informação correta? Sem invenções?
- **Coerência** - Texto faz sentido?
- **Fluência** - Bem escrito?
- **Relevância** - Informações importantes incluídas?

**Protocolo:** 3 avaliadores independentes, 50 resumos por técnica, Fleiss' Kappa

---

## 🗓️ Fases de Execução

### Fase 1: Setup e Dataset ⏳ (1-2 dias)
**Objetivo:** Preparar ambiente e dados

**Tasks:**
- [ ] Criar estrutura de diretórios (`source/summarization/`)
- [ ] Selecionar dataset (50 notícias da Issue #3)
- [ ] Criar referências (ground truth) - manual ou Claude
- [ ] Instalar dependências Python

**Critério de sucesso:** 50 notícias com resumos de referência prontos

---

### Fase 2: Implementação Extractive ⏳ (2-3 dias)
**Objetivo:** Implementar TextRank, LexRank, BERT Extractive

**Tasks:**
- [ ] TextRank (3, 5, 10 sentenças)
- [ ] LexRank (comparar vs TextRank)
- [ ] BERT Extractive (ratios: 0.2, 0.3, 0.4)
- [ ] Avaliar ROUGE e BERTScore

**Critério de sucesso:** ROUGE-L > 0.4 para pelo menos 1 técnica

---

### Fase 3: Implementação Abstractive ⏳ (3-4 dias)
**Objetivo:** Implementar mT5, BART (opcional), Claude

**Tasks:**
- [ ] mT5 base/small (fine-tuning opcional)
- [ ] BART (opcional se tempo permitir)
- [ ] Claude Haiku via Bedrock (reutilizar Issue #3)
- [ ] Avaliar hallucination rate

**Critério de sucesso:** 
- mT5 com ROUGE-L > 0.35
- Claude com ROUGE-L > 0.5

---

### Fase 4: Implementação Hybrid ⏳ (2 dias)
**Objetivo:** Pipeline Extract-then-Abstract

**Tasks:**
- [ ] TextRank → mT5
- [ ] TextRank → Claude
- [ ] BERT Extractive → Claude
- [ ] Testar ratios: 30%, 50%, 70%
- [ ] Análise de custo

**Critério de sucesso:** Hybrid > Abstractive em fidelidade

---

### Fase 5: Avaliação Automática ⏳ (1-2 dias)
**Objetivo:** Calcular ROUGE e BERTScore para todas técnicas

**Tasks:**
- [ ] Calcular ROUGE-1, ROUGE-2, ROUGE-L
- [ ] Calcular BERTScore (P, R, F1)
- [ ] Análise estatística (média, desvio, teste t)
- [ ] Gráficos comparativos

**Critério de sucesso:** Pelo menos 1 técnica com ROUGE-L > 0.45

---

### Fase 6: Avaliação Humana ⏳ (3-4 dias)
**Objetivo:** Coletar avaliações de qualidade

**Tasks:**
- [ ] Protocolo de avaliação (formulário)
- [ ] Recrutamento de 3 avaliadores
- [ ] Coleta de dados (50 resumos)
- [ ] Análise de agreement (Fleiss' Kappa)
- [ ] Consolidação de resultados

**Critério de sucesso:** 
- Kappa > 0.6 (agreement substancial)
- Pelo menos 1 técnica com média > 4.0

---

### Fase 7: Documentação ⏳ (3-4 dias)
**Objetivo:** Produzir deliverables finais

**Tasks:**
- [ ] Análise comparativa completa
- [ ] Documento técnico (40-50 páginas)
- [ ] Apresentação (18-20 slides)
- [ ] Notebook final (POC limpo)

**Critério de sucesso:** Todos deliverables completos e revisados

---

## 📂 Estrutura de Arquivos

```
source/
├── summarization/                      # ← NOVO (Issue #4)
│   ├── summarizers.py                 # Classes de cada técnica
│   ├── evaluator.py                   # ROUGE, BERTScore
│   ├── notebooks/
│   │   └── summarization_poc.ipynb    # POC completo
│   ├── scripts/
│   │   ├── evaluate_extractive.py
│   │   ├── evaluate_abstractive.py
│   │   ├── evaluate_hybrid.py
│   │   └── human_evaluation.py
│   ├── data/
│   │   ├── news_sample.csv            # 50 notícias
│   │   └── reference_summaries.csv    # Ground truth
│   ├── results/
│   │   ├── metrics/
│   │   │   ├── rouge_scores.csv
│   │   │   └── bertscore_results.csv
│   │   ├── human_eval/
│   │   │   └── ratings.csv
│   │   └── visualizations/
│   └── docs/
│       ├── TECHNICAL_REPORT_ISSUE4.md  # 40-50 páginas
│       ├── PRESENTATION_ISSUE4.pdf     # 18-20 slides
│       └── EXECUTION_PLAN.md           # Este plano
│
└── embeddings/                         # Issue #3 (manter)
    └── ...
```

---

## 🚀 Como Executar (Quando Pronto)

### 1. Avaliar Extractive

```bash
cd source/summarization
python scripts/evaluate_extractive.py --dataset data/news_sample.csv --output results/metrics/
```

### 2. Avaliar Abstractive

```bash
python scripts/evaluate_abstractive.py --model mt5 --dataset data/news_sample.csv
python scripts/evaluate_abstractive.py --model claude --dataset data/news_sample.csv
```

### 3. Avaliar Hybrid

```bash
python scripts/evaluate_hybrid.py --extractive textrank --abstractive claude --ratio 0.5
```

### 4. Ver Resultados

```bash
# Notebook interativo
jupyter notebook notebooks/summarization_poc.ipynb

# Gráficos
python scripts/visualize_results.py
```

---

## 📈 Timeline Estimado

| Fase | Duração | Período Estimado |
|------|---------|------------------|
| **Fase 1:** Setup e Dataset | 1-2 dias | 07-08 Mai |
| **Fase 2:** Extractive | 2-3 dias | 09-11 Mai |
| **Fase 3:** Abstractive | 3-4 dias | 12-15 Mai |
| **Fase 4:** Hybrid | 2 dias | 16-17 Mai |
| **Fase 5:** Avaliação Automática | 1-2 dias | 18-19 Mai |
| **Fase 6:** Avaliação Humana | 3-4 dias | 20-23 Mai |
| **Fase 7:** Documentação | 3-4 dias | 24-27 Mai |

**Total:** ~18-22 dias úteis (~3-4 semanas)

---

## 🎓 Aprendizados Esperados

Ao final desta issue, esperamos documentar:

1. **Trade-offs fundamentais:**
   - Extractive: rápido, barato, mas baixa fluência
   - Abstractive: fluente, mas caro e risco de hallucination
   - Hybrid: balanço ideal?

2. **Quando usar cada técnica:**
   - Produção de alto volume → Extractive (TextRank)
   - Qualidade crítica → Abstractive (Claude)
   - Balanço custo-benefício → Hybrid

3. **Métricas automáticas vs humanas:**
   - ROUGE correlaciona com qualidade percebida?
   - BERTScore é melhor proxy?
   - Avaliação humana é indispensável?

4. **Adequação ao domínio governamental:**
   - Notícias gov.br têm padrões específicos?
   - Técnicas precisam de fine-tuning?

---

## ⚠️ Riscos Identificados

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Dataset pequeno (50 notícias) | Alta | Médio | Expandir para 100 se métricas não significativas |
| Avaliadores inconsistentes | Média | Alto | Treinamento rigoroso, calibração |
| mT5 com qualidade ruim | Média | Médio | Claude como fallback |
| Tempo de execução apertado | Média | Médio | BART opcional, priorizar core |

---

## 📚 Referências Principais

**Papers:**
- Mihalcea & Tarau (2004) - TextRank
- Lin (2004) - ROUGE
- Zhang et al. (2020) - BERTScore
- Raffel et al. (2020) - T5 e mT5

**Bibliotecas:**
- `sumy` - TextRank, LexRank
- `transformers` - mT5, BART
- `bert-score` - BERTScore
- `rouge-score` - ROUGE

**Datasets PT-BR:**
- TeMário (corpus acadêmico)
- CSTNews (corpus jornalístico)
- Nosso: notícias gov.br (Issue #3)

---

## 🔗 Links Úteis

**Issue GitHub:**
- [Issue #4](https://github.com/destaquesgovbr/data-science/issues/4)

**Documentação relacionada:**
- [Plano de Execução Detalhado](docs/ISSUE4_EXECUTION_PLAN.md)
- [Issue #3 - Classificação](README_ISSUE3.md) (dataset base)

**Ferramentas:**
- [Hugging Face Transformers](https://huggingface.co/docs/transformers)
- [ROUGE Score](https://github.com/google-research/google-research/tree/master/rouge)
- [BERTScore](https://github.com/Tiiiger/bert_score)

---

## 📊 Status de Progresso

### Geral: 🟡 0% (Planejamento Concluído)

| Fase | Status | Progresso | Data Início | Data Fim |
|------|--------|-----------|-------------|----------|
| Fase 1: Setup | 🔴 Não iniciada | 0% | - | - |
| Fase 2: Extractive | 🔴 Não iniciada | 0% | - | - |
| Fase 3: Abstractive | 🔴 Não iniciada | 0% | - | - |
| Fase 4: Hybrid | 🔴 Não iniciada | 0% | - | - |
| Fase 5: Avaliação Auto | 🔴 Não iniciada | 0% | - | - |
| Fase 6: Avaliação Humana | 🔴 Não iniciada | 0% | - | - |
| Fase 7: Documentação | 🔴 Não iniciada | 0% | - | - |

**Legenda:**
- 🔴 Não iniciada
- 🟡 Em progresso
- 🟢 Concluída

---

## 👥 Time e Responsabilidades

**Líder Técnico:** Luis Felipe de Moraes  
**Implementação:** Luis Felipe de Moraes  
**Avaliadores (quando necessário):** A definir (Fase 6)  
**Revisão:** A definir

---

## 📝 Histórico de Atualizações

| Data | Versão | Mudanças | Autor |
|------|--------|----------|-------|
| 2026-05-07 | 1.0 | Criação do documento de planejamento | Claude Code |
| - | - | - | - |

---

## 🚀 Próximos Passos Imediatos

**Para iniciar a Issue #4:**

1. ✅ Plano aprovado
2. [ ] Criar branch `issue4` a partir da `main` limpa
3. [ ] Criar estrutura de diretórios
4. [ ] Selecionar 50 notícias do dataset da Issue #3
5. [ ] Instalar dependências Python
6. [ ] Implementar TextRank (primeira técnica piloto)

**Comando para começar:**
```bash
git checkout main
git pull origin main
git checkout -b issue4
mkdir -p source/summarization/{notebooks,scripts,data,results,docs}
```

---

**Documento preparado por:** Claude Code  
**Última atualização:** 2026-05-07  
**Próxima revisão:** Após Fase 1 (Setup)

---

_Este é um documento vivo que será atualizado conforme o progresso da Issue #4._
