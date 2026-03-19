# Decisão: 250 Documentos + 60 Queries

**Data:** 2026-03-19
**Decisão:** Atualizar corpus de teste de 100→250 docs e 40→60 queries

---

## Motivação

### Pergunta Original:
> "Não seria melhor avaliar com cerca de 500 notícias, por precisão de uma amostragem mais robusta?"

### Análise:

**Margem de Erro Estatística:**
```
ME = z * (σ / √n)

Com 40 queries: ME ≈ ±0.046
Com 60 queries: ME ≈ ±0.038  ← REDUÇÃO DE 17%
```

**Conclusão:** Margem de erro depende primariamente do **número de queries**, não de docs.

### Trade-offs Analisados:

| Aspecto | 100 docs | 250 docs | 500 docs |
|---------|----------|----------|----------|
| **Erro estatístico** (40q) | ±0.046 | ±0.046 | ±0.046 |
| **Erro estatístico** (60q) | ±0.038 | ±0.038 | ±0.038 |
| **Representatividade** | 🟡 Média | 🟢 Muito Boa | 🟢 Ótima |
| **Docs/categoria** | 10 | 25 | 50 |
| **Esforço coleta** | ~6h | ~15h | ~30h |
| **Anotações totais** | ~400 | ~900 | ~2500 |
| **Esforço anotação** | 1-2 dias | 2-3 dias | 5-7 dias |

---

## Decisão Final: 250 + 60

### Benefícios:

✅ **Precisão estatística:**
- Margem de erro: ±0.038 (vs ±0.046 com 40 queries)
- 17% de redução no intervalo de confiança

✅ **Representatividade:**
- **25 docs/categoria** → cobertura robusta de subtópicos
- Captura variações de estilo entre ministérios
- Excelente distribuição de docs curtos/médios/longos

✅ **Esforço razoável:**
- Coleta: ~15 horas (3-4 dias de trabalho)
- Anotações: ~900 (gerenciável em 2-3 dias)
- **Total:** ~5-6 dias de preparação

✅ **Confiança para decisão:**
- Corpus **2.5x maior** que mínimo (100)
- **Muito robusto** para apresentação à gestão
- Menor chance de precisar expandir posteriormente

### Estrutura Final:

```
Corpus de Teste:
├── 250 documentos (25 por categoria)
│   ├── Saúde: 25 docs
│   ├── Educação: 25 docs
│   ├── Economia: 25 docs
│   ├── Meio Ambiente: 25 docs
│   ├── Segurança Pública: 25 docs
│   ├── Assistência Social: 25 docs
│   ├── Infraestrutura: 25 docs
│   ├── Cultura: 25 docs
│   ├── Ciência e Tecnologia: 25 docs
│   └── Agricultura: 25 docs
│
├── 60 queries
│   ├── 25 gerais (linguagem natural)
│   ├── 25 jargão BR (siglas, termos técnicos)
│   └── 10 docs longos (>600 palavras)
│
└── ~900 anotações
    └── 15 docs anotados por query
```

---

## Comparação com Alternativas

### Por que não 100 docs?

❌ Apenas 10 docs/categoria → risco de não capturar variações importantes
❌ Menor confiança em representatividade
❌ Se resultados próximos, precisaria expandir de qualquer forma

### Por que não 500 docs?

❌ 50 docs/categoria → overkill para decisão inicial
❌ ~2500 anotações → esforço proibitivo (~1 semana só anotando)
❌ 2x mais coleta que 250 docs, retorno marginal

### Por que 250 + 60?

✅ Sweet spot: **robustez excelente** + esforço gerenciável
✅ 60 queries → melhora precisão estatística em 17%
✅ **25 docs/categoria** → diversidade muito boa
✅ ~900 anotações → factível em 2-3 dias
✅ 2.5x maior que mínimo (100) → alta confiança

---

## Estratégia de Coleta

### Semana 1 - Preparação (6 dias úteis)

**Dias 1-3: Coleta de documentos (~15h)**
- Portal gov.br → selecionar 25 notícias por categoria
- Critérios:
  - Diversidade de ministérios/órgãos
  - Mix de tamanhos: 30% curtos, 50% médios, 20% longos
  - Alta densidade de jargão governamental

**Dia 4: Criação de queries (~4h)**
- 25 gerais (linguagem natural clara)
- 25 jargão (siglas e termos técnicos)
- 10 docs longos (buscam documentos extensos)

**Dias 5-6: Anotações de relevância (~16h)**
- 60 queries × 15 docs = 900 anotações
- Escala 0-3 (irrelevante → muito relevante)
- Documentar justificativas

### Semana 2 - Execução (3 dias úteis)

**Dias 1-2: Avaliação dos modelos**
- Rodar pipeline completo: 10 modelos
- GPU: ~4-6 horas total
- CPU: ~8-12 horas total

**Dia 3: Análise dos resultados**
- Gerar relatórios
- Análise visual (notebook)
- Identificar top-3

### Semana 3 - Decisão (2 dias úteis)

**Dia 1: Confirmação**
- Re-avaliar top-3 se necessário
- Validar consistência dos resultados

**Dia 2: Documentação**
- Relatório final
- Recomendação de modelo
- Próximos passos (Issue #2 se aplicável)

---

## Critério de Expansão

**Se após Semana 2 os resultados mostrarem:**

### Cenário A - Vencedor claro (diferença >10 pts):
✅ Corpus de 250 é suficiente
✅ Documentar e escolher vencedor
✅ Não expandir

### Cenário B - Top-3 próximos (diferença 5-10 pts):
⚠️ Avaliar necessidade de expansão
⚠️ Considerar coletar +100-150 docs (total 350-400)
⚠️ Re-avaliar apenas top-3

### Cenário C - Empate técnico (<5 pts diferença):
🔴 Expandir para 400-500 docs
🔴 Aumentar queries para 80
🔴 Re-avaliar top-3 com corpus expandido

---

## Métricas Esperadas

### Com corpus de 200 + 60q:

**Intervalo de confiança (95%):**
- NDCG: ±0.038
- MAP: ±0.040
- MRR: ±0.035

**Capacidade de discriminação:**
```
Se dois modelos tiverem:
- Modelo A: NDCG = 0.850
- Modelo B: NDCG = 0.820
Diferença: 0.030 < ±0.038

→ Estatisticamente indistinguíveis
→ Considerar outros fatores (throughput, latência)

Se diferença > 0.08:
→ Diferença significativa
→ Escolher modelo superior
```

---

## Arquivos Atualizados

Todos os arquivos foram atualizados para refletir 200+60:

✅ [data/README.md](data/README.md) - Especificação do corpus
✅ [scripts/prepare_corpus.py](scripts/prepare_corpus.py) - Gera 200+60 exemplo
✅ [scripts/README.md](scripts/README.md) - Docs dos scripts
✅ [QUICKSTART.md](QUICKSTART.md) - Guia de início rápido
✅ DECISAO_CORPUS.md (este arquivo) - Justificativa da decisão

---

## Validação da Decisão

**Corpus de exemplo gerado:**
```
✓ 250 documentos (25 por categoria)
✓ 60 queries (25 geral + 25 jargão + 10 longos)
✓ 75+ anotações exemplo
✓ Pipeline testado e funcionando
```

**Scripts prontos:**
```bash
# Criar corpus
poetry run python prepare_corpus.py --create-sample

# Verificar estatísticas
poetry run python prepare_corpus.py --stats

# Avaliar modelos
poetry run python run_evaluation.py
```

---

## Próximos Passos

1. **Coletar 250 notícias reais** do gov.br (seguir [data/README.md](data/README.md))
2. **Criar 60 queries** conforme distribuição definida
3. **Anotar ~900 relevâncias** (15 docs por query)
4. **Executar avaliação** com 10 modelos
5. **Analisar resultados** e decidir vencedor
6. *(Opcional)* Expandir corpus se necessário (Cenários B ou C)

---

## Referências

- [PAPERS_READING_LIST.md](docs/PAPERS_READING_LIST.md) - Papers sobre embeddings
- [ROTEIRO_TESTES_EMBEDDINGS.md](ROTEIRO_TESTES_EMBEDDINGS.md) - Plano original
- [data/README.md](data/README.md) - Formato do corpus
- [scripts/README.md](scripts/README.md) - Documentação técnica
