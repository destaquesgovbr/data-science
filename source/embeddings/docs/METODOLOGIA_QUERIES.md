# Metodologia de Criação das 85 Queries de Teste

**Data:** 2026-04-02  
**Responsável:** Luis Felipe de Moraes  
**Projeto:** Issue #1 - Comparativo de Modelos de Embedding PT-BR

---

## Sumário Executivo

Este documento descreve a **metodologia e justificativa** para as decisões de design na criação das 85 queries de teste usadas para avaliar modelos de embedding para notícias governamentais brasileiras.

**Objetivo:** Garantir que os testes reflitam **cenários reais de uso** e avaliem capacidades críticas dos modelos.

---

## Princípios Norteadores

### 1. **Naturalidade e Realismo**

#### **Por que é importante?**

Queries artificiais ou academicamente construídas **não representam como usuários reais buscam informação**. Se testarmos com queries perfeitas (ex: "Ministério da Educação anuncia distribuição do PNLD para escolas públicas do ensino básico em 2026"), os resultados não refletirão a performance real em produção.

#### **Implicações para Embeddings**

Modelos de embedding treinados em texto formal podem ter **dificuldade com linguagem coloquial**:
- Usuário real: `"tilápia açude ema"`
- Query artificial: `"piscicultura tilápia reservatório"`

Embeddings precisam capturar:
- **Variações lexicais** (açude ≈ reservatório ≈ barragem)
- **Contexto implícito** (tilápia → piscicultura, não fauna selvagem)
- **Omissões naturais** (usuários raramente digitam artigos, preposições completas)

#### **Como validamos**

Queries criadas simulam comportamento observado em:
- Estudos de comportamento de busca (Jansen et al., 2000; Spink et al., 2001)
- Perfis de usuários identificados:
  - **Público geral:** Linguagem simples, objetiva
  - **Profissionais:** Mix de coloquial + jargão

#### **Exemplos no Dataset**

**Natural/Realista:**
```
"tilápia açude ema"              (como cidadão buscaria)
"microcrédito pescadores"        (direto ao ponto)
"conflito agrário paraná acordo" (contexto + localização)
```

**Artificial/Formal (evitado):**
```
"programa de fomento à piscicultura em reservatórios hídricos"
"política de microcrédito para pescadores artesanais"
"resolução de conflito fundiário em área rural do estado do Paraná"
```

#### **Referências**

- **Jansen et al. (2000):** Usuários reais usam média de 2.35 palavras, não frases completas
- **Rose & Levinson (2004):** "Understanding User Goals in Web Search" - Queries são **goal-oriented**, não descritivas

---

### 2. **Contexto Geográfico**

#### **Por que é importante?**

Notícias governamentais brasileiras têm **forte componente regional**:
- Programas federais com implementação estadual/municipal
- Eventos localizados (enchentes, secas, inaugurações)
- Políticas públicas com impacto geográfico específico

Sem contexto geográfico nos testes, **não validamos** se embeddings conseguem:
- Distinguir "Rio de Janeiro" (cidade) vs "Rio de Janeiro" (estado)
- Associar "Nordeste" com estados específicos (CE, PE, BA, etc.)
- Relacionar "Vale do Jequitinhonha" com Minas Gerais
- Capturar relevância local (usuário do PA busca por "Belém")

#### **Implicações para Embeddings**

Modelos multilíngues (treinados em 100+ línguas) podem **perder nuances geográficas brasileiras**:
- Não conhecer "Zona da Mata" (região de MG)
- Confundir "Corumbá" (MS) com outras cidades
- Não associar "BR-020" com Bahia
- Perder relação "Calçoene" (AP) com contexto amazônico

Modelos PT-BR específicos têm **vantagem potencial** aqui, pois treinados em corpus brasileiro rico em geografia local.

#### **Como validamos**

17 das 85 queries (20%) incluem contexto geográfico explícito:
- **Cidades:** Belém, Salvador, Corumbá, Foz do Iguaçu
- **Estados:** Paraná, Bahia, Rio Grande do Sul, Pará, Minas Gerais
- **Regiões:** Nordeste, Vale do Jequitinhonha, Zona da Mata
- **Rodovias:** BR-020/BA (código geográfico)

#### **Exemplos no Dataset**

**Com contexto geográfico:**
```
"conflito agrário paraná acordo"              (estado)
"demandas população Vale do Jequitinhonha"    (região de MG)
"implantação segmento br 020 ba"              (rodovia federal em BA)
"seminário mudanças climáticas Pará"          (estado)
"PAC Saúde entregas bahia"                    (programa federal + estado)
"construção barragem Rio grande do sul"       (estado)
"estupro coletivo rio de janeiro"             (cidade/estado)
"chuva zona da mata"                          (região de MG)
```

**Sem contexto (quando relevante):**
```
"seminário mudanças climáticas"       (perdeu localização)
"construção barragem"                 (poderia ser qualquer lugar)
"programa de educação"                (genérico demais)
```

#### **Distribuição Geográfica no Dataset**

- **Norte:** 3 queries (Belém, Pará, contexto amazônico)
- **Nordeste:** 5 queries (Bahia, região Nordeste)
- **Centro-Oeste:** 2 queries (Corumbá-MS)
- **Sudeste:** 4 queries (MG, RJ, Vale do Jequitinhonha)
- **Sul:** 3 queries (Paraná, Rio Grande do Sul)

**Cobertura:** Todas as 5 regiões representadas

#### **Métrica Específica**

Planejamos calcular **NDCG@10 para queries geográficas** separadamente para identificar se modelos têm dificuldade específica com contexto regional.

#### **Referências**

- **Gravano et al. (2003):** "Categorizing Web Queries According to Geographical Locality" - 18.6% de queries web têm intenção geográfica

---

### 3. **Mix de Jargão Técnico e Coloquial**

#### **Por que é importante?**

O caso de uso (notícias gov.br) tem, possivelmente, **dois perfis de usuários distintos**:

**Perfil A: Público Geral**
- Cidadãos buscando informações sobre serviços
- Linguagem natural, coloquial
- Exemplo: `"ajuda financeira para pescadores"`

**Perfil B: Profissionais**
- Servidores públicos, jornalistas, gestores, pesquisadores
- Usam siglas e jargão técnico
- Exemplo: `"PRONAF crédito rural"`

**Se testarmos apenas com um perfil**, os resultados serão **enviesados** e não refletirão performance real.

#### **Implicações para Embeddings**

Esta é uma **área crítica de diferenciação** entre modelos:

**Modelos Multilíngues (BGE-M3, E5):**
- Treinados em corpus diverso (100+ línguas), mas com foco em uma língua que não é o português.
- Podem **não conhecer siglas brasileiras** (MEC, SUS, INSS, DNOCS)
- Potencial **desvantagem** em queries com jargão não vistos originalmente
- **Vantagem:** Multi-functionality (BGE-M3 tem sparse retrieval que captura termos exatos)

**Modelos PT-BR Específicos (Serafim, BERTimbau):**
- Treinados exclusivamente em português brasileiro
- **Maior exposição** a siglas e jargões durante treino
- Potencial **vantagem** em queries técnicas
- Potencial **desvantagem** corpus geral e capacidade de treinamento menores do que grandes modelos vindos de fora
- **Hipótese testável:** Serafim deve ter NDCG@10 mais alto em queries "jargao_br"

#### **Como validamos**

Distribuição intencional:
- **43 queries gerais** (linguagem natural, público geral)
- **36 queries jargão BR** (siglas, termos técnicos, profissionais)
- **6 queries docs longos** (complexas, múltiplos conceitos)

#### **Jargões Incluídos no Dataset**

**Órgãos/Agências:**
- DNOCS, INSS, IBAMA, CADE, ANTT, CVM, CDTN, AGU
- MEC, SUS, MIDR, CNPq, INPA, ICMBio, ANVISA
- Ministérios por extenso + siglas

**Programas:**
- PRONAF, PNLD, FUNDEB, PAC Saúde, Bolsa Família
- PREPS, Pertinho da Gente

**Termos Técnicos:**
- "portaria", "decreto", "lei complementar"
- "regulados", "cartel", "infração ambiental"
- "concessão", "licitação", "saneamento"

**Rodovias/Infraestrutura:**
- BR-020/BA, BR-174/RR, DNIT

#### **Exemplos no Dataset**

**Jargão técnico (profissionais):**
```
"AGU mantém multa Spectrum"                    (AGU + empresa)
"cdtn seleção mestrado"                        (sigla + contexto)
"programa jovem cientista pesca artesanal"     (nome oficial)
"implantação segmento br 020 ba"               (código rodoviário)
"regulados CVM no ano"                         (termo técnico)
"ibama agu ambiental infração"                 (órgãos + jargão)
```

**Linguagem coloquial (público geral):**
```
"tilápia açude ema"                           (sem siglas)
"microcrédito pescadores"                     (linguagem simples)
"construção barragem Rio grande do sul"       (termos comuns)
"ribeirinhos testagem tuberculose"            (linguagem acessível)
```

**Mix (híbrido):**
```
"PAC Saúde entregas bahia"                    (sigla conhecida + contexto)
"conflito agrário paraná acordo"              (termo técnico + geografia)
"teia nacional corumbá"                       (nome de programa + cidade)
```

#### **Análise Planejada**

Calcularemos **NDCG@10 separadamente** para:
1. Queries gerais (baseline)
2. Queries jargão BR (métrica crítica!)
3. Queries docs longos

**Critério de Decisão:**  
Se Modelo A tem NDCG@10 geral 5% maior que Modelo B, MAS Modelo B tem NDCG@10 jargão 10% maior, **priorizamos Modelo B** (jargão é crítico para o caso de uso).

#### **Referências**

- **ROTEIRO_TESTES_EMBEDDINGS.md:** Peso de 25/100 pontos para "NDCG@10 Jargão BR"
- **Hofmann et al. (2019):** "Semantic Models for the First-stage Retrieval: A Comprehensive Review" - Embeddings densos lutam com termos raros/siglas
- **Luan et al. (2021):** "Sparse, Dense, and Attentional Representations for Text Retrieval" - Modelos hybrid (dense+sparse) têm vantagem em queries com termos técnicos

---

## Resumo da Distribuição Final

### **Por Tipo de Query**
```
Geral:       43 queries (50.6%) → Linguagem natural
Jargão BR:   36 queries (42.4%) → Termos técnicos
Docs Longos:  6 queries ( 7.0%) → Queries complexas
```

### **Por Comprimento**
```
3 palavras:  13 queries (15.3%)
4 palavras:  33 queries (38.8%) mais de 50% até 4 palavras
5 palavras:  25 queries (29.4%)
6+ palavras: 14 queries (16.5%)

Média: 4.6 palavras
```

### **Contexto Geográfico**
```
Com geografia:    17 queries (20.0%)
Sem geografia:    68 queries (80.0%)
```

### **Jargão Governamental**
```
Com siglas/jargão: ~40 queries (47%)
Linguagem comum:   ~45 queries (53%)
```

---  

### **Capacidades Testadas**

**Semântica geral:** Queries sem jargão testam compreensão básica PT-BR  
**Jargão BR:** Queries técnicas testam conhecimento de domínio governamental  
**Contexto geográfico:** Queries regionais testam conhecimento de geografia BR  
**Variação lexical:** Queries naturais testam robustez a variações de escrita  
**Docs longos:** Queries complexas testam capacidade de max_tokens e contexto  

---

## Critérios de Sucesso

Um modelo de embedding é considerado **adequado** para notícias gov.br se:

1. **NDCG@10 geral > 0.85** (boa compreensão semântica geral)
2. **NDCG@10 jargão BR > 0.80** (captura siglas e termos técnicos)
3. **NDCG@10 geografia > 0.75** (entende contexto regional)
4. **Gap jargão-geral < 10%** (não perde muito em queries técnicas)

Se **nenhum modelo** atinge esses critérios → **Fine-tuning necessário** (Issue #2)

---

## Referências

### **Comportamento de Busca**

1. **Jansen, B. J., Spink, A., & Saracevic, T. (2000)**  
   *"Real life, real users, and real needs: a study and analysis of user queries on the web"*  
   Information Processing & Management, 36(2), 207-227.

2. **Spink, A., Wolfram, D., Jansen, M. B., & Saracevic, T. (2001)**  
   *"Searching the Web: The public and their queries"*  
   Journal of the American Society for Information Science and Technology, 52(3), 226-234.

3. **Rose, D. E., & Levinson, D. (2004)**  
   *"Understanding user goals in web search"*  
   Proceedings of the 13th international conference on World Wide Web.

### **Busca Geográfica**

4. **Gravano, L., Hatzivassiloglou, V., & Lichtenstein, R. (2003)**  
   *"Categorizing web queries according to geographical locality"*  
   Proceedings of the twelfth international conference on Information and knowledge management.

### **Embeddings e Jargão**

5. **Hofmann, K., Oosterhuis, H., & Whiteson, S. (2019)**  
   *"Semantic Models for the First-stage Retrieval: A Comprehensive Review"*  
   ACM Transactions on Information Systems.

6. **Luan, Y., Eisenstein, J., Toutanova, K., & Collins, M. (2021)**  
   *"Sparse, Dense, and Attentional Representations for Text Retrieval"*  
   Transactions of the Association for Computational Linguistics, 9.

### **Documentos Internos**

7. **ROTEIRO_TESTES_EMBEDDINGS.md** - Metodologia geral de avaliação  
8. **GUIA_CRIACAO_QUERIES_85.md** - Fundamentação de tamanho de queries  
9. **ANALISE_CORPUS.md** - Análise estatística do corpus de notícias  
---

**Nota:** Este documento deve ser referenciado na seção de Metodologia do relatório final (**RESEARCH_EMBEDDING_MODELS.md**) para justificar as escolhas de design das queries de teste.
