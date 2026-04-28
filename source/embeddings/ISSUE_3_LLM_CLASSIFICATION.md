# Avaliação de LLMs para Classificação de Notícias - Issue #3

Projeto de comparação de múltiplos LLMs via AWS Bedrock para classificação de notícias governamentais brasileiras.

## 📋 Objetivo

Avaliar **12 modelos LLM** diferentes em termos de:
- **Qualidade**: Accuracy, F1-score
- **Custo**: Tokens consumidos e custo em USD
- **Latência**: Tempo de resposta (P50, P95, P99)
- **Adequação ao domínio**: Classificação de notícias gov.br

## 🎯 Resultados Principais

### 🏆 Melhor Modelo
**Claude 3 Sonnet**
- Accuracy: **51.0%**
- F1-Macro: 0.3732
- Custo: $0.4605 (200 notícias)
- Latência P50: 0.657s

### 💎 Melhor Custo-Benefício
**Amazon Nova Micro**
- Accuracy: **45.5%** (apenas 5.5% abaixo do melhor)
- Custo: $0.0045 (200 notícias) - **102x mais barato**
- Latência P50: 0.409s - **mais rápido**

### 📊 Modelos Avaliados (7 funcionais)

| Rank | Modelo | Accuracy | Custo | Latência P50 |
|------|--------|----------|-------|--------------|
| 1 | Claude 3 Sonnet | 51.0% | $0.46 | 0.657s |
| 2 | Claude 3 Haiku | 48.0% | $0.04 | 0.512s |
| 3 | Amazon Nova Pro | 47.0% | $0.10 | 0.512s |
| 4 | Mistral Large 2 | 46.0% | $0.00* | 0.421s |
| 5 | Amazon Nova Micro | 45.5% | $0.00 | 0.409s |
| 6 | Amazon Nova Lite | 42.5% | $0.01 | 0.410s |
| 7 | Mistral 7B | 32.5% | $0.00* | 0.362s |

\* Custo $0.00 indica que o modelo não reportou tokens (possível billing via outro método)

## 📂 Estrutura do Projeto

```
embeddings/
├── classifiers/              # Implementação dos classificadores
│   ├── base.py              # Classe abstrata BaseClassifier
│   ├── bedrock_classifier.py # Classificador universal AWS Bedrock
│   └── __init__.py
├── prompts/                  # Templates de prompts
│   └── classification_prompts.py # Zero-shot, Few-shot, CoT
├── config/
│   └── models_config.yaml   # Configuração dos 12 modelos
├── scripts/
│   ├── prepare_classification_dataset.py    # Geração do dataset
│   ├── evaluate_llm_apis.py                # Script principal de avaliação
│   └── generate_evaluation_report.py       # Geração de gráficos
├── data/classification/      # Datasets
│   ├── news_classification_full.csv        # 1000 notícias
│   ├── news_classification_train.csv       # 700 treino
│   ├── news_classification_val.csv         # 100 validação
│   ├── news_classification_test.csv        # 200 teste
│   └── dataset_metadata.json
└── results/llm_evaluation/   # Resultados
    ├── EVALUATION_REPORT.md                # Relatório completo
    ├── comparison_summary.csv              # Tabela comparativa
    ├── comparison_full.json                # Dados completos
    ├── model_rankings.txt                  # Rankings
    └── visualizations/                     # Gráficos PNG
        ├── accuracy_comparison.png
        ├── cost_vs_accuracy.png
        ├── latency_comparison.png
        ├── confusion_matrix_best.png
        └── tier_analysis.png
```

## 🚀 Como Executar

### 1. Preparar Dataset (já executado)
```bash
python scripts/prepare_classification_dataset.py
```
Gera 1000 notícias balanceadas (10 categorias × 100 docs), com split 70/10/20.

### 2. Executar Avaliação
```bash
python scripts/evaluate_llm_apis.py
```
- Testa todos os 12 modelos configurados
- Classifica 200 notícias de teste
- Calcula métricas (accuracy, F1, latency, cost)
- Tempo: ~15-20 minutos
- Custo: ~$0.60 USD (AWS Bedrock)

### 3. Gerar Visualizações
```bash
python scripts/generate_evaluation_report.py
```
Cria gráficos comparativos e relatório Markdown.

## 📊 Categorias

10 categorias de notícias governamentais:

1. **Agricultura** - Agropecuária, pesca, desenvolvimento rural
2. **Ciência e Tecnologia** - Inovação, pesquisa, tecnologia
3. **Cultura** - Patrimônio cultural, artes, eventos
4. **Economia** - Finanças, comércio, desenvolvimento econômico
5. **Educação** - Ensino básico, superior, capacitação
6. **Meio Ambiente** - Clima, recursos hídricos, conservação
7. **Outros** - Categorias não especificadas
8. **Política** - Governo, administração pública
9. **Saúde** - Saúde pública, vigilância sanitária
10. **Segurança** - Segurança pública, defesa

## 🔧 Detalhes Técnicos

### Dataset
- **Fonte**: 250 notícias reais do corpus gov.br
- **Aumento de dados**: 750 variantes sintéticas (extract_first, extract_middle, short)
- **Total**: 1000 documentos balanceados
- **Test set**: 200 notícias (20 por categoria)

### Classificadores
- **Provider**: AWS Bedrock (us-east-1)
- **Formato**: Universal adapter para múltiplos providers (Anthropic, Amazon, Meta, Mistral, Cohere)
- **Prompt**: Zero-shot (simples e econômico)
- **Temperatura**: 0 (determinístico)
- **Max tokens**: 100 (output curto)

### Métricas
- **Accuracy**: % de acertos totais
- **F1-Macro**: Média harmônica precision/recall (não ponderada)
- **F1-Weighted**: F1 ponderado por tamanho da classe
- **Latência**: P50, P95, P99 em segundos
- **Custo**: Input tokens + Output tokens (USD)

## 💡 Insights e Recomendações

### Para Produção - Alta Performance
**Recomendação:** Claude 3 Sonnet
- ✅ Melhor accuracy (51%)
- ✅ Boa generalização (F1-macro 0.37)
- ❌ Custo elevado ($0.46/200 docs = $2.30/1000 docs)
- ⚠️ Latência moderada (0.66s P50)

**Caso de uso:** Aplicações críticas onde accuracy é prioridade máxima

### Para Produção - Custo-Benefício
**Recomendação:** Amazon Nova Micro
- ✅ Accuracy competitiva (45.5% vs 51% do melhor = -11%)
- ✅ Custo mínimo ($0.004/200 docs = $0.02/1000 docs) - **100x mais barato**
- ✅ Latência rápida (0.41s P50)
- ✅ Contexto grande (128k tokens)

**Caso de uso:** Aplicações em escala, pipelines batch, MVP

### Para Experimentação
**Recomendação:** Claude 3 Haiku ou Amazon Nova Pro
- ✅ Performance intermediária (48-47% accuracy)
- ✅ Custo razoável ($0.04-0.10/200 docs)
- ✅ Boa latência (0.51s P50)

**Caso de uso:** Desenvolvimento, testes A/B, validação

## 📈 Análise de Performance

### Por que 51% é o máximo?
1. **Dataset desafiador**: Notícias gov.br têm overlap de tópicos (ex: "economia + meio ambiente")
2. **Prompts zero-shot**: Sem exemplos específicos do domínio
3. **Categorias ambíguas**: "Outros" é catch-all, "Política" permeia tudo
4. **Variantes sintéticas**: 75% do dataset são trechos truncados (mais difícil)

### Melhorias Possíveis
- [ ] **Few-shot prompts**: Incluir 3-5 exemplos por categoria (+5-10% accuracy esperado)
- [ ] **Chain-of-Thought**: Raciocínio explícito para casos ambíguos
- [ ] **Fine-tuning**: Modelos menores (Llama, Mistral) podem superar GPT com fine-tune
- [ ] **Ensemble**: Combinar predições de 2-3 modelos (voting)
- [ ] **Dataset maior**: Usar govbrnews_recent_10000 com categorias refinadas

## 🔍 Modelos que Falharam

5 modelos não funcionaram devido a restrições de acesso AWS Bedrock:

- Claude Sonnet 4.6, Haiku 4.5 (requerem inference profiles)
- Mistral Large 3 (on-demand não habilitado)
- Llama 3 70B, 8B (acesso não disponível na conta)
- Cohere Command R+ (throttling)
- Ministral 3 8B (on-demand não habilitado)

**Solução:** Lista atualizada com modelos ON_DEMAND confirmados

## 📝 Logs e Debug

Todos os logs de execução estão em:
- `results/llm_evaluation/run_final.log` - Log completo da última execução
- `results/llm_evaluation/comparison_full.json` - Predições individuais de todos os modelos

## 🎓 Aprendizados

1. **AWS Bedrock é complexo**: Nem todos model IDs funcionam via on-demand, alguns requerem inference profiles
2. **Amazon Nova é competitiva**: Família Nova oferece excelente custo-benefício
3. **Claude lidera em quality**: Mas o gap vs modelos mais baratos é pequeno (51% vs 45.5% = 11% diferença)
4. **Zero-shot é suficiente**: Para classificação simples, zero-shot entrega 45-51% accuracy
5. **Custo varia 100x**: De $0.004 (Nova Micro) a $0.46 (Claude Sonnet) para mesma tarefa

## 📚 Referências

- [AWS Bedrock Model IDs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
- [Anthropic Prompt Engineering](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [Amazon Nova Documentation](https://docs.aws.amazon.com/nova/)

---

**Issue:** #3  
**Status:** ✅ Completo  
**Data:** 2026-04-27  
**Custo Total:** $0.61 USD  
**Tempo:** ~16 minutos de execução
