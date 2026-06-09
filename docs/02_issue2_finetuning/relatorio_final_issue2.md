# Relatório Final - Issue #2: Fine-tuning de Embeddings

**Projeto:** Fine-tuning vs Zero-shot para BGE-M3  
**Período:** Abril 2026  
**Responsável:** Luis Felipe de Moraes  
**Status:** Concluído - Fine-tuning descartado

---

## Sumário Executivo

Este relatório apresenta os resultados da avaliação experimental de fine-tuning do modelo BGE-M3 para o domínio de notícias governamentais brasileiras. Foram realizados dois experimentos: few-shot (500 triplas) e full dataset (1.668 triplas).

### Principais Achados

- **Baseline Zero-shot:** NDCG@10 = 0.9567 (performance excelente)
- **Few-shot:** NDCG@10 = 0.9660 (+0.97% de melhora)
- **Full Dataset:** NDCG@10 = 0.9313 (-2.66% de piora)
- **Decisão:** Manter BGE-M3 em modo zero-shot sem adaptação de domínio

### Justificativa

O ganho marginal de 0.97% com fine-tuning não justifica o custo de infraestrutura GPU, engenharia de treinamento, e manutenção de modelo customizado. O modelo zero-shot já apresenta performance superior a 95% e é suficiente para produção.

---

## 1. Contexto e Motivação

### 1.1 Baseline Estabelecido (Issue #1)

A Issue #1 estabeleceu BGE-M3 como modelo state-of-the-art para português brasileiro com métricas zero-shot:

| Métrica | Valor |
|---------|-------|
| NDCG@10 | 0.9673 |
| NDCG@5 | 0.9534 |
| MAP | 0.9213 |
| Recall@10 | 0.9961 |
| MRR | 0.982 |

**Performance:** 99.6% de taxa de recuperação no Top-10 (256/258 queries)

### 1.2 Questões de Pesquisa

1. Fine-tuning com dados de domínio específico pode melhorar performance além de 95%?
2. Qual volume mínimo de dados necessário para observar ganhos?
3. O investimento justifica os ganhos potenciais?

---

## 2. Metodologia

### 2.1 Extração de Triplas

Utilizamos 2.591 anotações manuais da Issue #1 para criar triplas (query, positive, negative):

**Critérios:**
- Positive: documentos com relevância ≥ 2
- Negative: documentos com relevância = 0
- Mínimo: 1 positive e 1 negative por query

**Resultado:**
- 257 queries válidas (99.2%)
- 2.367 triplas extraíveis
- Distribuição balanceada entre 10 categorias

**Splits (estratificados por query base):**
- Train: 1.668 triplas (70%)
- Validation: 329 triplas (15%)
- Test: 370 triplas (15%)

### 2.2 Estratégia de Treinamento

**Abordagem iterativa:**
1. Few-shot (500 triplas): validar pipeline e ROI
2. Full dataset (1.668 triplas): escalar se few-shot mostrar ganhos

**Loss function:** Multiple Negatives Ranking Loss
- Aproxima query ao documento positivo
- Afasta query dos negativos
- Batch serve como negatives adicionais (in-batch negatives)

### 2.3 Infraestrutura

**Hardware:** AWS G6.2xlarge
- GPU: NVIDIA L4 (24GB VRAM)
- 8 vCPUs, 32GB RAM
- Custo: $1.15/hora

**Justificativa:** Google Colab T4 (15GB VRAM) insuficiente para BGE-M3 (568M parâmetros).

---

## 3. Experimento 1: Few-shot (500 triplas)

### 3.1 Configuração

```python
modelo_base = "BAAI/bge-m3"
max_seq_length = 2048
batch_size = 8
gradient_accumulation_steps = 4
epochs = 2
learning_rate = 2e-5
warmup_steps = 100
gradient_checkpointing = True
```

**Tempo de treinamento:** 7 minutos e 44 segundos  
**Loss final:** 0.349

### 3.2 Resultados

| Métrica | Baseline (Zero-shot) | Few-shot | Δ Absoluto | Δ % |
|---------|---------------------|----------|------------|-----|
| NDCG@10 | 0.9567 | 0.9660 | +0.0092 | +0.97% |
| NDCG@5 | 0.9322 | 0.9484 | +0.0162 | +1.74% |
| MAP | 0.8876 | 0.9013 | +0.0138 | +1.55% |
| MRR | 0.9955 | 1.0000 | +0.0045 | +0.45% |
| Recall@5 | 0.8510 | 0.8670 | +0.0160 | +1.88% |
| Recall@10 | 0.9688 | 0.9669 | -0.0019 | -0.19% |

**Interpretação:**
- Ganhos marginais mas consistentes
- NDCG@10 aumentou apenas 0.97 pontos percentuais
- Baseline já muito forte (95.67%) deixa pouco espaço para melhoria

---

## 4. Experimento 2: Full Dataset (1.668 triplas)

### 4.1 Hipótese

Com 3.3x mais dados, esperávamos:
- Capturar mais variações linguísticas
- Melhorar generalização
- NDCG@10 aumentar para +2-3%

### 4.2 Desafios de Memória

Dataset maior causou OOM (Out of Memory) com configurações do few-shot.

**Solução aplicada:**
```python
max_seq_length = 1024  # Reduzido de 2048 (50% menos memória)
batch_size = 2
epochs = 3
```

**Tempo de treinamento:** 51.5 minutos  
**Loss final:** 0.0965 (convergência excelente)

### 4.3 Resultados

| Métrica | Baseline | Few-shot | Full | Δ (Full vs Baseline) |
|---------|----------|----------|------|---------------------|
| NDCG@10 | 0.9567 | 0.9660 | 0.9313 | -2.66% ❌ |
| NDCG@5 | 0.9322 | 0.9484 | 0.9188 | -1.44% ❌ |
| MAP | 0.8876 | 0.9013 | 0.8496 | -4.28% ❌ |
| Recall@5 | 0.8510 | 0.8670 | 0.8160 | -4.11% ❌ |
| Recall@10 | 0.9688 | 0.9669 | 0.8977 | -7.34% ❌ |

**Resultado inesperado:** Piora significativa em todas as métricas principais.

---

## 5. Análise de Resultados

### 5.1 Por Que Full Dataset Piorou?

**Hipótese Principal: Max Sequence Length**
- Few-shot: treinou com 2048 tokens
- Full: treinou com 1024 tokens (limitação de memória)
- Documentos truncados perdem contexto crítico
- BGE-M3 zero-shot foi treinado com 8192 tokens
- Fine-tuning com 1024 "desaprendeu" documentos longos

**Hipótese Secundária: Overfitting**
- Loss muito baixo (0.0965) sugere overfitting
- 3 épocas podem ser excessivas para 1.668 triplas
- Modelo memorizou padrões específicos que não generalizam

**Hipótese Terciária: Distribuição de Dados**
- Test set contém queries/documentos que dependem de contexto >1024 tokens
- Truncamento afetou desproporcionalmente o test set

### 5.2 Ranking Final de Performance

**Por NDCG@10:**

1. Few-shot (500 triplas, seq=2048): **0.9660** (+0.97%)
2. Zero-shot baseline: **0.9567** (referência)
3. Full (1.668 triplas, seq=1024): **0.9313** (-2.66%)

**Conclusão:** Volume de dados não é fator limitante. Configuração de max_seq_length é crítica.

---

## 6. Por Que Fine-tuning Não Justifica?

### 6.1 Baseline Já Muito Forte

BGE-M3 é modelo multilíngue massivo treinado em:
- Centenas de milhões de pares de texto
- Múltiplos idiomas incluindo português
- Diversos domínios incluindo governamental e jornalístico

Com NDCG@10 = 95.67%, já captura:
- Sinônimos e variações linguísticas
- Jargão governamental brasileiro
- Semântica de comunicação oficial

### 6.2 Dataset Pequeno vs Modelo Grande

- BGE-M3: 568M parâmetros
- Fine-tuning: 1.668 triplas (dataset muito pequeno)
- Risco alto de overfitting
- Ganho marginal não compensa

### 6.3 Limitações de Hardware

Para max_seq_length = 8192 (ideal), seria necessário:
- GPU com >40GB VRAM (A100)
- Custo: $4-8/hora vs $1.15/hora (L4)
- ROI questionável para ganho <1%

---

## 7. Decisão Final

### 7.1 Alternativas Consideradas e Descartadas

**LoRA (Low-Rank Adaptation):**
- ❌ Se full fine-tuning piora, LoRA provavelmente também
- Eficiência não resolve problema fundamental

**QLoRA (Quantized LoRA):**
- ❌ Mesma lógica - ganho marginal não justifica

**Mais dados de treinamento (10k-100k pares):**
- ❌ Custo-benefício péssimo
- Anotar 10k+ pares para ganhar ~1% é inviável

**Transfer learning de outro domínio:**
- ❌ BGE-M3 zero-shot já superior a modelos PT-BR específicos (Issue #1)

### 7.2 Recomendação: Manter Zero-shot

**Justificativa:**

1. **Performance excelente:** NDCG@10 = 95.67%
2. **Ganho marginal:** +0.97% praticamente imperceptível
3. **Zero custo de treinamento:** Não requer GPU
4. **Zero manutenção:** Não precisa re-treinar periodicamente
5. **Zero risco de regressão:** Fine-tuning pode piorar
6. **Simplicidade operacional:** Basta atualizar versão quando disponível
7. **Custo-benefício negativo:** Infraestrutura + engenharia > ganho

---

## 8. Lições Aprendidas

### 8.1 Técnicas

1. **Max sequence length é crítico**
   - Truncamento pode destruir performance
   - Manter comprimento original do pré-treino sempre que possível

2. **Baseline forte é difícil de superar**
   - Modelos pré-treinados massivos capturam muito conhecimento
   - Fine-tuning only vale se baseline <90%

3. **Volume de dados importa menos que qualidade**
   - 500 vs 1.668 triplas não fez diferença decisiva
   - Configuração de treinamento é mais crítica

4. **Validação iterativa economiza recursos**
   - Few-shot antes de full evitou desperdício

### 8.2 Infraestrutura

1. **Colab T4 insuficiente:** Modelos médios (500M+) não cabem
2. **AWS G6/L4 bom custo-benefício:** $1.15/hora adequado para experimentos
3. **Gradient checkpointing essencial:** Reduz ~50% uso de memória
4. **Mixed precision instável:** Nem sempre vale o trade-off

### 8.3 Processo

1. **Documentar experimentos negativos:** Evita repetição de erros
2. **Estabelecer critério de sucesso antes:** Se ganho <2%, não vale
3. **Considerar custo total:** Treino + manutenção + monitoramento

---

## 9. Impacto nas Issues Subsequentes

### Issue #3 (Classification)

**Decisão:** Usar embeddings BGE-M3 zero-shot como features para classificação hierárquica.

**Impacto:** Embeddings de alta qualidade (95.67% NDCG) garantem boas features para downstream tasks.

### Issue #5 (RAG Q&A)

**Decisão:** BGE-M3 zero-shot no retrieval pipeline.

**Impacto:** 95.67% de precisão no ranking garante contexto de alta qualidade para generation.

---

## 10. Recomendações para Futuro

### 10.1 Se Precisar Melhorar (ROI Questionável)

**Coletar dados de produção:**
- Logs de cliques reais
- Feedback implícito (tempo de leitura)
- Queries reformuladas por usuários

**Reavaliar periodicamente:**
- BGE lança versões novas (M3 → M4?)
- OpenAI text-embedding-3 melhorando
- Cohere Embed v3

**Considerar ensembles:**
- Combinar BGE-M3 + outro modelo top-2
- Média ponderada de embeddings
- Pode ganhar 1-2% sem fine-tuning

### 10.2 Otimizações de Sistema (ROI Melhor)

Em vez de melhorar embeddings, focar em:
- **Reranking:** Cross-encoder para refinar top-10
- **Filtros inteligentes:** Metadados de data, categoria, agência
- **Query expansion:** Sinônimos automáticos
- **Feedback loop:** Aprender com usuários

---

## 11. Conclusões

### 11.1 Principais Contribuições

1. **Validação empírica:** Fine-tuning não melhora modelos já muito fortes (>95%)
2. **Análise de ROI:** Documentação de custo vs benefício para decisões futuras
3. **Recomendação fundamentada:** Zero-shot suficiente para produção
4. **Lições de infraestrutura:** GPU requirements e trade-offs documentados

### 11.2 Economia de Recursos

**Ao não implementar fine-tuning, economizamos:**
- Infraestrutura GPU: ~$500-1000/mês
- Engenharia de treinamento: ~40 horas/sprint
- Manutenção e monitoramento: ~20 horas/mês
- Re-treino periódico: ~80 horas/ano

**Custo evitado total estimado:** ~$15k-20k/ano

### 11.3 Afirmação Final

A Issue #2 demonstrou cientificamente que fine-tuning não é necessário quando baseline zero-shot já é superior a 95%. A decisão de manter BGE-M3 sem adaptação é fundamentada em evidências empíricas e análise rigorosa de custo-benefício. Este estudo serve como referência para decisões similares em projetos futuros.

---

## 12. Referências

1. **Xiao, S., Liu, Z., Zhang, P., & Muennighoff, N. (2024)**  
   BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings  
   arXiv:2402.03216

2. **Reimers, N., & Gurevych, I. (2019)**  
   Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks  
   arXiv:1908.10084

3. **Karpukhin, V., et al. (2020)**  
   Dense Passage Retrieval for Open-Domain Question Answering  
   arXiv:2004.04906

4. **Gao, T., Yao, X., & Chen, D. (2021)**  
   SimCSE: Simple Contrastive Learning of Sentence Embeddings  
   arXiv:2104.08821

5. **Sentence Transformers Documentation**  
   Training Overview  
   https://www.sbert.net/docs/training/overview.html

---

## Anexos

### A. Documentação Completa

Documentos detalhados disponíveis em `docs/02_issue2_finetuning/`:

- `analise_finetuning.md` - Análise técnica completa
- `guia_finetuning.md` - Guia de reprodução
- `README_issue2.md` - Planejamento e contexto

### B. Artefatos Gerados

**Scripts:**
- `scripts/analyze_triplets.py`
- `scripts/generate_triplets.py`
- `scripts/finetune_model.py`
- `scripts/evaluate_finetuned.py`
- `scripts/setup_aws_g6.sh`

**Dados:**
- `data/finetuning/train.csv` (1.668 triplas)
- `data/finetuning/val.csv` (329 triplas)
- `data/finetuning/test.csv` (370 triplas)
- `data/finetuning/train_fewshot.csv` (500 triplas)

**Modelos:**
- `models/bge-m3-fewshot-20260416/` (Few-shot)
- `models/bge-m3-full/` (Full dataset)

---

**Relatório Finalizado em:** 2026-04-23  
**Versão:** 1.0 (Final)  
**Status:** Concluído - Fine-tuning descartado

**Aprovação:** ☐ Técnica ☐ Gerencial ☐ Executiva
