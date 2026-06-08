# Issue #4 - Plano de Execução
## Estratégias de Sumarização de Notícias Governamentais

**Data de início:** 2026-05-07  
**Responsável:** Luis Felipe de Moraes  
**Branch:** `issue4`  
**Status:** 🚀 Planejamento

---

## 📋 Contexto da Issue

### Objetivo Principal
Explorar técnicas de sumarização aplicadas a notícias governamentais brasileiras, comparando métodos tradicionais (TextRank, LexRank) com abordagens modernas baseadas em LLMs.

### Hipótese Central
Técnicas **hybrid** (extractive + abstractive) oferecem melhor balanço entre fidelidade e fluência, superando tanto extractive puro (baixa fluência) quanto abstractive puro (risco de hallucination).

### Deliverables (SLA)
1. ✅ **Notebook** - POCs de todas técnicas
2. ✅ **Documento** - 40-50 páginas de análise
3. ✅ **Apresentação** - 18-20 slides

---

## 🎯 Técnicas a Implementar (7 abordagens)

### Grupo A: Extractive (3 técnicas)
1. ✅ **TextRank** - Graph-based, PageRank sobre sentenças
2. ✅ **LexRank** - Similar ao TextRank com TF-IDF
3. ✅ **BERT Extractive** - Contexto semântico via embeddings

### Grupo B: Abstractive (3 técnicas)
4. ✅ **mT5** - Multilingual T5 (Google)
5. ✅ **BART** - Facebook (limitado em PT-BR)
6. ✅ **LLM (Claude/GPT)** - Estado da arte

### Grupo C: Hybrid (1 abordagem)
7. ✅ **Extract-then-Abstract** - Pipeline em 2 etapas

---

## 📊 Métricas de Avaliação

### Automáticas
- ✅ **ROUGE** (ROUGE-1, ROUGE-2, ROUGE-L) - overlap léxico
- ✅ **BERTScore** - similaridade semântica

### Humana
- ✅ **Fidelidade** - Informação correta? Sem invenções?
- ✅ **Coerência** - Texto faz sentido?
- ✅ **Fluência** - Bem escrito?
- ✅ **Relevância** - Informações importantes incluídas?

**Protocolo:** 3 avaliadores, 50 resumos/técnica, Fleiss' Kappa

---

## 🗓️ Plano de Execução Detalhado

### Fase 1: Setup e Dataset (1-2 dias)

**Tasks:**
1. [ ] Criar estrutura de diretórios
   ```
   source/summarization/
   ├── notebooks/
   │   └── summarization_poc.ipynb
   ├── scripts/
   │   ├── evaluate_extractive.py
   │   ├── evaluate_abstractive.py
   │   └── evaluate_hybrid.py
   ├── data/
   │   ├── news_sample.csv
   │   └── reference_summaries.csv
   ├── results/
   │   └── metrics/
   └── docs/
       └── TECHNICAL_REPORT_ISSUE4.md
   ```

2. [ ] Selecionar dataset
   - **Opção A:** Usar notícias da Issue #3 (200 notícias já classificadas)
   - **Opção B:** Buscar dataset público PT-BR (TeMário, CSTNews)
   - **Decisão:** Começar com 50 notícias da Issue #3 + anotação manual

3. [ ] Criar referências (ground truth)
   - Anotar 50 notícias manualmente com resumos ideais
   - **OU** usar Claude Haiku para gerar baseline de referência

4. [ ] Instalar dependências
   ```bash
   pip install sumy transformers bert-score rouge-score
   pip install sentence-transformers nltk spacy
   python -m spacy download pt_core_news_lg
   ```

---

### Fase 2: Implementação Extractive (2-3 dias)

**Tasks:**

1. [ ] **TextRank**
   - Implementar usando `sumy`
   - Testar com 3, 5, 10 sentenças
   - Avaliar ROUGE e BERTScore

2. [ ] **LexRank**
   - Implementar usando `sumy`
   - Comparar vs TextRank
   - Documentar diferenças

3. [ ] **BERT Extractive**
   - Testar modelo: `neuralmind/bert-base-portuguese-cased`
   - Explorar ratios: 0.2, 0.3, 0.4 do texto original
   - Avaliar qualidade semântica

**Critério de sucesso:** ROUGE-L > 0.4 para pelo menos 1 técnica

---

### Fase 3: Implementação Abstractive (3-4 dias)

**Tasks:**

1. [ ] **mT5 (Multilingual T5)**
   - Modelo base: `google/mt5-base` ou `google/mt5-small`
   - Fine-tuning opcional (se dataset grande)
   - Avaliar hallucination rate

2. [ ] **BART** (opcional, se tempo permitir)
   - Modelo: `facebook/bart-large-cnn`
   - Tradução PT→EN→PT pode ser necessária
   - Comparar qualidade vs mT5

3. [ ] **LLM (Claude Haiku)**
   - Usar API Bedrock (já configurada da Issue #3)
   - Prompt: "Resuma em 2-3 frases..."
   - Benchmark de qualidade (baseline de ouro)

**Critério de sucesso:** 
- mT5 com ROUGE-L > 0.35
- Claude com ROUGE-L > 0.5 (esperado)

---

### Fase 4: Implementação Hybrid (2 dias)

**Tasks:**

1. [ ] **Pipeline Extract-then-Abstract**
   ```python
   def hybrid_summarize(text):
       # Step 1: Extractive (reduz para 50%)
       important_sentences = textrank(text, ratio=0.5)
       
       # Step 2: Abstractive (reescreve com LLM)
       summary = claude_summarize(important_sentences)
       
       return summary
   ```

2. [ ] **Variações a testar:**
   - TextRank → mT5
   - TextRank → Claude
   - BERT Extractive → Claude
   - Diferentes ratios de compressão (30%, 50%, 70%)

3. [ ] **Análise de custo:**
   - Extractive: grátis, ~1-2s
   - Abstractive (LLM): ~$0.001/notícia, ~2-3s
   - Hybrid: reduz custo 50% vs abstractive puro

**Critério de sucesso:** Hybrid > Abstractive em fidelidade, similar em fluência

---

### Fase 5: Avaliação Automática (1-2 dias)

**Tasks:**

1. [ ] **Calcular ROUGE para todas técnicas**
   ```python
   from rouge import Rouge
   rouge = Rouge()
   
   for technique in techniques:
       scores = rouge.get_scores(generated, reference)
       # Armazenar ROUGE-1, ROUGE-2, ROUGE-L
   ```

2. [ ] **Calcular BERTScore**
   ```python
   from bert_score import score
   P, R, F1 = score(generated_list, reference_list, lang="pt")
   ```

3. [ ] **Análise estatística**
   - Comparar médias e desvios padrão
   - Teste t para significância estatística
   - Ranking por métrica

4. [ ] **Gráficos comparativos**
   - Bar plot: ROUGE-L por técnica
   - Scatter: ROUGE vs BERTScore
   - Box plot: distribuição de scores

**Critério de sucesso:** Pelo menos 1 técnica com ROUGE-L > 0.45

---

### Fase 6: Avaliação Humana (3-4 dias)

**Tasks:**

1. [ ] **Protocolo de avaliação**
   - Definir escala Likert (1-5)
   - Criar formulário Google Forms
   - Selecionar 50 resumos (7 técnicas × 7 notícias + overlap)

2. [ ] **Recrutamento de avaliadores**
   - Mínimo: 3 avaliadores independentes
   - Perfil: familiaridade com notícias governamentais
   - Treinamento: calibração com 5 exemplos

3. [ ] **Coleta de dados**
   - Randomizar ordem de apresentação
   - Ocultar qual técnica gerou qual resumo
   - Calcular tempo médio de avaliação

4. [ ] **Análise de agreement**
   - Calcular Fleiss' Kappa (agreement entre avaliadores)
   - Se Kappa < 0.6, recalibrar e reavaliar

5. [ ] **Consolidação de resultados**
   - Média por técnica em cada dimensão
   - Identificar padrões (extractive = baixa fluência?)

**Critério de sucesso:** 
- Kappa > 0.6 (agreement substancial)
- Pelo menos 1 técnica com média > 4.0 em todas dimensões

---

### Fase 7: Análise e Documentação (3-4 dias)

**Tasks:**

1. [ ] **Análise comparativa completa**
   - Trade-offs: fidelidade vs fluência
   - Custo vs qualidade
   - Latência por técnica
   - Quando usar cada abordagem

2. [ ] **Documento técnico (40-50 páginas)**
   
   **Estrutura:**
   ```markdown
   1. Introdução (3-4 páginas)
      - Contexto: notícias governamentais
      - Problema: leitores precisam de resumos
      - Objetivo da pesquisa
   
   2. Revisão da Literatura (6-8 páginas)
      - Extractive: TextRank, LexRank, BERT
      - Abstractive: T5, BART, LLMs
      - Hybrid approaches
      - Métricas: ROUGE, BERTScore
   
   3. Metodologia (8-10 páginas)
      - Dataset (seleção, anotação)
      - Implementação de cada técnica
      - Protocolo de avaliação humana
      - Análise estatística
   
   4. Resultados (12-15 páginas)
      - Métricas automáticas (tabelas, gráficos)
      - Avaliação humana (scores, agreement)
      - Análise qualitativa (exemplos)
      - Comparação custo-benefício
   
   5. Discussão (6-8 páginas)
      - Interpretação dos resultados
      - Trade-offs identificados
      - Limitações do estudo
      - Recomendações práticas
   
   6. Conclusões (2-3 páginas)
      - Síntese dos achados
      - Contribuições
      - Trabalhos futuros
   
   7. Referências (2-3 páginas)
   
   8. Anexos
      - Código-fonte
      - Exemplos de resumos
      - Protocolo de avaliação
   ```

3. [ ] **Apresentação (18-20 slides)**
   
   **Estrutura:**
   ```
   Slide 1: Título
   Slide 2-3: Contexto e Motivação
   Slide 4: Objetivo e Hipótese
   Slide 5-7: Técnicas Exploradas (3 grupos)
   Slide 8-9: Metodologia
   Slide 10-14: Resultados (gráficos, exemplos)
   Slide 15-16: Trade-offs e Recomendações
   Slide 17-18: Conclusões
   Slide 19: Trabalhos Futuros
   Slide 20: Q&A
   ```

4. [ ] **Notebook final (POC)**
   - Código limpo e documentado
   - Exemplos executáveis
   - Visualizações inline
   - Exportar para HTML

**Critério de sucesso:** Documentação completa, clara e reproduzível

---

## 📦 Estrutura de Código Proposta

```python
# source/summarization/summarizers.py

class BaseSummarizer:
    def summarize(self, text: str, **kwargs) -> str:
        raise NotImplementedError

class TextRankSummarizer(BaseSummarizer):
    def __init__(self, language="portuguese"):
        self.language = language
    
    def summarize(self, text: str, sentences_count=3) -> str:
        # Implementação TextRank
        pass

class LexRankSummarizer(BaseSummarizer):
    # Similar

class BERTExtractiveSummarizer(BaseSummarizer):
    def __init__(self, model_name="neuralmind/bert-base-portuguese-cased"):
        self.model = load_model(model_name)
    
    def summarize(self, text: str, ratio=0.3) -> str:
        # Implementação BERT extractive
        pass

class MT5Summarizer(BaseSummarizer):
    def __init__(self, model_name="google/mt5-base"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    
    def summarize(self, text: str, max_length=150) -> str:
        # Implementação mT5
        pass

class ClaudeSummarizer(BaseSummarizer):
    def __init__(self, model_id="anthropic.claude-haiku-20250306-v1:0"):
        self.model_id = model_id
        self.bedrock = boto3.client('bedrock-runtime')
    
    def summarize(self, text: str, max_sentences=3) -> str:
        prompt = f"Resuma em {max_sentences} frases:\n\n{text}"
        # Chamar Bedrock
        pass

class HybridSummarizer(BaseSummarizer):
    def __init__(self, extractive_model, abstractive_model):
        self.extractive = extractive_model
        self.abstractive = abstractive_model
    
    def summarize(self, text: str, extract_ratio=0.5) -> str:
        # Step 1: Extractive
        extracted = self.extractive.summarize(text, ratio=extract_ratio)
        
        # Step 2: Abstractive
        summary = self.abstractive.summarize(extracted)
        
        return summary
```

---

## 🎯 Critérios de Sucesso da Issue

### Técnicos
- [ ] Todas 7 técnicas implementadas e funcionais
- [ ] ROUGE-L > 0.4 para pelo menos 2 técnicas
- [ ] Avaliação humana com Kappa > 0.6
- [ ] Hybrid approach supera extractive puro em fluência

### Documentação
- [ ] Notebook reproduzível com todos POCs
- [ ] Documento técnico 40-50 páginas completo
- [ ] Apresentação 18-20 slides profissional

### Aprendizados
- [ ] Trade-offs claramente documentados
- [ ] Recomendações práticas para produção
- [ ] Contribuição para conhecimento interno

---

## ⚠️ Riscos e Mitigações

### Risco 1: Dataset de referência pequeno
**Impacto:** Métricas podem não ser estatisticamente significativas  
**Mitigação:** Começar com 50, expandir para 100 se necessário

### Risco 2: Avaliadores inconsistentes
**Impacto:** Kappa baixo, resultados não confiáveis  
**Mitigação:** Treinamento rigoroso, calibração com exemplos, re-avaliação se necessário

### Risco 3: mT5 com qualidade ruim
**Impacto:** Abstractive puro não compete  
**Mitigação:** Ter Claude como fallback (já funcional da Issue #3)

### Risco 4: Tempo de execução
**Impacto:** 2-3 semanas pode ser apertado  
**Mitigação:** Priorizar técnicas core (TextRank, mT5, Claude, Hybrid), BART opcional

---

## 📅 Timeline Estimado

| Fase | Duração | Data Início | Data Fim |
|------|---------|-------------|----------|
| Setup e Dataset | 1-2 dias | 2026-05-07 | 2026-05-08 |
| Extractive | 2-3 dias | 2026-05-09 | 2026-05-11 |
| Abstractive | 3-4 dias | 2026-05-12 | 2026-05-15 |
| Hybrid | 2 dias | 2026-05-16 | 2026-05-17 |
| Avaliação Automática | 1-2 dias | 2026-05-18 | 2026-05-19 |
| Avaliação Humana | 3-4 dias | 2026-05-20 | 2026-05-23 |
| Documentação | 3-4 dias | 2026-05-24 | 2026-05-27 |

**Total:** ~18-22 dias (~3-4 semanas)

---

## 🚀 Próximos Passos Imediatos

1. ✅ Revisar e aprovar este plano
2. [ ] Criar estrutura de diretórios
3. [ ] Selecionar e preparar dataset (50 notícias)
4. [ ] Instalar dependências Python
5. [ ] Implementar TextRank (primeira técnica, validar pipeline)

---

**Preparado por:** Claude Code  
**Data:** 2026-05-07  
**Próxima revisão:** Após Fase 1
