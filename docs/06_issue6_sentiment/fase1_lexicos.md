# Fase 1 - Baseline Léxico: Análise de Sentimento

**Issue #6 - Análise de Sentimento em Notícias Governamentais**  
**Data:** 30 de Junho de 2026  
**Status:** 🔄 Em andamento

---

## 📋 Sumário Executivo

Primeira fase da implementação do sistema de análise de sentimento. Nesta fase realizamos extensa pesquisa sobre recursos léxicos disponíveis para português brasileiro e implementamos baseline léxico usando OpLexicon v3.0.

**Resultado esperado:** Baseline léxico funcional com accuracy > 50% em dataset inicial de 50 notícias governamentais anotadas manualmente.

---

## 🎯 Objetivos da Fase 1

### A. Baseline Léxico
1. ✅ Pesquisar léxicos de sentimento PT-BR disponíveis
2. ✅ Revisar literatura acadêmica relevante
3. [ ] **Escolher léxico primário** (OpLexicon OU SentiLex)
4. [ ] Implementar baseline léxico com léxico escolhido
5. [ ] Criar dataset inicial de teste (50 notícias anotadas)
6. [ ] Avaliar performance do baseline
7. [ ] Análise de erros e identificação de limitações

### B. LLM Quick Test (NOVO - Teste Estratégico)
1. [ ] Testar Nova 2 Lite zero-shot no mesmo dataset de 50 notícias
2. [ ] Testar Claude Haiku 4.5 zero-shot
3. [ ] Comparar accuracy: Léxico vs LLM
4. [ ] **Decisão estratégica:** Priorizar BERT (Fase 2) ou LLM (Fase 3)?

---

## 🔍 Pesquisa: Recursos Léxicos PT-BR

### 1. OpLexicon v3.0 ⭐ **ESCOLHIDO COMO PRIMÁRIO**

**Fonte Oficial:**
- GitHub: https://github.com/marlovss/OpLexicon
- Arquivo: `lexico_v3.0.txt` (formato texto) ou `OpLexicon.csv` (CSV)

**Tamanho e Estrutura:**
- **32.191 entradas totais**
- **24.475 adjetivos** (76%)
- **6.889 verbos** (21%)
- **471 hashtags** (1,5%)
- **66 emoticons** (0,2%)

**Formato dos Dados:**
```csv
term,type,polarity,source
abafada,adj,-1,A
abençoada,adj,1,A
aberta,adj,0,A
```

**Colunas:**
- **term**: palavra em português, emoticon ou hashtag
- **type**: classe gramatical (adj, vb, emot, htag)
- **polarity**: -1 (negativo), 0 (neutro), 1 (positivo)
- **source**: M (revisado manualmente) ou A (automático)

**Pontos Fortes:**
- Construído especificamente para **Português Brasileiro (PT-BR)**
- Versão 3.0 inclui **revisão linguística manual** pelas linguistas Aline Vanin e Denise Hogetop
- Inclui formas flexionadas (masculino/feminino, singular/plural)
- Escala simples de 3 pontos (-1, 0, 1) facilita integração
- Amplamente usado em pesquisa acadêmica brasileira

**Limitações Identificadas:**
- Cobertura limitada de termos governamentais/políticos (encontrados apenas: "antipolítica", "brasileiro/a")
- Predominância de adjetivos - pode perder substantivos específicos do domínio
- Viés de redes sociais (inclui hashtags e emoticons)
- Sem scores de intensidade (apenas -1/0/1, sem gradações)

**Como Acessar:**
```python
import pandas as pd
url = "https://raw.githubusercontent.com/marlovss/OpLexicon/master/lexico_v3.0.txt"
oplexicon = pd.read_csv(url, names=['term', 'type', 'polarity', 'source'])
```

**Citações:**
1. Souza, M., Vieira, R. (2012) - 10th International Conference on Portuguese Language Processing
2. Souza, M. et al. (2011) - 8th Brazilian Symposium in Information and Human Language Technology

**Decisão preliminar:** Forte candidato a léxico primário devido à qualidade, disponibilidade e foco em PT-BR.

**⚠️ Decisão final:** Pendente após análise comparativa com SentiLex.

---

### 2. SentiLex-PT

**Fonte Oficial:**
- Repositório Linguateca (acesso direto não disponível)
- Implementações GitHub:
  - https://github.com/lilianoftheveil/polaridade_sentilex
  - https://github.com/lucashfernandes91/Analise-de-sentimento-aplicado-a-frases--Python-e-Sentilex-

**Variante de Idioma:**
- Originalmente construído para **Português Europeu (PT-PT)**
- Desenvolvido na Universidade do Minho (Portugal) com Prof. José João Almeida
- Pode ser adaptado para PT-BR mas pode ter incompatibilidades de vocabulário

**Formato dos Dados:**
- Arquivo: `SentiLex-lem-PT02.txt`
- Contém lemas (formas base) com valores de polaridade
- Estrutura: lemas pareados com polaridades de sentimento

**Uso Comparativo:**
- Filtrado por categorias gramaticais: ADJ, V (verbos), N (substantivos)
- Usado junto com OpLexicon em estudos comparativos

**Pontos Fortes:**
- Inclui substantivos (diferente do OpLexicon que é principalmente adjetivos)
- Academicamente validado
- Usado em análise de discurso político (veja paper sobre eleições brasileiras)

**Limitações:**
- **Incompatibilidade PT-PT vs PT-BR** - diferenças de vocabulário e uso
- Menos comum em pesquisa brasileira comparado ao OpLexicon
- Mais difícil de acessar (sem repositório público centralizado)

**Relevância para Texto Formal:**
- Usado com sucesso em análise de discurso político (estudo eleições brasileiras 2018)
- Melhor cobertura de substantivos pode ajudar com terminologia governamental

**Decisão preliminar:** Considerar como alternativa ao OpLexicon se:
- Cobertura de substantivos for crítica
- Textos formais/políticos se beneficiarem da origem PT-PT acadêmica

**⚠️ Decisão final:** Pendente após comparação direta com OpLexicon.

---

### 3. LIWC-PT (Linguistic Inquiry and Word Count - Português)

**Versões:**
- **LIWC 2007pt** - Primeira versão para português brasileiro
- **LIWC 2015pt** - Versão atualizada (2019)
- **AffectPT-br** (2018) - Léxico afetivo baseado no LIWC 2015

**Características:**
- **Recurso comercial/proprietário** (não disponível gratuitamente)
- Construído especificamente para português brasileiro
- Fornece classificação categorial além de sentimento
- Inclui categorias psicológicas e linguísticas

**Papers Relevantes:**
1. "An evaluation of the Brazilian Portuguese LIWC dictionary for sentiment analysis" (Balage Filho & Pardo, 2013) - 163 citações
2. "AffectPT-br: an Affective Lexicon based on LIWC 2015" (Carvalho & Santos, 2018) - 23 citações
3. "Evaluating the Brazilian Portuguese version of the 2015 LIWC Lexicon" (Carvalho et al., 2019)

**Pontos Fortes:**
- Análise multi-dimensional (não apenas positivo/negativo)
- Categorias psicológicas úteis para entender mensagens governamentais
- Bem validado para PT-BR

**Limitações:**
- **Não disponível gratuitamente** - requer compra de licença
- Integração mais complexa que léxicos simples de polaridade
- Pode ser excessivo para análise básica de sentimento

**Decisão:** Não utilizar na Fase 1 devido a custo e complexidade. Considerar apenas se orçamento permitir e análise multi-dimensional for necessária.

---

### 4. NRC Emotion Lexicon (Adaptação Portuguesa)

**Características:**
- Léxico de emoções multilíngue com tradução para português
- **8 emoções**: raiva, alegria, medo, confiança, tristeza, surpresa, antecipação, nojo
- **2 sentimentos**: positivo, negativo

**Pontos Fortes:**
- Classificação emocional refinada
- Gratuito e código aberto
- Usado em workflows de análise de sentimento em R

**Limitações:**
- Qualidade da tradução para PT-BR não extensivamente validada
- Pode não capturar expressões idiomáticas brasileiras
- Abordagem agnóstica de linguagem pode perder nuances culturais

**Decisão:** Possível complemento ao OpLexicon para detecção de emoções além de polaridade, mas não prioritário para Fase 1.

---

### 5. Léxicos Específicos de Domínio (Custom)

**Exemplos Encontrados:**
- Léxico de termos pejorativos (custom, de TCC sobre transfobia)
- Léxico de sentimento financeiro (adaptação de domínio BERTaú)

**Recomendação para Domínio Governamental:**
Considerar construir **léxico suplementar governamental** com termos como:
- reforma (reform)
- corrupção (corruption)
- transparência (transparency)
- investimento (investment)
- crise (crisis)
- medida (measure)
- avanço (advance)
- retrocesso (setback)
- aprovação (approval)
- rejeição (rejection)

**Decisão:** Implementar após validação do baseline com OpLexicon. Prioridade média.

---

## 📚 Revisão de Literatura

### A. Sentiment Analysis em Português - Papers Fundamentais

#### 1. "A survey of sentiment analysis in the Portuguese language"
- **Autores:** DA Pereira
- **Ano:** 2021
- **Publicação:** Artificial Intelligence Review (Springer)
- **Citações:** 123
- **Contribuição:** Survey abrangente de trabalhos em análise de sentimento para português. Revisa OpLexicon, LIWC-PT e outros recursos.
- **Relevância:** Alta - fornece visão geral de métodos e recursos

#### 2. "Exploring resources for sentiment analysis in Portuguese language"
- **Autores:** LA De Freitas, R Vieira
- **Ano:** 2015
- **Publicação:** Brazilian Conference on Intelligent Systems (IEEE)
- **Citações:** 33
- **Contribuição:** Avaliou **quatro léxicos portugueses de sentimento**: OpLexicon, SentiLex, LIWC-PT e Onto.PT synsets para tarefas de análise de sentimento.
- **Relevância:** Alta - comparação direta dos léxicos que estamos considerando

#### 3. "Building a Sentiment Corpus of Tweets in Brazilian Portuguese" (TweetSentBR)
- **Autores:** Henrico Bertini Brum, Maria das Graças Volpe Nunes
- **Ano:** 2017 (LREC 2018)
- **arXiv:** 1712.08917
- **Dataset:** 15.000 tweets anotados (3 classes: positivo/neutro/negativo)
- **Resultados:** 80,99% F1 (binário), 59,85% F1 (3 classes)
- **Relevância:** Média - domínio redes sociais, mas fornece benchmark PT-BR

---

### B. Modelos Transformer para Português

#### 4. "DeBERTinha: A Multistep Approach to Adapt DebertaV3 XSmall for Brazilian Portuguese"
- **Autores:** Israel Campiotti et al.
- **Ano:** 2023
- **arXiv:** 2309.16844
- **Contribuição:** Adaptou DebertaV3 XSmall (40M parâmetros) para PT-BR usando vocabulário de 50K tokens em português. **Superou BERTimbau-Large** apesar de ser muito menor.
- **Treinamento:** Datasets Carolina e BrWac
- **Relevância:** Alta - demonstra adaptação eficiente de transformer para PT-BR

#### 5. "Embedding generation for text classification of Brazilian Portuguese user reviews"
- **Autores:** Frederico Dias Souza, João Baptista de Oliveira e Souza Filho
- **Ano:** 2022
- **Publicação:** Neural Computing and Applications
- **arXiv:** 2212.00587
- **Achado Principal:** **Modelos de Linguagem Transformers fine-tuned** consistentemente alcançaram melhor performance em todos os datasets, superiores a Bag-of-Words, CNN, LSTM.
- **Relevância:** Alta - recomenda transformers sobre abordagens léxicas para PT-BR

#### 6. "Mono vs Multilingual Transformer-based Models"
- **Autores:** Diego de Vargas Feijo, Viviane Pereira Moreira
- **Ano:** 2020
- **arXiv:** 2007.09757
- **Achado Principal:** **Modelos monolíngues e multilíngues têm performance similar** - vantagem de treinar modelos específicos para português é pequena.
- **Relevância:** Alta - sugere que modelos multilíngues (mBERT) podem ser suficientes

---

### C. Análise de Texto Formal/Governamental

#### 7. "Detecting Group Beliefs Related to 2018's Brazilian Elections in Tweets" ⭐
- **Autores:** Brenda Salenave Santana, Aline Aver Vanin
- **Ano:** 2020
- **arXiv:** 2006.00490
- **Contribuição:** Combinou **modelagem de tópicos com SentiLex-PT** para analisar discurso político durante eleições brasileiras. Encontrou "uso exacerbado de discursos apaixonados" no Twitter político.
- **Relevância:** **MUITO ALTA** - diretamente relevante para texto governamental/político em PT-BR

#### 8. "A Weakly Supervised Dataset of Fine-Grained Emotions in Portuguese"
- **Autores:** Diogo Cortiz et al.
- **Ano:** 2021
- **arXiv:** 2108.07638
- **Abordagem:** Supervisão fraca baseada em léxico para reconhecimento de emoções, validado com fine-tuning BERT (F1=0,64)
- **Relevância:** Média - demonstra abordagem híbrida léxico+BERT

---

### D. Abordagens Léxico vs ML

#### 9. "A New Statistical Approach for Comparing Algorithms For Lexicon Based Sentiment Analysis"
- **Autores:** Mateus Machado, Evandro Ruiz, Kuruvilla Joseph Abraham
- **Ano:** 2019
- **arXiv:** 1906.08717
- **Contribuição:** Desenvolve métodos estatísticos para comparar algoritmos de sentimento **sem anotação humana** usando testes de homogeneidade marginal e modelos log-lineares.
- **Relevância:** Alta - aborda desafios de avaliação quando ground truth é escasso

#### 10. "Lexicon-based sentiment analysis: Comparative evaluation of six sentiment lexicons"
- **Autores:** CSG Khoo, SB Johnkhan
- **Ano:** 2018
- **Citações:** 383
- **Contribuição:** Estudo comparativo avaliando performance de diferentes léxicos de sentimento.
- **Relevância:** Média - metodologia geral aplicável ao português

---

### E. Análise de Sentimento Baseada em Aspectos

#### 11. "Deep Learning Brasil at ABSAPT 2022: Portuguese Transformer Ensemble Approaches"
- **Autores:** Juliana Resplande Santanna Gomes et al.
- **Ano:** 2023
- **arXiv:** 2311.05051
- **Contribuição:** **Resultados estado-da-arte** em Análise de Sentimento Baseada em Aspectos (ABSA) para português usando ensembles de transformers.
- **Tarefas:** Extração de Termos de Aspecto (ATE) + Extração de Orientação de Sentimento (SOE)
- **Relevância:** Alta - útil se analisarmos sentimento em relação a entidades/políticas governamentais específicas

---

## 🏗️ Arquitetura da Implementação - Fase 1

### Decisões Técnicas

**Léxico Primário:** OpLexicon v3.0
- 32.191 entradas, revisão linguística manual
- Cobertura adequada para baseline
- Fácil integração e disponibilidade

**Abordagem de Scoring:**

```python
# Algoritmo baseline (versão 1.0)
def calculate_sentiment_score(text: str, lexicon: dict) -> tuple:
    """
    Calcula score de sentimento usando abordagem léxica simples.
    
    Args:
        text: texto para análise
        lexicon: dicionário {term: polarity}
    
    Returns:
        (score, label, details)
        score: -1.0 a 1.0 (normalizado)
        label: "positive" | "neutral" | "negative"
        details: dict com contagens
    """
    # 1. Preprocessamento
    tokens = preprocess_text(text)  # lowercase, remove pontuação
    
    # 2. Contagem de polaridades
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    
    for token in tokens:
        if token in lexicon:
            polarity = lexicon[token]
            if polarity == 1:
                positive_count += 1
            elif polarity == -1:
                negative_count += 1
            else:
                neutral_count += 1
    
    # 3. Cálculo de score agregado
    total_sentiment_terms = positive_count + negative_count
    
    if total_sentiment_terms == 0:
        score = 0.0
        label = "neutral"
    else:
        # Score normalizado: (pos - neg) / total
        score = (positive_count - negative_count) / total_sentiment_terms
        
        # Classificação por threshold
        if score > 0.1:
            label = "positive"
        elif score < -0.1:
            label = "negative"
        else:
            label = "neutral"
    
    details = {
        "positive_terms": positive_count,
        "negative_terms": negative_count,
        "neutral_terms": neutral_count,
        "total_sentiment_terms": total_sentiment_terms,
        "total_tokens": len(tokens)
    }
    
    return score, label, details
```

**Justificativa:**
- Abordagem simples para baseline
- Normalizção por total de termos de sentimento (não por tamanho total do texto)
- Thresholds conservadores (0.1/-0.1) para evitar false positives
- Captura detalhes para análise posterior

**Limitações Conhecidas (a serem abordadas em versões futuras):**
1. Não trata negação ("não é bom" → ainda marca como positivo)
2. Não trata intensificadores ("muito bom" conta igual a "bom")
3. Bag-of-words (ignora ordem e contexto)
4. Termos governamentais específicos podem não estar no léxico

---

## 📊 Implementação

### Arquivos Criados

1. **`src/lexicon_analyzer.py`** - Implementação do analisador léxico
2. **`scripts/download_oplexicon.py`** - Script para baixar OpLexicon
3. **`scripts/test_lexicon.py`** - Script de testes
4. **`data/lexicons/oplexicon.txt`** - Léxico OpLexicon v3.0

### Próximas Tasks

#### Decisão de Léxico
- [ ] **Escolher léxico primário:**
  - [ ] Opção A: OpLexicon v3.0 (32k termos, PT-BR, bem validado)
  - [ ] Opção B: SentiLex-PT (substantivos, PT-PT adaptado, político)
  - [ ] Critério: Cobertura em textos governamentais + facilidade integração
- [ ] Implementar analisador com léxico escolhido

#### Dataset Anotado
- [ ] Criar dataset inicial de 50 notícias para anotação manual
- [ ] Implementar script de anotação (interface simples)
- [ ] Anotar manualmente 50 notícias (ground truth)
  - [ ] **Considerar:** LLM como co-anotador (Claude Sonnet 4) + validação manual 20%
  - [ ] Calcular Kappa inter-anotador (target > 0.65)

#### Baseline Léxico
- [ ] Executar baseline em dataset anotado
- [ ] Calcular métricas: accuracy, F1-macro, confusion matrix
- [ ] Análise de erros qualitativa

#### LLM Quick Test (NOVO)
- [ ] Testar Nova 2 Lite zero-shot (prompt simples: "Classifique o sentimento: positivo/neutro/negativo")
- [ ] Testar Claude Haiku 4.5 zero-shot (mesmo prompt)
- [ ] Comparar: Léxico vs Nova vs Haiku
- [ ] **Decisão crítica:**
  - SE melhor LLM > 70% → Priorizar Fase 3 (prompt optimization)
  - SE melhor LLM < 70% → Continuar Fase 2 (BERT)

#### Documentação
- [ ] Documentar escolha de léxico e justificativa
- [ ] Documentar resultados baseline léxico
- [ ] Documentar resultados LLM quick test
- [ ] Documentar decisão estratégica (Fase 2 vs Fase 3)

---

## 🎯 Critérios de Sucesso

**Fase 1 será considerada completa quando:**

1. ✅ Pesquisa de léxicos PT-BR documentada
2. ✅ Literatura acadêmica revisada
3. [ ] Baseline léxico implementado e funcional
4. [ ] Dataset de 50 notícias anotado com concordância inter-anotador > 0.65
5. [ ] Métricas calculadas: accuracy > 50%, F1-macro documentado
6. [ ] Análise de erros completa identificando padrões de falha
7. [ ] Documentação de fase finalizada

---

## 📈 Resultados (a serem preenchidos)

### Métricas Quantitativas

```
# A ser preenchido após execução do baseline

Accuracy: TBD
F1-macro: TBD
Precision (pos): TBD
Recall (pos): TBD
Precision (neu): TBD
Recall (neu): TBD
Precision (neg): TBD
Recall (neg): TBD

Confusion Matrix:
           pred_pos  pred_neu  pred_neg
true_pos      TBD       TBD       TBD
true_neu      TBD       TBD       TBD
true_neg      TBD       TBD       TBD
```

### Análise Qualitativa

```
# A ser preenchido após análise de erros

Padrões de Erro:
1. TBD
2. TBD
3. TBD

Limitações Identificadas:
1. TBD
2. TBD
3. TBD

Oportunidades de Melhoria:
1. TBD
2. TBD
3. TBD
```

---

## 🔄 Próximos Passos

**Imediato (esta semana):**
1. Implementar código do baseline léxico
2. Criar e anotar dataset inicial (50 notícias)
3. Executar baseline e calcular métricas
4. Análise de erros

**Fase 2 (próximas 2 semanas):**
1. Avaliar modelos BERT pré-treinados
2. Comparar performance léxico vs BERT
3. Considerar fine-tuning se necessário

---

## 📚 Referências Citadas

1. Souza, M., Vieira, R. (2012). Sentiment Analysis on Twitter Data for Portuguese Language. 10th International Conference on Portuguese Language Processing.

2. Pereira, D. A. (2021). A survey of sentiment analysis in the Portuguese language. Artificial Intelligence Review, 54(2), 1087-1115.

3. De Freitas, L. A., Vieira, R. (2015). Exploring resources for sentiment analysis in Portuguese language. Brazilian Conference on Intelligent Systems (IEEE).

4. Santana, B. S., Vanin, A. A. (2020). Detecting Group Beliefs Related to 2018's Brazilian Elections in Tweets. arXiv:2006.00490.

5. Souza, F. D., Souza Filho, J. B. O. (2022). Embedding generation for text classification of Brazilian Portuguese user reviews. Neural Computing and Applications. arXiv:2212.00587.

6. Machado, M., Ruiz, E., Abraham, K. J. (2019). A New Statistical Approach for Comparing Algorithms For Lexicon Based Sentiment Analysis. arXiv:1906.08717.

---

**Documento preparado por:** Claude Code  
**Data:** 2026-06-30  
**Última atualização:** 2026-06-30  
**Próxima revisão:** Após implementação do baseline

---

_Documentação viva - será atualizada conforme progresso da Fase 1._
