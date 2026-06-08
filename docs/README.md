# Documentação Consolidada - Projetos Data Science

**Branch:** doc-data-science  
**Data de Consolidação:** 2026-06-08  
**Status:** Documentação de 6 projetos/issues consolidada

---

## Visão Geral

Este diretório contém toda a documentação técnica consolidada dos projetos de Data Science desenvolvidos, organizados por issue/projeto com nomenclatura padronizada.

**Total de Documentos:** 74 arquivos  
**Páginas Estimadas:** ~1000-1500 páginas  
**Issues Documentadas:** 5 issues + 1 experimento

---

## Estrutura de Diretórios

```
docs/
├── README.md (este arquivo)
├── 01_issue1_embeddings/          # Issue #1: Embeddings PT-BR
├── 02_issue2_finetuning/          # Issue #2: Fine-tuning
├── 03_issue3_classification/      # Issue #3: Classificação LLM
├── 04_issue4_summarization/       # Issue #4: Sumarização
├── 05_issue5_rag/                 # Issue #5: RAG Q&A
├── 06_experiments_rag/            # Experimentos RAG
└── 99_infrastructure/             # Infraestrutura comum
```

---

## 01 - Issue #1: Embeddings PT-BR

**Objetivo:** Avaliar modelos de embedding para português brasileiro

**Relatório Final:**
- [relatorio_final_issue1.md](01_issue1_embeddings/relatorio_final_issue1.md) ⭐ **RELATÓRIO COMPLETO**

**Documentos principais:**
- [README_issue1.md](01_issue1_embeddings/README_issue1.md) - Comparativo de modelos
- [quickstart.md](01_issue1_embeddings/quickstart.md) - Guia rápido
- [roteiro_testes.md](01_issue1_embeddings/roteiro_testes.md) - Roteiro completo de testes
- [validacao_ranking.md](01_issue1_embeddings/validacao_ranking.md) - Validação externa

**Metodologia:**
- [metodologia_metricas.md](01_issue1_embeddings/metodologia_metricas.md) - Métricas (NDCG, MRR, MAP)
- [metodologia_ndcg.md](01_issue1_embeddings/metodologia_ndcg.md) - Explicação NDCG@10
- [metodologia_queries.md](01_issue1_embeddings/metodologia_queries.md) - Criação de queries

**Análises:**
- [analise_corpus.md](01_issue1_embeddings/analise_corpus.md) - Análise estatística
- [queries_expandidas.md](01_issue1_embeddings/queries_expandidas.md) - 259 variantes
- [validacao_ranking.md](01_issue1_embeddings/validacao_ranking.md) - Validação externa
- [papers_reading_list.md](01_issue1_embeddings/papers_reading_list.md) - Papers relevantes

**Decisões:**
- [decisao_corpus.md](01_issue1_embeddings/decisao_corpus.md) - 250 docs + 60 queries
- [changelog_queries.md](01_issue1_embeddings/changelog_queries.md) - Expansão para 259 queries

**Guias:** (subdiretório guias/)
- criacao_queries.md
- criacao_queries_85.md
- corpus_teste.md

**Total:** 16 arquivos

---

## 02 - Issue #2: Fine-tuning Embeddings

**Objetivo:** Fine-tuning de modelos de embedding

**Relatório Final:**
- [relatorio_final_issue2.md](02_issue2_finetuning/relatorio_final_issue2.md) ⭐ **RELATÓRIO COMPLETO**

**Documentos principais:**
- [README_issue2.md](02_issue2_finetuning/README_issue2.md) - Plano de fine-tuning
- [analise_finetuning.md](02_issue2_finetuning/analise_finetuning.md) - Análise fine-tuning vs zero-shot
- [guia_finetuning.md](02_issue2_finetuning/guia_finetuning.md) - Guia prático

**Total:** 4 arquivos

---

## 03 - Issue #3: Classificação com LLMs

**Objetivo:** Avaliar LLMs para classificação hierárquica de notícias

**Documentos principais:**
- [README_issue3.md](03_issue3_classification/README_issue3.md) - Avaliação comparativa
- [documento_principal.md](03_issue3_classification/documento_principal.md) - Documento central
- [relatorio_executivo_final.md](03_issue3_classification/relatorio_executivo_final.md) ⭐ **CRÍTICO**
- [relatorio_tecnico_completo.md](03_issue3_classification/relatorio_tecnico_completo.md) ⭐ **CRÍTICO**

**Solução:**
- [sumario_solucao.md](03_issue3_classification/sumario_solucao.md) - Sumário da solução
- [relatorio_avaliacao.md](03_issue3_classification/relatorio_avaliacao.md) - Relatório de avaliação

**Modelos Locais:**
- [modelos_locais.md](03_issue3_classification/modelos_locais.md) - Avaliação open source
- [plano_modelos_locais.md](03_issue3_classification/plano_modelos_locais.md) - Plano deployment
- [log_experimentos_locais.md](03_issue3_classification/log_experimentos_locais.md) - Log experimentos

**Contexto:**
- [contexto_projeto.md](03_issue3_classification/contexto_projeto.md) - Contexto geral (CLAUDE.md)

**Total:** 10 arquivos

---

## 04 - Issue #4: Sumarização

**Objetivo:** Sumarização automática de notícias governamentais

**Relatório Final:**
- [relatorio_final_issue4.md](04_issue4_summarization/relatorio_final_issue4.md) ⭐ **RELATÓRIO COMPLETO**

**Documentos principais:**
- [README_issue4.md](04_issue4_summarization/README_issue4.md) - Visão geral
- [experimento_completo.md](04_issue4_summarization/experimento_completo.md) ⭐ **CRÍTICO**
- [fase1_setup_log.md](04_issue4_summarization/fase1_setup_log.md) - Log execução

**Prompts:** (subdiretório prompts/)
- prompt_v2_fewshot.md
- prompt_v2.5_refined.md

**Avaliação Humana:** (subdiretório avaliacao_humana/)
- amostra_analise.md
- analise_llama_70b.md

**Total:** 8 arquivos

---

## 05 - Issue #5: RAG Q&A (EM PROGRESSO)

**Objetivo:** Sistema RAG para Q&A sobre notícias governamentais

**Status:** 60% concluído (7 de ~10 fases)

**Documentos principais:**
- [README_issue5.md](05_issue5_rag/README_issue5.md) - Visão geral completa ⭐
- [guia_setup.md](05_issue5_rag/guia_setup.md) - Setup geral
- [changelog.md](05_issue5_rag/changelog.md) - Registro de mudanças
- [tecnologias_explicadas.md](05_issue5_rag/tecnologias_explicadas.md) - Explicações técnicas

**Fases Implementadas:**
- [fase1_setup_indexacao.md](05_issue5_rag/fase1_setup_indexacao.md) - Setup e indexação
- [fase2_retrieval_pipeline.md](05_issue5_rag/fase2_retrieval_pipeline.md) - Retrieval pipeline
- [fase4_generation_pipeline.md](05_issue5_rag/fase4_generation_pipeline.md) - Generation pipeline
- [fase5_api_rest.md](05_issue5_rag/fase5_api_rest.md) - REST API
- [fase6_temporalidade.md](05_issue5_rag/fase6_temporalidade.md) - Features temporais
- [fase6_sumario.md](05_issue5_rag/fase6_sumario.md) - Sumário Fase 6
- [fase7_producao_ollama.md](05_issue5_rag/fase7_producao_ollama.md) ⭐ **CRÍTICO** - Deploy EC2 + análises

**Infraestrutura:**
- [migracao_hnsw.md](05_issue5_rag/migracao_hnsw.md) - Migração de índices

**Deploy:** (subdiretório deploy/)
- guia_deploy_ec2.md
- quickstart_ec2.md

**Benchmarks:** (subdiretório benchmarks/)
- benchmark_rerankers.md
- analise_reranking.md

**API:** (subdiretório api/)
- documentacao_api.md

**Total:** 17 arquivos (~200 páginas)

---

## 06 - Experimentos: RAG Comparison

**Objetivo:** Experimentos com RAG para classificação (abordagem híbrida)

**Documentos principais:**
- [comparacao_rag_vs_direto.md](06_experiments_rag/comparacao_rag_vs_direto.md) - RAG vs abordagem direta
- [comparacao_3_abordagens.md](06_experiments_rag/comparacao_3_abordagens.md) ⭐ **CRÍTICO**
- [sumario_executivo.md](06_experiments_rag/sumario_executivo.md) ⭐ **CRÍTICO** - 1 página

**Guias e Integração:**
- [quickstart_rag.md](06_experiments_rag/quickstart_rag.md) - Guia rápido
- [integracao_airflow.md](06_experiments_rag/integracao_airflow.md) - Integração Airflow
- [benchmark_curadoria.md](06_experiments_rag/benchmark_curadoria.md) - Benchmark curadoria

**Total:** 6 arquivos

---

## 99 - Infraestrutura

**Objetivo:** Documentação comum de infraestrutura e setup

### News Enrichment System
(subdiretório news_enrichment/)
- README.md - Sistema principal
- sistema_enriquecimento.md - Sistema completo
- resumo_executivo.md - Resumo executivo
- sistema_pronto.md - Sistema finalizado
- classificacao_sem_dataset.md - Classificação sem dataset

### Setup Guides
(subdiretório setup_guides/)
- setup_ambiente.md
- configuracao_repositorio.md
- configuracao_aws.md
- quickstart_bedrock.md
- instalacao_ollama.md
- guia_poetry.md

### Documentação Interna
(subdiretório documentacao_interna/)
- documentacao_sistema.md
- documentacao_prompts.md
- resultados_testes.md

**Total:** 14 arquivos

---

## Documentos Críticos para Prestação de Contas

### Relatórios Executivos (Prioridade Máxima)

1. **Issue #1:**
   - [relatorio_final_issue1.md](01_issue1_embeddings/relatorio_final_issue1.md) ⭐

2. **Issue #2:**
   - [relatorio_final_issue2.md](02_issue2_finetuning/relatorio_final_issue2.md) ⭐

3. **Issue #3:**
   - [relatorio_executivo_final.md](03_issue3_classification/relatorio_executivo_final.md) ⭐
   - [relatorio_tecnico_completo.md](03_issue3_classification/relatorio_tecnico_completo.md) ⭐

4. **Issue #4:**
   - [relatorio_final_issue4.md](04_issue4_summarization/relatorio_final_issue4.md) ⭐

5. **Issue #5:**
   - [README_issue5.md](05_issue5_rag/README_issue5.md) (status e progresso)
   - [fase7_producao_ollama.md](05_issue5_rag/fase7_producao_ollama.md) (análises comparativas)

6. **Experimentos RAG:**
   - [comparacao_3_abordagens.md](06_experiments_rag/comparacao_3_abordagens.md)
   - [sumario_executivo.md](06_experiments_rag/sumario_executivo.md) (1 página)

### Relatórios Técnicos (Prioridade Alta)

1. [fase2_retrieval_pipeline.md](05_issue5_rag/fase2_retrieval_pipeline.md) - Retrieval detalhado
2. [comparacao_rag_vs_direto.md](06_experiments_rag/comparacao_rag_vs_direto.md) - Comparação técnica
3. [benchmark_rerankers.md](05_issue5_rag/benchmarks/benchmark_rerankers.md) - Benchmarks

### Metodologias (Referência)

1. [metodologia_metricas.md](01_issue1_embeddings/metodologia_metricas.md)
2. [metodologia_queries.md](01_issue1_embeddings/metodologia_queries.md)
3. [papers_reading_list.md](01_issue1_embeddings/papers_reading_list.md)

---

## Nomenclatura Padronizada

**Padrão adotado:**
- `README_issueN.md` - Documento principal de cada issue
- Nomes em minúsculas com underscores: `nome_do_arquivo.md`
- Prefixos descritivos: `metodologia_`, `analise_`, `guia_`, `relatorio_`
- Sufixos específicos quando necessário: `_completo`, `_final`, `_executivo`

**Categorias de documentos:**
- `README_` - Documentos principais de overview
- `relatorio_` - Relatórios técnicos ou executivos
- `metodologia_` - Documentação de metodologias
- `guia_` - Guias práticos e tutoriais
- `analise_` - Análises e comparações
- `experimento_` - Documentação de experimentos
- `fase#_` - Fases de implementação (Issue #5)

---

## Estatísticas

| Métrica | Valor |
|---------|-------|
| **Total de Arquivos** | 76 |
| **Issues Documentadas** | 5 (completas) |
| **Relatórios Finais** | 4 (Issues #1, #2, #3, #4) |
| **Experimentos** | 1 (RAG Comparison) |
| **Páginas Estimadas** | 1200-1700 |
| **Maior Projeto** | Issue #5 (17 docs, ~200 páginas) |
| **Mais Completo** | Issue #3 (relatórios executivo + técnico) |

---

## Origem dos Documentos

Documentação consolidada das seguintes branches:
- `main` - Infraestrutura base
- `embeddings-study` - Issue #1
- `issue2` - Issue #2 (Fine-tuning)
- `issue3` - Issue #3 (Classification)
- `issue4` - Issue #4 (Summarization)
- `issue5` - Issue #5 (RAG Q&A)
- `ragintheloop` - Experimentos RAG

---

## Manutenção

**Branch de documentação:** `doc-data-science`  
**Última atualização:** 2026-06-08  
**Responsável:** Luis Felipe de Moraes

**Nota:** Os conteúdos dos documentos não foram alterados, apenas organizados e renomeados para padronização.

**Relatórios Finais Criados:**
- Issue #1: ✅ relatorio_final_issue1.md
- Issue #2: ✅ relatorio_final_issue2.md  
- Issue #3: ✅ relatorio_executivo_final.md + relatorio_tecnico_completo.md
- Issue #4: ✅ relatorio_final_issue4.md
- Issue #5: 🔄 Em progresso (fases 1-7 documentadas)

---

## Navegação Rápida

### Por Tipo de Documento

**Relatórios Executivos:**
- [Issue #3 - Relatório Final](03_issue3_classification/relatorio_executivo_final.md)
- [RAG - Sumário Executivo](06_experiments_rag/sumario_executivo.md)
- [RAG - Comparação 3 Abordagens](06_experiments_rag/comparacao_3_abordagens.md)

**Relatórios Técnicos:**
- [Issue #3 - Relatório Técnico](03_issue3_classification/relatorio_tecnico_completo.md)
- [Issue #5 - Fase 7 Produção](05_issue5_rag/fase7_producao_ollama.md)
- [Issue #4 - Experimento Completo](04_issue4_summarization/experimento_completo.md)

**Guias de Implementação:**
- [Issue #1 - Quick Start](01_issue1_embeddings/quickstart.md)
- [Issue #2 - Guia Fine-tuning](02_issue2_finetuning/guia_finetuning.md)
- [Issue #5 - Guia Setup](05_issue5_rag/guia_setup.md)

**Metodologias:**
- [Metodologia de Métricas](01_issue1_embeddings/metodologia_metricas.md)
- [Metodologia NDCG](01_issue1_embeddings/metodologia_ndcg.md)
- [Metodologia Queries](01_issue1_embeddings/metodologia_queries.md)

---

**Documento gerado em:** 2026-06-08  
**Versão:** 1.0
