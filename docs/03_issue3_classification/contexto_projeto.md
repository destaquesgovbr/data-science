# Data Science Workspace - Contexto do Projeto

> **Última atualização:** 2026-04-30  
> **Responsável:** Luis Felipe de Moraes - Cientista de Dados CPQD  
> **Repo:** [github.com/destaquesgovbr/data-science](https://github.com/destaquesgovbr/data-science)

---

## 🎯 O que é este Projeto?

Workspace de Data Science focado em **notícias governamentais brasileiras** (domínio gov.br), com pesquisas sobre embeddings, LLMs e classificação automática de conteúdo.

**Domínio:** Textos governamentais em português brasileiro  
**Objetivo:** Avaliar técnicas de ML/NLP para classificação, retrieval e enriquecimento de notícias  
**Stack:** Python 3.9+, Poetry, PyTorch, Transformers, AWS Bedrock, Ollama

---

## 📊 Status Atual - Issue #3 (Branch: `issue3`)

### Issue #3: Avaliação Comparativa de LLMs para Classificação

**Objetivo:** Comparar LLMs (APIs comerciais vs open source local) para classificar notícias em taxonomia hierárquica de 500 categorias (3 níveis).

**Status:** 🔄 **Fase 3 em andamento** - Avaliação de modelos open source locais

#### Fases Concluídas

**✅ Fase 1: APIs Comerciais (AWS Bedrock)**
- 7 modelos testados (Claude, Nova, Mistral)
- **Melhor:** Claude 3 Sonnet (51% accuracy, $0.46/200 notícias)
- **Melhor custo-benefício:** Amazon Nova Micro (45.5%, $0.004/200 notícias)
- Dataset: 200 notícias, 10 categorias simples
- Resultados: [EVALUATION_REPORT.md](source/embeddings/results/llm_evaluation/EVALUATION_REPORT.md)

**✅ Fase 2: Taxonomia Hierárquica (500 categorias, 3 níveis)**
- Migração: 10 categorias → 500 categorias hierárquicas (árbol.yaml)
- Dataset reannotado com Claude Haiku via API
- Formato: JSON estruturado (compatível com sistema working `news-enrichment/`)
- **Melhor resultado:** Claude Haiku - **80.5% accuracy L3**, $97/mês (@1k classificações/dia)
- Insight: Haiku (médio) superou Sonnet (premium) em 2.4x!

**🔄 Fase 3: Modelos Open Source Locais (ATUAL)**
- **Objetivo:** Avaliar viabilidade técnica/econômica de deployment local vs APIs
- **8 modelos selecionados:**
  - Tier B (7-15B): Llama 3.1 8B, Mistral 7B, Qwen 2.5 14B, Gemma 2 9B, Phi-4 14B
  - Tier C (2-4B): Llama 3.2 3B, Phi-3.5 Mini, Gemma 2 2B
- **Tecnologia:** Ollama (serving local), quantização Q4_K_M
- **Infraestrutura:** Scripts prontos, configs criadas
- **Status:** ⏳ Aguardando execução completa da avaliação

#### Próximos Passos Imediatos

1. **Executar avaliação completa:**
   ```bash
   cd source/embeddings
   python scripts/evaluate_local_models.py  # ~2-4h
   ```

2. **Comparar resultados:** Local vs API
   ```bash
   python scripts/compare_local_vs_api.py
   ```

3. **Decisão final:** Qual estratégia usar em produção?
   - Se accuracy local >60%: Considerar deployment local para volumes >5k/dia
   - Se accuracy local <50%: Manter APIs (Haiku)

4. **Documentar e fechar Issue #3**

---

## 🗂️ Estrutura do Projeto (Mapa de Navegação)

```
data-science/
├── CLAUDE.md                    # 👈 ESTE ARQUIVO (contexto para Claude)
├── README.md                    # Overview geral do workspace
├── pyproject.toml               # Poetry dependencies
│
├── source/
│   ├── embeddings/              # 🎯 ISSUE #1, #2, #3 - FOCO ATUAL
│   │   ├── README.md            # Issue #1 overview
│   │   ├── README_ISSUE3.md     # Issue #3 status geral
│   │   ├── README_LOCAL_MODELS.md  # Guia de modelos locais (Fase 3)
│   │   ├── ISSUE_3_LLM_CLASSIFICATION.md  # Resumo Fase 1 (APIs)
│   │   │
│   │   ├── classifiers/         # Implementações
│   │   │   ├── bedrock_classifier_json.py  # AWS Bedrock (Fase 1/2)
│   │   │   └── local_classifier.py         # Ollama (Fase 3)
│   │   │
│   │   ├── prompts/
│   │   │   └── classification_prompts_json.py  # Templates JSON estruturados
│   │   │
│   │   ├── scripts/             # 🚀 EXECUTAR DAQUI
│   │   │   ├── evaluate_llm_apis_json.py      # Fase 2 (APIs + taxonomia)
│   │   │   ├── evaluate_local_models.py       # Fase 3 (local) - PRÓXIMO
│   │   │   ├── compare_local_vs_api.py        # Comparação final
│   │   │   ├── setup_local_models.sh          # Baixar modelos Ollama
│   │   │   └── test_local_quick.py            # Validação rápida (3 modelos)
│   │   │
│   │   ├── config/
│   │   │   ├── models_config.yaml             # APIs (11 modelos)
│   │   │   └── local_models_config.yaml       # Local (8 modelos)
│   │   │
│   │   ├── data/classification/
│   │   │   ├── arvore.yaml                    # Taxonomia 500 categorias
│   │   │   └── news_classification_test_annotated.csv  # 200 notícias
│   │   │
│   │   ├── results/
│   │   │   ├── llm_evaluation/                # Fase 1 (APIs simples)
│   │   │   ├── comparison_summary_json.csv    # Fase 2 (taxonomia)
│   │   │   └── local_models/                  # Fase 3 (será gerado)
│   │   │
│   │   ├── docs/                              # 📚 DOCUMENTAÇÃO TÉCNICA
│   │   │   ├── TECHNICAL_REPORT_ISSUE3.md     # Relatório completo (263+ linhas)
│   │   │   ├── PLAN_LOCAL_MODELS.md           # Plano detalhado Fase 3
│   │   │   ├── SOLUTION_SUMMARY.md            # Resumo da solução
│   │   │   └── [outros 10+ docs]
│   │   │
│   │   └── notebooks/
│   │       └── federated_learning_demo.ipynb  # ⚠️ NÃO FAZ PARTE DA ISSUE #3
│   │
│   ├── news-enrichment/         # Sistema de classificação WORKING (base de referência)
│   │   └── (implementação já em produção)
│   │
│   └── data/                    # Corpus de notícias gov.br
│
└── [outros arquivos config]
```

---

## 📝 Histórico de Issues

| Issue | Título | Status | Branch | Aprendizado Chave |
|-------|--------|--------|--------|-------------------|
| #1 | Comparativo Embeddings PT-BR | ✅ Fechada | `embeddings-study` | BGE-M3 venceu, modelos PT-BR não superaram multilíngues |
| #2 | Fine-tuning vs Zero-shot | ✅ Fechada | `issue2` | Fine-tuning dá +10-15% NDCG, mas zero-shot é 90% do resultado |
| #3 | LLMs para Classificação | 🔄 Aberta | `issue3` | Haiku (médio) > Sonnet (premium), modelos locais podem compensar |

**Issues futuras planejadas:** #5 (RAG), #6 (Sentiment), #7 (NER), #8 (Storage), #9 (Pipeline), #10 (Tendências)

---

## 🧠 Decisões Importantes (Contexto Histórico)

### Por que JSON estruturado?

**Problema:** Fase 1 tinha 0% accuracy porque ground truth era "Agricultura" e modelos retornavam "10.03.02 - Crédito Agrícola" (formato incompatível).

**Solução:** Formato JSON com campos separados:
```json
{
  "nivel1": "Economia e Finanças",
  "nivel2": "Agricultura",
  "nivel3": "Crédito Agrícola",
  "codigo": "10.03.02",
  "confianca": 0.85
}
```

Baseado no sistema working de `news-enrichment/`.

### Por que Haiku e não Sonnet?

**Fase 1:** Sonnet teve 51% vs Haiku 48% (margem pequena)  
**Fase 2 (taxonomia):** Haiku **80.5%** vs Sonnet **33.5%** (inversão!)

**Hipótese:** Modelos menores têm melhor "fit" para tarefas específicas. Sonnet pode estar "over-thinking".

### Por que focar em modelos médios (7-15B)?

- Llama 3 70B via Bedrock teve 0% accuracy (suspeita de problema de API)
- Hardware para 70B é 8-10x mais caro (A100 80GB vs A10G 24GB)
- Experiência com APIs mostrou que médio > grande para esta tarefa
- Modelos 7-15B cabem confortavelmente em g5.xlarge ($434/mês reserved)

### Por que Ollama?

- Open source, simples de instalar
- Suporta quantização (Q4_K_M reduz VRAM em 8x, ~2-5% accuracy loss)
- API compatível com OpenAI (fácil migração)
- Comunidade ativa, modelos pré-quantizados disponíveis

---

## 🚀 Comandos Úteis (Atalhos)

### Issue #3 - Fase 3 (Modelos Locais)

```bash
# 1. Verificar se Ollama está rodando
curl http://localhost:11434/api/tags

# 2. Baixar todos os 8 modelos (~40-60GB)
cd source/embeddings
./scripts/setup_local_models.sh

# 3. Teste rápido (3 modelos, 10 notícias, ~2-5min)
python scripts/test_local_quick.py

# 4. Avaliação completa (8 modelos, 200 notícias, ~2-4h)
python scripts/evaluate_local_models.py

# 5. Comparar local vs API
python scripts/compare_local_vs_api.py

# 6. Ver resultados
cat results/local_models/comparison_summary.csv
```

### Git

```bash
# Ver status da branch issue3
git status

# Ver histórico de commits
git log --oneline -10

# Criar commit
git add <arquivos>
git commit -m "feat: descrição"

# Comparar com main
git diff main..issue3 --stat
```

### Ambiente

```bash
# Ativar Poetry
poetry shell

# Instalar dependências
poetry install --with dev

# Jupyter Lab
jupyter lab source/embeddings/notebooks/
```

---

## 💡 Dicas para Claude (IA Assistant)

### Quando eu pedir para "dar uma olhada no projeto":

1. Ler este arquivo primeiro (contexto rápido)
2. Verificar `git status` e `git log -3` (últimas mudanças)
3. Perguntar: "Onde você quer focar?" (Issue #3 atual vs outra coisa)

### Arquivos importantes para Issue #3:

- **Status geral:** `source/embeddings/README_ISSUE3.md`
- **Guia Fase 3:** `source/embeddings/README_LOCAL_MODELS.md`
- **Relatório técnico:** `source/embeddings/docs/TECHNICAL_REPORT_ISSUE3.md`
- **Scripts para executar:** `source/embeddings/scripts/evaluate_local_models.py`
- **Configs:** `source/embeddings/config/local_models_config.yaml`

### Arquivos que NÃO fazem parte da Issue #3:

- `source/embeddings/notebooks/federated_learning_demo.ipynb` (outro projeto)
- `source/news-enrichment/` (sistema working, apenas referência)

### Se eu pedir para "continuar de onde paramos":

**Estamos na Fase 3 da Issue #3:**
- ✅ APIs avaliadas (Haiku venceu com 80.5%)
- ✅ Infraestrutura local pronta (Ollama + 8 modelos configurados)
- ⏳ **PRÓXIMO PASSO:** Executar `evaluate_local_models.py` e comparar resultados

---

## 📞 Informações de Contato e Convenções

**Autor:** Luis Felipe de Moraes  
**Email:** lpmoraes@cpqd.com.br  
**Organização:** CPQD / Governo Federal (Destaques Gov.br)

**Convenções de Commit:**
- `feat:` - Nova funcionalidade
- `fix:` - Correção de bug
- `docs:` - Documentação
- `refactor:` - Refatoração sem mudança de comportamento

**Branch Strategy:**
- `main` - Código estável (issues finalizadas)
- `issue3` - Issue #3 em andamento (ATUAL)
- `embeddings-study` - Issue #1 (mesclada)
- `issue2` - Issue #2 (mesclada)

---

## 🎓 Aprendizados Chave (Para Futuras Issues)

1. **Documentação é rei** - Investir tempo em docs paga dividendos depois
2. **Baseline primeiro** - Sempre teste zero-shot antes de fine-tuning
3. **Médio pode ser melhor** - Modelos grandes nem sempre vencem
4. **Custo importa** - TCO analysis desde o início, não depois
5. **JSON > texto livre** - Parsing confiável é crítico para automação
6. **Ground truth de qualidade** - Métricas só fazem sentido com bom ground truth
7. **APIs para MVP, local para escala** - Break-even é ~5-10k classificações/dia

---

## 🔗 Links Úteis

**Documentação Externa:**
- [AWS Bedrock Model IDs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [Anthropic Prompt Engineering](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers)

**Repo GitHub:**
- [Issues](https://github.com/destaquesgovbr/data-science/issues)
- [Pull Requests](https://github.com/destaquesgovbr/data-science/pulls)

---

**Fim do contexto. Claude está pronto para trabalhar! 🚀**
