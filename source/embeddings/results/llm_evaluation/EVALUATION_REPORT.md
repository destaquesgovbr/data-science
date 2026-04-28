# Relatório de Avaliação de LLMs - Issue #3

**Data:** 2026-04-27 16:26:06
**Total de modelos testados:** 12
**Modelos funcionais:** 7
**Total de notícias de teste:** 200
**Categorias:** 10

---

## 🏆 Melhor Modelo

**Claude 3 Sonnet** (S)

- **Accuracy:** 51.00%
- **F1-Macro:** 0.3732
- **F1-Weighted:** 0.4851
- **Latência P50:** 0.657s
- **Custo (200 notícias):** $0.4605

---

## 📊 Ranking Completo

### Por Accuracy

| Rank | Modelo | Tier | Accuracy | F1-Macro | Custo |
|------|--------|------|----------|----------|-------|
| 1 | Claude 3 Sonnet | S | 51.00% | 0.3732 | $0.4605 |
| 2 | Claude 3 Haiku | S | 48.00% | 0.3737 | $0.0383 |
| 3 | Amazon Nova Pro | B | 47.00% | 0.3608 | $0.1021 |
| 4 | Mistral Large 2 | A | 46.00% | 0.3445 | $0.0000 |
| 5 | Amazon Nova Micro | B | 45.50% | 0.3546 | $0.0045 |
| 6 | Amazon Nova Lite | B | 42.50% | 0.3416 | $0.0076 |
| 7 | Mistral 7B | D | 32.50% | 0.2633 | $0.0000 |

### Por Custo-Benefício (Accuracy / Custo)

| Rank | Modelo | Accuracy | Custo | Custo-Benefício |
|------|--------|----------|-------|------------------|
| 1 | Mistral Large 2 | 46.00% | $0.0000 | 4600.00 |
| 2 | Mistral 7B | 32.50% | $0.0000 | 3250.00 |
| 3 | Amazon Nova Micro | 45.50% | $0.0045 | 101.48 |
| 4 | Amazon Nova Lite | 42.50% | $0.0076 | 55.80 |
| 5 | Claude 3 Haiku | 48.00% | $0.0383 | 12.53 |

---

## 💡 Insights

### Performance
- **Melhor accuracy:** 51.00% (Claude 3 Sonnet)
- **Accuracy médio:** 44.64%
- **Spread:** 18.50%

### Custo
- **Mais econômico:** Amazon Nova Micro ($0.0000)
- **Mais caro:** Claude 3 Sonnet ($0.4605)
- **Custo total (todos modelos):** $0.61

### Latência
- **Mais rápido:** Mistral 7B (0.362s)
- **Mais lento:** Claude 3 Sonnet (0.657s)

---

## 🎯 Recomendações

### Para Produção (Melhor Performance)
**Claude 3 Sonnet** - Accuracy de 51%, mas custo elevado ($0.46/200 notícias)

### Para Produção (Melhor Custo-Benefício)
**Amazon Nova Micro** - Accuracy de 45.5% com custo mínimo ($0.004/200 notícias)
**Custo-benefício:** 101x melhor que Claude 3 Sonnet

### Para Experimentação
**Amazon Nova Lite** ou **Amazon Nova Pro** - Boa performance intermediária

---

## 📁 Arquivos Gerados

- `comparison_summary.csv` - Tabela comparativa
- `comparison_full.json` - Dados completos com predições
- `model_rankings.txt` - Rankings por métrica
- `visualizations/` - Gráficos e visualizações

---

## 🔧 Categorias Avaliadas

Agricultura, Ciência e Tecnologia, Cultura, Economia, Educação, Meio Ambiente, Outros, Política, Saúde, Segurança

---

**Gerado automaticamente pela Issue #3 - LLM Classification Evaluation**
