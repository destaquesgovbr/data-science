# [Pesquisa] Validar Amazon Nova 2 Lite para Classificação Temática

## Contexto

**Issue #4** validou que Amazon Nova 2 Lite é **superior** ao Claude Haiku para sumarização:
- +3.5% qualidade (ROUGE-L)
- -38% latência  
- -25% custo

**Issue #3** validou Claude Haiku para classificação hierárquica:
- 80.5% accuracy no nível L3
- **MAS**: Nova 2 Lite ainda não existia!

**Problema atual:**
- Nossa arquitetura usa **UMA chamada** para classificação + resumo + sentimento
- Migração para Nova (Issue #176) também muda o modelo de classificação
- **Não sabemos** se Nova classifica tão bem quanto Haiku

## Objetivo

Validar se Amazon Nova 2 Lite consegue classificar notícias governamentais com accuracy comparável ao Haiku (baseline: 80.5%).

## Trabalho Já Realizado

### Teste Preliminar: Haiku vs Nova (commit `ad51678`)

**Metodologia:**
- 5 notícias representativas com taxonomia fixa (`arvore.yaml`)
- Prompt idêntico para ambos os modelos
- Comparação direta das classificações

**Resultados:**

| Métrica | Resultado |
|---------|-----------|
| L1 (tema macro) | 80% acordo |
| L2 (subtema) | 60% acordo |
| L3 (específico) | 40% acordo |
| Latência Nova | **47% mais rápido** (1.98s vs 3.61s) |

**Observações:**
- Divergências em L2/L3 são frequentemente nuances válidas, não erros
- Exemplo: notícia sobre PF/corrupção → Haiku classifica "Segurança Pública", Nova "Justiça" (ambos corretos)
- Comparar modelos entre si ≠ comparar com ground truth humano

### Teste de Qualidade Isolada (8 notícias)

**Resultados:**
- Taxa de sucesso: 8/8 (100%)
- Latência média: 1.91s
- Avaliação manual: todas as classificações coerentes

**Artefatos:**
- `docs/nova_classification_evaluation.md` - relatório completo
- `scripts/test_nova_with_taxonomy.py` - teste comparativo
- `scripts/test_nova_quality_sample.py` - teste de qualidade com output HTML

## O Que Falta

### Limitações do Estudo Preliminar

1. ⚠ **Amostra pequena:** apenas 8-13 notícias (Issue #3 usou ~300)
2. ⚠ **Sem ground truth:** comparamos Nova vs Haiku, não vs humano
3. ⚠ **Edge cases não testados:** notícias ambíguas, multi-tema, etc

### Proposta: Mini Issue #3 para Nova

Executar o MESMO protocolo da Issue #3, mas com Nova 2 Lite:

**Setup:**
- Dataset: ~300 notícias com classificações humanas validadas (mesmo da Issue #3)
- Prompt: idêntico ao usado na Issue #3
- Taxonomia: `arvore.yaml` (25 categorias L1, ~500 L3)
- Métricas: accuracy L1, L2, L3

**Critério de Aceitação:**
- **Accuracy L3 ≥ 75%** → Aprovar Nova para produção
  - 75% é ligeiramente abaixo do Haiku (80.5%)
  - Trade-off justificável pelos ganhos de latência/custo
- **Accuracy L3 < 75%** → Considerar split de modelos (Haiku p/ classificação, Nova p/ resumo)

**Esforço Estimado:** 1-2 dias

## Alternativas (se teste expandido for inviável)

### Opção B: Deploy Monitorado em Staging

1. Deploy Nova em staging por 1 semana
2. Log de TODAS as classificações
3. Revisão manual de 50-100 classificações aleatórias
4. Calcular accuracy real
5. Decisão baseada em dados reais

**Esforço:** 1 semana + 2h revisão

### Opção C: Split Conservador

1. Manter Haiku para classificação (80.5% validado)
2. Usar Nova para resumo (Issue #4 validado)
3. Custo: 2 chamadas LLM (~$50/mês vs $30/mês)
4. Latência: ~5s total vs ~2s

**Esforço:** Imediato, zero risco

## Recomendação

**Executar Opção A (Mini Issue #3)** para ter certeza científica.

**Justificativa:**
- Ganhos de latência/custo são significativos (47% / 25%)
- Evidências preliminares são positivas (100% em amostra pequena)
- Risco controlado: se accuracy < 75%, fazemos split (Opção C)

## Tasks

- [ ] Recuperar dataset da Issue #3 (300 notícias com ground truth humano)
- [ ] Executar script de teste com Nova 2 Lite
- [ ] Calcular accuracy L1, L2, L3
- [ ] Documentar resultados
- [ ] Decisão: aprovar Nova OU fazer split de modelos

## Referências

- Issue #3: Validação Haiku 80.5%
- Issue #4: Validação Nova para sumarização
- Issue #176 (data-platform): Migração para Nova
- Commit: `ad51678` (avaliação preliminar)

---

**Labels:** `research`, `llm`, `classification`, `nova`, `extended-issue-4`  
**Priority:** Medium  
**Effort:** 1-2 dias (teste expandido)
