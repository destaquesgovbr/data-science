# Changelog - Expansão para 259 Queries

**Data:** 2026-04-02  
**Mudança:** Expandido de 85 queries → 259 queries (todas as variantes)

---

## O que mudou

### Antes
- 85 queries (apenas `recommended_query`)
- Uma query por documento âncora
- Não testava robustez a reformulações

### Depois
- **259 queries** (todas as variantes expandidas)
- ~3 variantes por documento âncora
- Testa robustez, consistência e cobertura de perfis

---

## Scripts Atualizados

### 1. `semantic_search.py`
- ✅ Agora expande todas as variantes
- ✅ Cria query_id com sufixo (ex: q001_v1, q001_v2, q001_v3)
- ✅ Mantém metadados (base_query_id, variant_num, variant_type)

### 2. `create_ground_truth.py`
- ✅ Suporta estrutura expandida
- ✅ Anchor-only cria anotações para todas as 259 queries
- ✅ Mostra estatísticas (259 queries, 85 âncoras únicas)

### 3. `evaluate_metrics.py`
- ✅ Calcula métricas para 259 queries
- ✅ Adiciona breakdown por tipo de variante
- ✅ Agregação por variant_type (from_title, with_jargon, etc)

### 4. `evaluate_consistency.py` (NOVO)
- ✅ Nova métrica: Consistency@K
- ✅ Mede robustez a reformulações
- ✅ Identifica modelos frágeis vs robustos

### 5. `run_evaluation.py`
- ✅ Adiciona passo 4: Avaliação de Consistência
- ✅ Flag `--skip-consistency` para controle
- ✅ Numeração atualizada (6 passos → 7 passos)

---

## Novos Arquivos

```
docs/
├── QUERIES_EXPANDIDAS.md        # Documentação das 259 queries
└── METODOLOGIA_QUERIES.md        # Já existia, sem mudanças

scripts/
├── evaluate_consistency.py       # NOVO - Avalia consistência
├── semantic_search.py            # ATUALIZADO
├── create_ground_truth.py        # ATUALIZADO
├── evaluate_metrics.py           # ATUALIZADO
├── run_evaluation.py             # ATUALIZADO
└── README.md                     # ATUALIZADO
```

---

## Nova Métrica: Consistency@K

**O que é:**
- Para cada documento âncora (ex: q001), verifica se aparece no top-K de todas as variantes
- Consistency@10 = (variantes com âncora no top-10) / (total variantes)

**Interpretação:**
```
Consistency > 0.8  → Modelo robusto
Consistency 0.5-0.8 → Moderadamente sensível
Consistency < 0.5  → Muito frágil
```

**Exemplo:**
```
q001 com 3 variantes:
  v1: doc_01_08 em pos 1  ✓
  v2: doc_01_08 em pos 3  ✓
  v3: doc_01_08 em pos 8  ✓
  Consistency@10 = 3/3 = 1.0 (perfeito!)
```

---

## Benefícios da Mudança

### 1. Robustez
- Testa se modelo funciona bem com formulações diferentes
- Identifica sensibilidade a palavras exatas

### 2. Cobertura de Perfis
- Variantes simples → Público geral
- Variantes com jargão → Profissionais
- Variantes coloquiais → Usuários casuais

### 3. Confiança Estatística
- 259 queries vs 85 = 3x mais dados
- Testes estatísticos mais confiáveis
- Padrões mais claros

### 4. Nova Dimensão de Análise
- Consistência entre variantes
- Qual tipo de variante cada modelo prefere
- Robustez como critério de seleção

---

## Trade-offs

### Tempo de Processamento
- Busca: 259 queries vs 85 = ~3x mais lento
- Ainda manejável: ~10-15 min vs ~3-5 min

### Armazenamento
- Resultados 3x maiores
- Não é problema (alguns MB)

### Ground Truth
- 259 × 250 = 64,750 anotações potenciais
- **Solução:** Estratégia híbrida (anchor + subset) = ~550 anotações

---

## Compatibilidade

### Retrocompatibilidade
- Scripts antigos continuam funcionando
- Se preferir 85 queries, modificar `load_queries()` é simples

### Forward compatibility
- Estrutura preparada para mais variantes no futuro
- Metadados permitem análises flexíveis

---

## Próximos Passos

1. **Testar pipeline:** `python run_evaluation.py`
2. **Verificar consistência:** Primeiro modelo mostrará se expansão funcionou
3. **Ajustar se necessário:** Se algum problema, fácil reverter

---

## Como Usar

### Pipeline completo (recomendado)
```bash
python run_evaluation.py
# Usa automaticamente 259 queries
```

### Passo a passo
```bash
python semantic_search.py          # 259 queries
python evaluate_consistency.py     # Nova métrica
python create_ground_truth.py --mode anchor-only
python evaluate_metrics.py         # Com breakdown por variante
```

---

## Perguntas Frequentes

**Q: Por que não usar apenas recommended_query?**  
A: Perde diversidade, não testa robustez, menos confiança estatística.

**Q: 64k anotações não é muito?**  
A: Sim! Por isso usamos estratégia híbrida: anchor-only (auto) + top-10 de subset (manual).

**Q: Vai demorar muito mais?**  
A: ~3x mais tempo na busca (~10-15 min total). Aceitável pelo ganho de qualidade.

**Q: E se um modelo for inconsistente?**  
A: Isso é informação valiosa! Significa que depende muito da formulação exata = problema em produção.

---

**Aprovado por:** Luis Felipe de Moraes  
**Data de implementação:** 2026-04-02
