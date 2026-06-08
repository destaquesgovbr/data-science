# Queries Expandidas - 259 Variantes

**Data:** 2026-04-02  
**Projeto:** Issue #1 - Comparativo de Modelos de Embedding PT-BR

---

## Resumo Executivo

Das **85 queries** originais (uma por documento âncora), expandimos para **259 queries totais** usando as variantes criadas manualmente.

**Estrutura:**
- 85 documentos âncora
- ~3 variantes por documento
- **Total: 259 queries únicas**

---

## Justificativa da Expansão

### Por que usar todas as variantes?

1. **Robustez a reformulações:**
   - Usuários diferentes buscam o mesmo conceito com palavras diferentes
   - Modelo robusto deve retornar resultados similares independente da formulação

2. **Cobertura de perfis:**
   - Variante 1: Geralmente simples/título (público geral)
   - Variante 2: Com jargão/siglas (profissionais)
   - Variante 3: Sem jargão (público geral alternativo)

3. **Mais dados = mais confiança estatística:**
   - 259 queries vs 85 queries = **3x mais evidência**
   - Testes estatísticos mais confiáveis
   - Identificação de padrões mais clara

4. **Nova métrica: Consistência:**
   - Mede se modelo retorna mesmo documento para variantes da mesma query
   - Identifica fragilidade a palavras exatas

---

## Distribuição

### Por Número de Variantes

```
3 variantes: 79 queries (93%)
4 variantes:  5 queries (6%)
2 variantes:  1 query  (1%)

Total documentos âncora: 85
Total queries expandidas: 259
```

### Tipos de Variantes

**Variant 1 (from_title):**
- Baseada no título simplificado
- 2-3 palavras geralmente
- Linguagem natural
- Exemplo: "tilápia açude ema"

**Variant 2 (with_jargon):**
- Inclui siglas, órgãos, termos técnicos
- 3-4 palavras
- Perfil: Profissionais/servidores
- Exemplo: "alevinos dnocs iracema"

**Variant 3 (without_jargon / contextual):**
- Linguagem coloquial, sem siglas
- 3-4 palavras
- Perfil: Público geral
- Exemplo: "piscicultura alevinos tilápia Iracema"

---

## Exemplos de Expansão

### Query q001 (Agricultura)

**Documento âncora:** doc_01_08  
**Título:** DNOCS realiza peixamento no Açude Ema em Iracema/CE

**Variantes:**
1. `"tilápia açude ema"` (simples)
2. `"alevinos dnocs iracema"` (jargão: DNOCS + localização)
3. `"piscicultura alevinos tilápia Iracema"` (descritivo)

---

### Query q005 (Agricultura)

**Documento âncora:** doc_01_06  
**Título:** Acordo põe fim a conflito agrário histórico no oeste do Paraná

**Variantes:**
1. `"assentamento celso furtado paraná"` (nome específico + local)
2. `"agu pnra rio das cobras acordo"` (jargão: AGU + PNRA)
3. `"conflito agrário paraná acordo"` (descritivo geral)

---

### Query q050 (Educação)

**Documento âncora:** doc_11_11  
**Título:** ANA convoca aprovados em seu concurso público

**Variantes:**
1. `"convocação candidados ANA segunda turma"` (natural)
2. `"CEBRASPE convocação regulação hídrica ANA"` (jargão: banca + órgão)
3. `"saneamento e regulação hídrica convocação"` (área técnica)

---

### Query q075 (Saúde)

**Documento âncora:** doc_17_06  
**Título:** Projeto promove testagem para ISTs, cuidados com a tuberculose

**Variantes:**
1. `"ribeirinhos testagem tuberculose"` (público-alvo)
2. `"opas/OMS Mobiliza TB Rondônia"` (siglas internacionais + programa)
3. `"cuidados tuberculose populações ribeirinhas Mobiliza TB"` (descritivo)

---

## Impacto nos Testes

### Ground Truth

**Antes (85 queries):**
- 85 queries × 250 docs = 21,250 anotações potenciais

**Depois (259 queries):**
- 259 queries × 250 docs = 64,750 anotações potenciais

**Estratégia híbrida:**
- Anchor-only: 259 anotações automáticas (1 min)
- Top-10 interativo: ~30-40 queries × 10 docs = 300-400 anotações manuais (~4-5h)
- **Total manejável:** ~550 anotações

---

### Métricas Adicionais

Com 259 queries, podemos calcular:

1. **NDCG@10 geral** (todas as 259)

2. **NDCG@10 por tipo de variante:**
   - Variantes simples (from_title)
   - Variantes com jargão (with_jargon)
   - Variantes coloquiais (without_jargon)

3. **Consistência intra-documento:**
   ```
   Para cada documento âncora:
     Consistency@10 = (variantes com âncora no top-10) / (total variantes)
   
   Modelo robusto: Consistency → 1.0
   Modelo frágil: Consistency → 0.3-0.5
   ```

4. **Análise de robustez:**
   - Quais modelos são mais sensíveis a reformulações?
   - Jargão vs coloquial: qual tem mais impacto?

---

## Vantagens vs Trade-offs

### Vantagens

- **Robustez:** Testa performance com diferentes formulações
- **Realismo:** Reflete diversidade de usuários reais
- **Confiança:** 3x mais dados = resultados mais confiáveis
- **Nova métrica:** Consistência entre variantes
- **Cobertura:** Público geral + profissionais bem representados

### Trade-offs

- **Tempo de busca:** 3x mais queries = 3x mais tempo (~3× mais lento)
- **Armazenamento:** Resultados 3x maiores
- **Ground truth:** Mais anotações (mas estratégia híbrida resolve)

### Decisão

**Vantagens superam trade-offs** → Usamos as 259 queries!

---

## Uso nos Scripts

### semantic_search.py

```python
# Expande automaticamente todas as variantes
queries = load_queries()  
# Output: 259 queries carregadas (expandidas de 85 documentos âncora)
```

### evaluate_consistency.py

```python
# Avalia consistência entre variantes de mesma query base
python evaluate_consistency.py
# Output: Consistency@10 por modelo
```

### evaluate_metrics.py

```python
# Calcula métricas incluindo breakdown por tipo de variante
python evaluate_metrics.py
# Output: NDCG@10 geral + por variante
```

---

## Referências

- **METODOLOGIA_QUERIES.md:** Justificativa dos perfis de usuário
- **query_template_85.json:** Estrutura completa com variantes
- **semantic_search.py:** Implementação da expansão

---

**Última atualização:** 2026-04-02
