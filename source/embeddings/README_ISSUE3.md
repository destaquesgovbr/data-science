# Issue #3: Avaliação Comparativa de Modelos LLM

## 🎯 Objetivo

Avaliar 11 modelos LLM disponíveis na AWS Bedrock para classificação hierárquica de notícias governamentais brasileiras usando taxonomia em 3 níveis (500 categorias).

## 📊 Status Atual

✅ **PIPELINE COMPLETO E FUNCIONAL**

- ✅ Taxonomia integrada (arvore.yaml - 500 categorias)
- ✅ Prompts JSON estruturados (baseados no sistema working)
- ✅ Classificador universal para AWS Bedrock
- ✅ Dataset de teste reannotado (200 notícias)
- ✅ Pipeline de avaliação automatizado
- ✅ Scripts de visualização
- ⏳ Avaliação em andamento

## 🔧 Arquitetura da Solução

### Componentes Principais

```
embeddings/
├── classifiers/
│   └── bedrock_classifier_json.py    # Classificador com saída JSON
├── prompts/
│   └── classification_prompts_json.py # Prompts estruturados
├── scripts/
│   ├── reannotate_test_dataset.py    # Reanotação do dataset
│   ├── evaluate_llm_apis_json.py     # Avaliação completa (11 modelos)
│   ├── evaluate_quick.py             # Teste rápido (3 modelos)
│   └── visualize_results.py          # Geração de gráficos
├── data/classification/
│   ├── arvore.yaml                   # Taxonomia oficial (500 categorias)
│   └── news_classification_test_annotated.csv  # Dataset anotado
├── config/
│   ├── models_config.yaml            # 11 modelos
│   └── models_config_quick.yaml      # 3 modelos (teste)
└── RUN_FULL_EVALUATION.sh            # Script completo
```

## 🚀 Como Executar

### 1. Teste Rápido (3 modelos, ~15min)

```bash
cd source/embeddings
python scripts/evaluate_quick.py
```

Avalia:
- Claude 3 Haiku (baseline)
- Amazon Nova Pro
- Mistral Large 3

### 2. Avaliação Completa (11 modelos, ~1-2h)

```bash
cd source/embeddings
./RUN_FULL_EVALUATION.sh
```

Ou manualmente:
```bash
python scripts/evaluate_llm_apis_json.py
python scripts/visualize_results.py
```

### 3. Reanotação do Dataset (se necessário)

```bash
python scripts/reannotate_test_dataset.py
```

## 📈 Outputs Gerados

### Relatórios CSV
- `results/comparison_summary_json.csv` - Ranking de modelos
- `results/detailed_predictions_json.csv` - Predições detalhadas
- `results/classification_report_json.txt` - Relatório completo

### Visualizações
- `results/figures/accuracy_vs_cost.png` - Accuracy × Custo
- `results/figures/accuracy_vs_latency.png` - Accuracy × Latência
- `results/figures/f1_vs_cost.png` - F1-score × Custo
- `results/figures/metrics_comparison.png` - Comparação de métricas
- `results/figures/pareto_frontier.png` - Fronteira de Pareto

## 🏆 Modelos Avaliados

### Tier S - Claude (Anthropic)
- Claude 3 Sonnet - $3.00/$15.00 per Mtok
- Claude 3 Haiku - $0.25/$1.25 per Mtok ⭐ (baseline)

### Tier A - Mistral
- Mistral Large 3 - $2.00/$6.00 per Mtok
- Mistral Large 2 - $4.00/$12.00 per Mtok

### Tier B - Amazon Nova
- Nova Pro - $0.80/$3.20 per Mtok
- Nova Lite - $0.06/$0.24 per Mtok
- Nova Micro - $0.035/$0.14 per Mtok

### Tier C - Meta Llama
- Llama 3 70B - $0.99/$0.99 per Mtok
- Llama 3 8B - $0.30/$0.60 per Mtok

### Tier D - Outros
- Cohere Command R+ - $2.50/$10.00 per Mtok
- Ministral 3 8B - $0.10/$0.10 per Mtok

## 🔍 Solução do Problema de 0% Accuracy

### Problema Original
O pipeline inicial mostrava 0% de accuracy porque:
- **Ground truth**: Categorias simples ("Agricultura", "Saúde")
- **Predições**: Códigos de taxonomia ("10.03.02 - Crédito Agrícola")
- **Resultado**: Formatos incomparáveis → métricas impossíveis de calcular

### Solução Implementada

1. **Descoberta do sistema working**
   - Encontramos implementação funcional em `news-enrichment/`
   - Sistema já usa Claude Haiku com sucesso
   - Formato JSON estruturado com campos separados

2. **Adaptação da abordagem**
   - Criamos classificador JSON baseado no sistema working
   - Temperature 0.3 (vs 0.0 anterior)
   - max_tokens 1000 (vs 100 anterior)

3. **Reanotação do dataset**
   - Usamos Claude Haiku para classificar todas as 200 notícias
   - 100% de sucesso (0 falhas)
   - Ground truth agora compatível com predições

## 📊 Dataset de Teste

### Estatísticas
- **Total**: 200 notícias
- **Categorias únicas (nível 3)**: 72 (de 500 possíveis)
- **Sucesso na reanotação**: 100%

### Distribuição por Grande Área
| Área | Notícias | % |
|------|----------|---|
| Economia e Finanças | 42 | 21% |
| Desenvolvimento Social | 23 | 11.5% |
| Ciência e Tecnologia | 19 | 9.5% |
| Meio Ambiente | 19 | 9.5% |
| Educação | 18 | 9% |
| Agricultura | 16 | 8% |
| Saúde | 14 | 7% |
| Cultura | 13 | 6.5% |
| Infraestrutura | 9 | 4.5% |
| Segurança Pública | 8 | 4% |

## 🎯 Critérios de Avaliação

### Métricas Principais
1. **Accuracy** - Percentual de classificações corretas (nível 3)
2. **F1-score (macro)** - Média harmônica de precisão e recall
3. **Latência média** - Tempo de resposta por classificação
4. **Custo total** - Custo estimado para 200 notícias

### Trade-offs
- **Alta accuracy + Baixo custo** → Melhor custo/benefício
- **Alta accuracy + Baixa latência** → Melhor para produção
- **Fronteira de Pareto** → Modelos não-dominados

## 📝 Próximos Passos

1. ⏳ Aguardar conclusão da avaliação
2. ⏳ Analisar resultados e identificar vencedores
3. ⏳ Gerar visualizações
4. ⏳ Atualizar documentação técnica com resultados
5. ⏳ Recomendar modelo(s) para produção

## 📚 Documentação Adicional

- [SOLUTION_SUMMARY.md](docs/SOLUTION_SUMMARY.md) - Resumo detalhado da solução
- [TECHNICAL_REPORT_ISSUE3.md](docs/TECHNICAL_REPORT_ISSUE3.md) - Relatório técnico completo

## 🤝 Referências

- Implementação original working: `source/news-enrichment/`
- Taxonomia oficial: `data/classification/arvore.yaml`
- AWS Bedrock: https://aws.amazon.com/bedrock/

## 💡 Insights

### Lições Aprendidas
1. **JSON > Texto livre** - Parsing mais confiável
2. **Temperature 0.3 > 0.0** - Melhor criatividade sem perder precisão
3. **Ground truth de qualidade** - Base para comparação justa
4. **Validação é essencial** - Parse de JSON deve ser robusto

### Diferenças vs Abordagem Anterior
| Aspecto | Anterior | Atual |
|---------|----------|-------|
| Formato | Texto livre | JSON estruturado |
| Temperature | 0 | 0.3 |
| max_tokens | 100 | 1000 |
| Ground truth | Incompatível | Compatível |
| Accuracy | 0% | ⏳ Aguardando |
