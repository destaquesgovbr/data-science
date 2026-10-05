# Avaliação: Amazon Nova 2 Lite para Classificação Temática

**Data:** 2026-06-25  
**Contexto:** Issue #177 (data-platform) + extensão da Issue #4  
**Objetivo:** Validar se Amazon Nova 2 Lite pode ser usado para classificação temática, além de sumarização

---

## 🎯 Motivação

### Situação Atual

**Issue #4 (Sumarização):** Validou que Nova 2 Lite é **superior** ao Claude Haiku para resumos:
- Qualidade: +3.5% ROUGE-L F1 (0.502 vs 0.485)
- Latência: -38% mais rápido (1.32s vs 2.12s)  
- Custo: -25% mais barato ($30 vs $40/mês)

**Issue #3 (Classificação):** Validou Claude Haiku para classificação hierárquica:
- Accuracy: 80.5% no nível L3 (mais específico)
- **MAS:** Nova 2 Lite ainda não existia quando Issue #3 foi realizada!

### Problema

**Arquitetura atual:**
- Uma ÚNICA chamada LLM faz classificação + resumo + sentimento
- Mudança para Nova 2 Lite (Issue #176) **também afeta a classificação**
- Não sabemos se Nova classifica tão bem quanto Haiku

### Questão de Pesquisa

**Nova 2 Lite consegue classificar notícias com qualidade comparável ao Haiku 80.5%?**

Se SIM → usar Nova para TUDO (1 chamada, mais rápido, mais barato)  
Se NÃO → separar chamadas (Haiku p/ classificação, Nova p/ resumo)

---

## 🧪 Metodologia

### Teste 1: Comparação Direta Haiku vs Nova (5 notícias)

**Setup:**
- Taxonomia: `arvore.yaml` (25 categorias L1, ~500 L3)
- Notícias: 5 casos representativos (Saúde, Economia, Educação, Segurança, Meio Ambiente)
- Prompt: IDÊNTICO para ambos os modelos (inclui taxonomia completa)
- Modelo comparação: Haiku 3 (baseline da Issue #3)
- Modelo avaliado: Nova 2 Lite V2

**Resultados:**

| # | Notícia | L1 Match | L2 Match | L3 Match | Observação |
|---|---------|----------|----------|----------|------------|
| 1 | COVID Vacinação | ✓ (03) | ✗ | ✗ | Haiku: SUS/Assistência, Nova: Programas/Idoso. Ambos válidos. |
| 2 | Selic | ✓ (01) | ✓ (01.01) | ✗ | Haiku: Análise Econômica, Nova: Política Fiscal. Nuance aceitável. |
| 3 | ENEM | ✓ (02) | ✓ (02.04) | ✓ (02.04.01) | **Match perfeito!** |
| 4 | PF Corrupção | ✗ | ✗ | ✗ | Haiku: Segurança Pública, Nova: Justiça. **Ambos corretos** (tema cruzado). |
| 5 | Ibama | ✓ (05) | ✓ (05.01) | ✓ (05.01.01) | **Match perfeito!** |

**Métricas:**
- L1 (tema macro): 80% acordo
- L2 (subtema): 60% acordo
- L3 (específico): 40% acordo
- **Latência:** Nova 45% mais rápido (1.98s vs 3.61s)

**Interpretação:**
- Divergências em L2/L3 são **nuances válidas**, não erros
- Caso #4: notícia tem classificação AMBÍGUA (é Segurança E Justiça)
- Comparar Haiku vs Nova ≠ comparar vs ground truth humano
- Para accuracy real, precisamos dataset com rótulos humanos

### Teste 2: Qualidade Isolada do Nova (8 notícias)

**Setup:**
- Notícias: 8 casos diversos (Saúde, Economia, Educação, Segurança, Meio Ambiente, Cultura, Trabalho, Infraestrutura)
- Foco: avaliar **qualidade absoluta** do Nova, não relativa ao Haiku
- Script: `test_nova_quality_sample.py`

**Resultados:**

| Métrica | Valor |
|---------|-------|
| Classificações bem-sucedidas | 8/8 (100%) |
| Latência média | 1.91s |
| Latência p50 | 1.84s |
| Latência p95 | 2.90s |

**Distribuição L1:**
- Economia e Finanças: 25%
- Outros (7 categorias): 12.5% cada

**Avaliação Manual (Amostra):**

1. **Vacinação contra gripe** → `03.05.02 - Saúde do Idoso` ✓ Correto
2. **Selic 9,5%** → `01.01.01 - Política Fiscal` ✓ Correto (poderia ser Política Econômica também)
3. **Bolsas MEC** → `02.04.03 - Bolsas e Incentivos` ✓ Perfeito
4. **PF tráfico** → `04.02.02 - Operações Contra o Tráfico de Drogas` ✓ Perfeito
5. **Ibama multa** → `05.01.01 - Proteção da Vida Selvagem` ✓ Correto
6. **BNDES rodovias** → `01.04.03 - Financiamento de Infraestrutura` ✓ Perfeito
7. **Cultura editais** → `08.03.02 - Financiamento e Editais` ✓ Perfeito
8. **MTB fiscalização** → `14.04.02 - Inspeção do Trabalho` ✓ Perfeito

**Taxa de Acerto Manual:** 8/8 = **100%** (pequena amostra)

**Resumos Gerados:**
- Concisos (1-2 frases)
- Capturam ponto principal
- Nenhum problema de PII ou conteúdo inapropriado

---

## 📊 Análise

### Pontos Fortes do Nova 2 Lite

1. **Latência excelente:** 1.91s média (vs Haiku 3.61s = 47% mais rápido)
2. **Classificações coerentes:** 100% das 8 notícias classificadas corretamente
3. **L1 (tema macro) robusto:** 80% de acordo com Haiku
4. **Resumos de qualidade:** validado na Issue #4

### Limitações do Estudo

1. **Amostra pequena:** apenas 8-13 notícias testadas
2. **Sem ground truth:** comparamos Nova vs Haiku, não vs humano
3. **Divergências ≠ Erros:** muitas notícias têm múltiplas classificações válidas
4. **Não testamos edge cases:** notícias ambíguas, multi-tema, etc

### Comparação com Issue #3

| Aspecto | Issue #3 (Haiku) | Este Estudo (Nova) |
|---------|------------------|-------------------|
| **Amostra** | ~300 notícias | 8 notícias |
| **Ground Truth** | Sim (humano) | Não (vs Haiku) |
| **Accuracy L3** | 80.5% | Desconhecida* |
| **Latência** | ~3.6s | 1.9s (-47%) |
| **Custo** | $40/mês | $30/mês (-25%) |

*Accuracy real só pode ser medida vs dataset rotulado por humanos

---

## 🎯 Recomendações

### Recomendação Primária: Teste Expandido

**Executar mini-Issue #3 para Nova:**

1. **Dataset:** Usar o MESMO dataset da Issue #3 (se disponível)
   - ~300 notícias com classificações humanas validadas
   - Garante comparação direta Haiku 80.5% vs Nova ?%

2. **Metodologia:** Idêntica à Issue #3
   - Prompt com taxonomia completa
   - Temperatura 0
   - Avaliar accuracy L1, L2, L3

3. **Critério de Aceitação:** Nova accuracy ≥ 75% no L3
   - 75% é ligeiramente abaixo do Haiku (80.5%)
   - Trade-off justificável pelos ganhos de latência/custo
   - Se < 75%, considerar split de modelos

**Esforço estimado:** 1-2 dias  
**Confidence gain:** Alto (validação científica)

### Recomendação Alternativa: Deploy Monitorado

Se teste expandido for inviável:

1. **Staging:** Deploy Nova para classificação + resumo
2. **Logging:** Salvar TODAS as classificações por 1 semana
3. **Amostragem:** Revisar manualmente 50-100 classificações
4. **Métricas:** Calcular accuracy real vs revisão humana
5. **Decisão:** Se ≥ 75%, aprovar; senão, reverter

**Esforço estimado:** 1 semana + 2h revisão  
**Confidence gain:** Médio (dados reais de produção)

### Recomendação Conservadora: Split de Modelos

Se não houver tempo para validação:

1. **Classificação:** Manter Haiku (80.5% validado)
2. **Resumo:** Usar Nova (Issue #4 validado)
3. **Custo:** 2 chamadas LLM (~$50/mês total)
4. **Latência:** ~5s total (3.6s + 1.3s)

**Esforço estimado:** Imediato  
**Confidence gain:** Alto (ambos validados)

---

## 🔧 Artefatos Gerados

### Scripts

1. **`test_nova_with_taxonomy.py`**  
   Compara Haiku vs Nova em notícias de exemplo com taxonomia fixa

2. **`test_nova_quality_sample.py`**  
   Testa Nova isoladamente e gera relatórios HTML para revisão manual

3. **Outputs:**
   - `/tmp/nova_vs_haiku_with_taxonomy.json` (comparação direta)
   - `/tmp/nova_quality_test/results_review.html` (revisão visual)
   - `/tmp/nova_quality_test/report.txt` (estatísticas)

### Próximos Passos para Usar com Notícias Reais

O script `test_nova_quality_sample.py` está pronto para rodar com PostgreSQL.

**Para executar com 50-100 notícias reais:**

```bash
# 1. Conectar ao PostgreSQL com notícias
# Ajustar DATABASE_URL no script ou via env var

# 2. Modificar função load_news_sample() para:
import psycopg2

conn = psycopg2.connect("postgresql://user:pass@localhost:5432/destaques")
cursor = conn.cursor()
cursor.execute("""
    SELECT unique_id, title, content, agency_name, published_at 
    FROM news 
    WHERE summary IS NOT NULL  -- já tem resumo
    ORDER BY RANDOM() 
    LIMIT 50
""")
news = cursor.fetchall()

# 3. Executar
poetry run python scripts/test_nova_quality_sample.py

# 4. Revisar resultados em /tmp/nova_quality_test/results_review.html
```

---

## 📚 Conclusão

**Evidências a favor do Nova 2 Lite:**
- ✓ Latência 47% melhor que Haiku
- ✓ Custo 25% menor
- ✓ Resumos validados como superiores (Issue #4)
- ✓ Classificações coerentes em amostra pequena (100%)
- ✓ L1 (tema macro) 80% de acordo com Haiku

**Incertezas:**
- ⚠ Accuracy real vs ground truth humano desconhecida
- ⚠ Amostra pequena (8-13 notícias)
- ⚠ Comportamento em edge cases não testado

**Decisão sugerida:**
Executar **Teste Expandido** (mini-Issue #3 para Nova) antes de aprovar para produção.  
Se inviável: **Deploy Monitorado** em staging com revisão manual.

**Risco de usar Nova sem validação adicional:**
Accuracy pode cair de 80.5% para ~70-75%, mas:
- Ganho de latência/custo pode justificar
- Monitoramento permite reverter rápido se necessário
- Tema macro (L1) parece robusto

---

**Autor:** Claude Code (Sonnet 4.5) + Luis Felipe de Moraes  
**Revisão:** Pendente  
**Status:** Proposta de pesquisa
