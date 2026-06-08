# Issue #2: Fine-tuning vs Zero-shot Analysis

## Sumário Executivo

Este documento detalha o processo experimental de fine-tuning do modelo BGE-M3 para embeddings de notícias governamentais brasileiras, realizado como parte da Issue #2 do projeto PBIA.

**Conclusão principal:** O modelo BGE-M3 em modo zero-shot apresenta desempenho excelente (NDCG@10 = 0.9567) para o domínio específico. Fine-tuning com dataset reduzido (500 triplas) trouxe ganho marginal de 0.97%, enquanto fine-tuning com dataset completo (1668 triplas) resultou em piora de 2.66%. A decisão é manter o modelo zero-shot sem adaptação de domínio.

---

## 1. Contexto e Motivação

### 1.1 Baseline Zero-shot

Na Issue #1, avaliamos 5 modelos de embedding em modo zero-shot (sem treinamento específico) usando 2.591 anotações manuais de relevância. O BGE-M3 obteve o melhor resultado:

- **NDCG@10:** 0.9673
- **NDCG@5:** 0.9534
- **MAP:** 0.9213
- **Recall@10:** 0.9961

### 1.2 Questões de Pesquisa

1. Fine-tuning com dados de domínio específico (jargão governamental, português brasileiro) pode melhorar o desempenho?
2. Qual volume de dados de treinamento é necessário para observar ganhos?
3. O investimento em infraestrutura de GPU e tempo de treinamento justifica os potenciais ganhos?

---

## 2. Metodologia

### 2.1 Extração de Triplas de Treinamento

Utilizamos as 2.591 anotações manuais da Issue #1 para extrair triplas no formato (query, positive, negative):

- **Positive:** documentos com relevância ≥ 2 (relevante ou muito relevante)
- **Negative:** documentos com relevância = 0 (não relevante)
- **Critério:** mínimo 1 positive e 1 negative por query

**Resultado da análise:**
- 257 queries válidas de 259 totais (99.2%)
- 2.367 triplas extraíveis
- Distribuição balanceada entre 10 categorias temáticas

Splits estratificados por query base (evitar data leakage entre variantes):
- **Train:** 1.668 triplas (70%)
- **Validation:** 329 triplas (15%)
- **Test:** 370 triplas (15%)

### 2.2 Estratégia de Treinamento

**Few-shot primeiro:** Criamos subset de 500 triplas (30% do treino) para:
1. Validar pipeline de treinamento
2. Estimar tempo e recursos computacionais
3. Verificar se volume reduzido já traz ganhos
4. Evitar desperdício de recursos se não houver melhora

**Full dataset depois:** Se few-shot mostrar ganhos, escalar para 1.668 triplas.

### 2.3 Configuração Técnica

**Modelo base:** BAAI/bge-m3
- Arquitetura: XLM-RoBERTa
- Dimensão: 1024
- Max sequence length: 8192 tokens (padrão)

**Loss function:** Multiple Negatives Ranking Loss
- Aproxima embedding de query ao positive
- Afasta embedding de query do negative
- Batch serve como negatives adicionais (in-batch negatives)

**Hardware:** AWS G6.2xlarge
- GPU: NVIDIA L4 (24GB VRAM)
- 8 vCPUs, 32GB RAM
- Custo: ~$1.15/hora

---

## 3. Experimento 1: Few-shot (500 triplas)

### 3.1 Desafios de Infraestrutura

**Tentativa inicial - Google Colab (T4 GPU):**
- OOM (Out of Memory) com batch sizes 16, 8 e 4
- T4 possui 15GB VRAM efetiva
- BGE-M3 requer: 2.3GB (modelo) + 2.3GB (gradientes) + 4.6GB (optimizer) + 3-5GB (activations) ≈ 14-16GB

**Otimizações testadas (todas falharam no Colab):**
- Gradient checkpointing (reduz activations)
- Mixed precision FP16
- Batch size mínimo (16/8/4/2/1)

**Solução:** Migração para AWS G6 com GPU L4 (24GB VRAM).

### 3.2 Configuração Final Few-shot

Após ajustes iterativos para caber na L4:

```python
max_seq_length = 2048/1024      # Reduzido de 8192, e mantém paridade com demais modelos também
batch_size = 8/4/2 # em conjuntom com o gradient_accumulation 
gradient_accumulation = 4/2 
epochs = 2/3/5 # Muitas épocas causaram overfitting aqui
learning_rate = 2e-5
warmup_steps = 100
gradient_checkpointing = True
use_amp = False            # Causou instabilidade
```

**Resultado do treinamento:**
- Tempo: 7 minutos e 44 segundos
- Loss final: 0.349
- GPU utilization: ~21GB/24GB

### 3.3 Avaliação Few-shot

**Métricas no test set (370 triplas):**

| Métrica | Baseline (Zero-shot) | Few-shot | Δ Absoluto | Δ % |
|---------|---------------------|----------|------------|-----|
| NDCG@5 | 0.9322 | 0.9484 | +0.0162 | +1.74% |
| NDCG@10 | 0.9567 | 0.9660 | +0.0092 | +0.97% |
| MAP | 0.8876 | 0.9013 | +0.0138 | +1.55% |
| MRR | 0.9955 | 1.0000 | +0.0045 | +0.45% |
| Recall@5 | 0.8510 | 0.8670 | +0.0160 | +1.88% |
| Recall@10 | 0.9688 | 0.9669 | -0.0019 | -0.19% |

**Interpretação:**
- Ganhos pequenos mas consistentes na maioria das métricas
- NDCG@10 subiu apenas 0.97 pontos percentuais (foi a principal métrica da Issue #1)
- Baseline já muito forte deixa pouco espaço para melhora
- 500 triplas parecem suficientes para capturar padrões básicos

---

## 4. Experimento 2: Full Dataset (1.668 triplas)

### 4.1 Hipótese

Com 3.3x mais dados de treinamento, esperávamos:
- Capturar mais variações linguísticas do domínio
- Melhorar generalização
- NDCG@10 aumentar de +0.97% para +2-3%, e assim justificaria o esforço extra

### 4.2 Desafios de Memória

**OOM com configuração few-shot:**
- Batch size 8: OOM durante treinamento
- Batch size 4: OOM durante treinamento
- Batch size 2: OOM durante treinamento

**Causa:** Dataset maior significa validation set maior, que consome memória durante avaliação periódica.

**Solução aplicada:**
```python
max_seq_length = 1024      # Reduzido de 2048 (50% menos memória)
batch_size = 2
epochs = 3
# Evaluator desabilitado durante treino
```

### 4.3 Resultado do Treinamento Full

- Tempo: 51.5 minutos
- Loss final: 0.0965 (convergência excelente)
- 1.251 steps totais (3 épocas)

### 4.4 Avaliação Full Dataset

**Métricas no test set:**

| Métrica | Baseline | Few-shot | Full | Δ (Full vs Baseline) |
|---------|----------|----------|------|---------------------|
| NDCG@5 | 0.9322 | 0.9484 | 0.9188 | -1.44% ❌ |
| NDCG@10 | 0.9567 | 0.9660 | 0.9313 | -2.66% ❌ |
| MAP | 0.8876 | 0.9013 | 0.8496 | -4.28% ❌ |
| MRR | 0.9955 | 1.0000 | 0.9949 | -0.06% |
| Recall@5 | 0.8510 | 0.8670 | 0.8160 | -4.11% ❌ |
| Recall@10 | 0.9688 | 0.9669 | 0.8977 | -7.34% ❌ |

**Resultado inesperado:** Piora significativa em todas as métricas principais.

---

## 5. Análise de Resultados

### 5.1 Por que Full Dataset Piorou?

**Hipótese 1: Max Sequence Length Diferente**
- Few-shot treinou com `max_seq_length = 2048`
- Full treinou com `max_seq_length = 1024` (necessário para caber na memória)
- Documentos truncados perdem contexto importante
- Queries longas do test set perdem informação crítica

**Hipótese 2: Overfitting**
- Loss muito baixo (0.0965) indica possível overfitting
- 3 épocas podem ser excessivas para dataset de 1.668 triplas
- Modelo pode ter memorizado padrões específicos do treino que não generalizam

**Hipótese 3: Distribuição de Dados**
- Test set pode conter queries/documentos mais longos que dependem de contexto >1024 tokens
- BGE-M3 zero-shot foi treinado com max_seq_length = 8192
- Fine-tuning com 1024 tokens "desaprendeu" como lidar com documentos longos

### 5.2 Comparativo Final

**Ranking de desempenho (NDCG@10):**

1. **Few-shot (500 triplas, seq=2048):** 0.9660 (+0.97%)
2. **Zero-shot baseline:** 0.9567 (referência)
3. **Full (1.668 triplas, seq=1024):** 0.9313 (-2.66%)

**Conclusão:** Volume de dados não é o fator limitante. Configuração de treinamento (principalmente max_seq_length) é crítica.

---

## 6. Discussão: Por que Fine-tuning Não Ajudou?

### 6.1 Baseline Já Muito Forte

O BGE-M3 é um modelo multilíngue massivo treinado em:
- Centenas de milhões de pares de texto
- Múltiplos idiomas incluindo português
- Diversos domínios incluindo texto governamental e jornalístico

Com NDCG@10 = 0.9567, o modelo já captura muito bem:
- Sinônimos e variações linguísticas
- Jargão governamental brasileiro
- Semântica de notícias e comunicação oficial

### 6.2 Dataset Pequeno vs Modelo Grande

- BGE-M3 possui ~568M parâmetros
- Fine-tuning com 1.668 triplas é volume muito pequeno
- Risco de overfitting ao invés de aprendizado de padrões gerais
- Few-shot (500) pode ter tido sorte na amostragem

### 6.3 Limitações de Hardware

Para explorar max_seq_length = 2048 ou 8192 no full dataset, seria necessário:
- GPU com >40GB VRAM (A100 ou superior)
- Custo: $4-8/hora vs $1.15/hora da L4
- Seria necessário um banco anotado muito maior para o treinamento ser proveitoso
- Ou técnicas mais avançadas (LoRA, QLoRA, gradient accumulation extremo)

---

## 7. Decisão: Não Prosseguir com Adaptação de Domínio

### 7.1 Alternativas Consideradas

**LoRA (Low-Rank Adaptation):**
- Treina apenas matrizes de baixo rank (muito menos parâmetros)
- Reduz uso de memória e risco de overfitting
- **Decisão:** Não prosseguir. Se full fine-tuning piora, LoRA provavelmente também piorará. A técnica é mais eficiente, mas não resolve problema fundamental de baseline já forte.

**QLoRA (Quantized LoRA):**
- Quantização + LoRA para ainda menos memória
- **Decisão:** Mesma lógica - eficiência não resolve problema de ganho marginal.

**Mais dados de treinamento:**
- Anotar 10k-100k pares query-documento
- **Decisão:** Custo-benefício péssimo. Para ganhar ~1% seria necessário esforço massivo de anotação.

**Transfer learning de outro domínio:**
- Usar modelo já fine-tunado em português legal/jurídico
- **Decisão:** Não explorado. BGE-M3 zero-shot já é suficiente e modelos treinados em pt-br se mostraram muito inferiores ao BGE-M3 na etapa anterior

### 7.2 Recomendação Final

**Manter BGE-M3 em modo zero-shot** pelos seguintes motivos:

1. **Desempenho excelente:** NDCG@10 = 0.9567 (95.67% de precisão no ranking)
2. **Melhora muito pequena** Em resultado já alto, praticamente passaria desapercebida
3. **Zero custo de treinamento:** Não requer GPU dedicada
4. **Zero acompanhamento de ciclo de vida do modelo** se implementado o fine tuning teria que ser revisto frequentemente
5. **Zero risco de regressão:** Fine-tuning pode piorar resultados
6. **Manutenção simples:** Basta atualizar versão do modelo quando disponível
7. **Ganho marginal não justifica investimento:** +0.97% vs custo de infraestrutura e engenharia

---

## 8. Lições Aprendidas

### 8.1 Técnicas

1. **Max sequence length é crítico:** Truncar documentos pode destruir desempenho
2. **Baseline forte é difícil de superar:** Modelos pré-treinados massivos capturam muito conhecimento
3. **Volume de dados importa menos que qualidade:** 500 vs 1668 triplas não fez diferença decisiva
4. **Validação iterativa economiza recursos:** Few-shot antes de full dataset evitou desperdício

### 8.2 Infraestrutura

1. **Colab T4 é insuficiente para fine-tuning de LLMs:** Mesmo modelos "médios" como BGE-M3 não cabem
2. **AWS G6/L4 é bom custo-benefício:** $1.15/hora, suficiente para experimentos
3. **Gradient checkpointing é essencial:** Reduz ~50% uso de memória, viabilizando testes com modelos médios a um custo acessível
4. **Mixed precision (AMP) pode causar instabilidade:** Nem sempre vale o tradeoff

### 8.3 Processo

1. **Documentação detalhada de experimentos negativos é valiosa:** Evita que outras equipes repitam erros
2. **Estabelecer critério de sucesso antes:** Se ganho <2%, não vale a pena
3. **Considerar custo total:** Não apenas treino, mas manutenção, monitoramento, re-treino periódico

---

## 9. Arquivos Gerados

### 9.1 Scripts

- `source/embeddings/scripts/analyze_triplets.py` - Análise de triplas extraíveis
- `source/embeddings/scripts/generate_triplets.py` - Geração de splits train/val/test
- `source/embeddings/scripts/finetune_model.py` - Pipeline de fine-tuning
- `source/embeddings/scripts/evaluate_finetuned.py` - Comparação com baseline
- `source/embeddings/scripts/setup_aws_g6.sh` - Setup automatizado de VM AWS

### 9.2 Dados

- `source/embeddings/data/finetuning/train.csv` - 1.668 triplas (70%)
- `source/embeddings/data/finetuning/val.csv` - 329 triplas (15%)
- `source/embeddings/data/finetuning/test.csv` - 370 triplas (15%)
- `source/embeddings/data/finetuning/train_fewshot.csv` - 500 triplas (subset estratificado)

### 9.3 Modelos

- `models/bge-m3-fewshot-20260416_090041/` - Few-shot (500 triplas, seq=2048)
- `models/bge-m3-full-<timestamp>/` - Full dataset (1.668 triplas, seq=1024)

### 9.4 Resultados

- `results/final_evaluation.json` - Few-shot vs baseline
- `results/full_evaluation.json` - Full vs baseline

---

## 10. Próximos Passos (Fora do Escopo Issue #2)

### 10.1 Se Precisar Melhorar Embeddings no Futuro

1. **Coletar mais dados de produção:**
   - Logs de cliques reais de usuários
   - Feedback implícito (tempo de leitura, compartilhamentos)
   - Queries reformuladas

2. **Reavaliar periodicamente:**
   - BGE lança versões novas (M3 → M4?)
   - OpenAI text-embedding-3 está melhorando
   - Cohere Embed v3 pode superar em português

3. **Considerar ensembles:**
   - Combinar BGE-M3 + outro modelo top-2
   - Média ponderada de embeddings
   - Pode ganhar 1-2% sem fine-tuning

### 10.2 Otimizações de Sistema

Em vez de melhorar embeddings, focar em:
- Reranking com modelo cross-encoder (NDCG@10 → NDCG@5)
- Filtros de metadados mais inteligentes
- Query expansion automática
- Feedback loop de usuários

---

## Referências

- [BGE-M3: Multi-Lingual, Multi-Functionality, Multi-Granularity](https://huggingface.co/BAAI/bge-m3)
- [Sentence Transformers - Training Overview](https://www.sbert.net/docs/training/overview.html)
- [Multiple Negatives Ranking Loss](https://www.sbert.net/docs/package_reference/losses.html#multiplenegativesrankingloss)
- Issue #1: METODOLOGIA_NDCG.md
- Issue #1: Resultados completos em `results/consolidated_results_with_ndcg.csv`

---

**Documento criado em:** 2026-04-23  
**Autor:** Luis Felipe de Moraes (com assistência de Claude Code)  
**Projeto:** INSPIRE 7
**Status:** Concluído - Fine-tuning descartado, manter zero-shot
