# Análise de Sentimento - Issue #6

**Sistema de análise de sentimento para notícias governamentais brasileiras**

---

## 🎯 Visão Geral

Este módulo implementa análise de sentimento em três níveis:
1. **Léxico** - Baseline com OpLexicon/SentiLex
2. **BERT** - Transformers PT-BR (condicional)
3. **LLM** - Nova/Claude/Llama via Bedrock

**Desafio único:** Textos governamentais são majoritariamente neutros e formais, diferente de redes sociais/reviews.

---

## 📂 Estrutura de Diretórios

```
sentiment-analysis/
├── README.md                    # Este arquivo
├── data/
│   ├── lexicons/                # Léxicos de sentimento
│   │   ├── oplexicon_v3.txt     # OpLexicon v3.0 (32k termos PT-BR)
│   │   └── sentilex.txt         # SentiLex-PT (se usado)
│   ├── datasets/                # Datasets anotados
│   │   ├── annotated_50.csv     # Dataset inicial (Fase 1)
│   │   ├── annotated_200.csv    # Dataset expandido (Fase 2, se necessário)
│   │   └── annotation_guide.md  # Guia de anotação manual
│   └── samples/                 # Amostras de teste
├── src/
│   ├── lexicon_analyzer.py      # Analisador léxico
│   ├── bert_analyzer.py         # Analisador BERT (Fase 2)
│   ├── llm_analyzer.py          # Analisador LLM (Fase 3)
│   ├── ensemble_analyzer.py     # Ensemble (Fase 4, condicional)
│   └── utils/
│       ├── preprocessing.py     # Preprocessamento de texto
│       ├── metrics.py           # Métricas de avaliação
│       └── visualization.py     # Gráficos e análises
├── scripts/
│   ├── download_oplexicon.py    # Download OpLexicon v3.0
│   ├── test_lexicon_baseline.py # Teste baseline léxico
│   ├── test_bert.py             # Teste modelos BERT
│   ├── test_llm.py              # Teste LLMs
│   └── analyze_results.py       # Análise comparativa
├── notebooks/
│   ├── lexicon_baseline.ipynb   # Experimentos Fase 1
│   ├── bert_experiments.ipynb   # Experimentos Fase 2
│   ├── llm_experiments.ipynb    # Experimentos Fase 3
│   └── advanced_analysis.ipynb  # Análises avançadas Fase 5
├── results/
│   ├── metrics/                 # Resultados quantitativos (CSV)
│   ├── predictions/             # Predições por modelo
│   └── visualizations/          # Gráficos e dashboards
└── models/                      # Modelos treinados (se fine-tuning)
    └── bert_finetuned/
```

---

## 🚀 Quick Start

### 1. Setup Inicial

```bash
cd source/sentiment-analysis

# Instalar dependências (se necessário)
pip install pandas numpy scikit-learn nltk spacy

# Download léxico OpLexicon v3.0
python scripts/download_oplexicon.py
```

### 2. Testar Baseline Léxico

```python
from src.lexicon_analyzer import LexiconAnalyzer

# Carregar analisador
analyzer = LexiconAnalyzer(lexicon_path="data/lexicons/oplexicon_v3.txt")

# Analisar texto
text = "O governo anuncia investimento histórico em educação."
score, label, details = analyzer.analyze(text)

print(f"Score: {score:.2f}")
print(f"Label: {label}")
print(f"Detalhes: {details}")
```

### 3. Executar Testes em Dataset

```bash
# Testar baseline léxico em dataset anotado
python scripts/test_lexicon_baseline.py \
  --dataset data/datasets/annotated_50.csv \
  --lexicon data/lexicons/oplexicon_v3.txt \
  --output results/metrics/lexicon_results.csv
```

---

## 📊 Datasets

### Dataset Inicial (Fase 1)
- **Arquivo:** `data/datasets/annotated_50.csv`
- **Tamanho:** 50 notícias governamentais
- **Anotação:** Manual (3 classes: pos/neu/neg)
- **Formato:**
  ```csv
  id,title,content,sentiment,confidence,annotator
  1,"Título...","Conteúdo...",positive,high,lfelipe
  ```

### Guidelines de Anotação
Ver `data/datasets/annotation_guide.md` para:
- Definições de positivo/neutro/negativo
- Casos ambíguos e como resolver
- Exemplos anotados

---

## 🔬 Metodologia

### Fase 1: Baseline Léxico (atual)

**Algoritmo:**
1. Preprocessamento: lowercase, tokenização, remoção pontuação
2. Contagem de termos positivos/negativos/neutros no léxico
3. Score normalizado: `(pos - neg) / total_sentiment_terms`
4. Classificação por threshold: score > 0.1 → positivo, < -0.1 → negativo, else neutro

**Léxicos considerados:**
- **OpLexicon v3.0** - 32.191 termos PT-BR (adjetivos, verbos, emoticons)
- **SentiLex-PT** - Léxico português europeu adaptável

**Limitações conhecidas:**
- Não trata negação ("não é bom" → ainda positivo)
- Não trata intensificadores ("muito bom" = "bom")
- Bag-of-words (ignora contexto)

### Fase 2: BERT (condicional)

**Modelos a testar:**
- BERTimbau sentiment (`lm-finetune/bertimbau-sentiment`)
- XLM-RoBERTa sentiment (`cardiffnlp/twitter-xlm-roberta-base-sentiment`)

**Decisão fine-tuning:**
- SE zero-shot < 70% → Fine-tune com dataset expandido
- SE zero-shot > 70% → Usar pré-treinado

### Fase 3: LLM

**Modelos via AWS Bedrock:**
- Amazon Nova 2 Lite (custo-efetivo)
- Claude Haiku 4.5 (rápido)
- Llama 3.3 70B (alternativa)

**Estratégias de prompt:**
- Zero-shot (baseline)
- Few-shot (3-5 exemplos)
- Chain-of-thought (raciocínio explícito)

### Fase 4: Ensemble (condicional)

**Executar SE:**
- Melhor modelo < 75% accuracy, E
- Ensemble ganha > 5%

**Estratégias:**
- Voting (maioria)
- Weighted voting
- Stacking (meta-learner)
- Conditional (léxico filtra → ML decide)

---

## 📈 Métricas de Avaliação

### Métricas Primárias
- **Accuracy** - Percentual correto (3 classes)
- **F1-Score Macro** - Média harmônica por classe
- **Confusion Matrix** - Padrões de erro

### Métricas Secundárias
- **F1 por Classe** - Pos/Neu/Neg isoladamente
- **Confidence Calibration** - Correlação confidence vs accuracy
- **Latência** - Tempo médio por classificação
- **Custo** - Custo por 10k classificações

### Targets
- Accuracy > 75% (final)
- F1-macro > 0.70
- Latência: < 2s (LLM), < 100ms (BERT), < 10ms (léxico)
- Kappa inter-anotador > 0.65

---

## 🧪 Testes e Reprodutibilidade

### Executar Testes

```bash
# Baseline léxico
python scripts/test_lexicon_baseline.py

# BERT (Fase 2, se executada)
python scripts/test_bert.py --model neuralmind/bert-base-portuguese-cased

# LLM (Fase 3)
python scripts/test_llm.py --model nova-2-lite --prompt zero-shot

# Análise comparativa
python scripts/analyze_results.py --compare lexicon bert llm
```

### Notebooks Interativos

```bash
jupyter notebook notebooks/lexicon_baseline.ipynb
```

---

## 🔗 Documentação Completa

- **Documentação principal:** [`docs/06_issue6_sentiment/README_issue6.md`](../../docs/06_issue6_sentiment/README_issue6.md)
- **Guia de Fases:** [`docs/06_issue6_sentiment/GUIA_FASES.md`](../../docs/06_issue6_sentiment/GUIA_FASES.md)
- **Fase 1 - Léxicos:** [`docs/06_issue6_sentiment/fase1_lexicos.md`](../../docs/06_issue6_sentiment/fase1_lexicos.md)

---

## 📚 Referências Principais

1. **OpLexicon v3.0** - Souza, M., Vieira, R. (2012) - https://github.com/marlovss/OpLexicon
2. **BERTimbau** - Souza et al. (2020) - https://arxiv.org/abs/2010.05595
3. **Sentiment Analysis Survey (PT)** - Pereira, D.A. (2021) - Artificial Intelligence Review
4. **TweetSentBR Dataset** - Brum, H., Nunes, M.G.V. (2018) - 15k tweets anotados

---

## 👥 Time

**Líder Técnico:** Luis Felipe de Moraes  
**Implementação:** Luis Felipe de Moraes

---

## 📝 Status Atual

**Fase 1:** 🔄 Em andamento (30%)
- [x] Estrutura criada
- [x] Pesquisa léxicos completa
- [ ] Escolher léxico primário
- [ ] Implementar baseline
- [ ] Anotar 50 notícias
- [ ] Teste LLM quick

**Próximos passos:** Escolher léxico (OpLexicon vs SentiLex), implementar baseline, anotar dataset inicial.

---

**Última atualização:** 2026-07-02
