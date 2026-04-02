# Lista de Leitura - Embeddings PT-BR

> Papers, artigos e recursos para pesquisa de modelos de embedding

---

## Papers Essenciais (Prioridade Alta)

### 1. Fundamentos de Sentence Embeddings

- [ ] **Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks**
  - Autores: Reimers & Gurevych (2019)
  - Link: https://arxiv.org/abs/1908.10084
  - **Por quê**: Base fundamental para entender sentence embeddings com BERT
  - **Foco**: Arquitetura Siamese, pooling strategies, fine-tuning para similaridade

- [ ] **Making Monolingual Sentence Embeddings Multilingual using Knowledge Distillation**
  - Autores: Reimers & Gurevych (2020)
  - Link: https://arxiv.org/abs/2004.09813
  - **Por quê**: Entender como modelos multilinguais são criados
  - **Foco**: Knowledge distillation, teacher-student, alinhamento cross-lingual

### 2. Modelos State-of-the-Art

- [ ] **BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings**
  - Autores: BAAI (2024)
  - Link: https://arxiv.org/abs/2402.03216
  - **Por quê**: Um dos principais modelos multilinguais atuais
  - **Foco**: Multi-granularity (8k tokens), multi-functionality (dense/sparse/colbert)

- [ ] **Text Embeddings by Weakly-Supervised Contrastive Pre-training**
  - Autores: Wang et al. (E5) (2022)
  - Link: https://arxiv.org/abs/2212.03533
  - **Por quê**: E5 é referência em embeddings multilinguais
  - **Foco**: Contrastive learning, weak supervision

### 3. Modelos Específicos PT-BR

- [ ] **Open Sentence Embeddings for Portuguese with the Serafim PT* Encoders**
  - Autores: Gomes et al. (2024)
  - Link: https://arxiv.org/abs/2407.19527
  - **Por quê**: Modelo específico PT-BR state-of-the-art
  - **Foco**: Arquitetura, dados de treino PT, benchmark PT

- [ ] **Advancing Neural Encoding of Portuguese with Transformer Albertina PT-***
  - Autores: Rodrigues et al. (2023)
  - Link: https://arxiv.org/abs/2305.06721
  - **Por quê**: DeBERTa para português, base para embeddings
  - **Foco**: Arquitetura DeBERTa, dados PT, downstream tasks

- [ ] **BERTimbau: Pretrained BERT Models for Brazilian Portuguese**
  - Autores: Souza et al. (2020)
  - Link: https://arxiv.org/abs/2010.01327
  - **Por quê**: Referência histórica para BERT PT-BR
  - **Foco**: Pretraining em corpus brasileiro, diferenças PT-PT vs PT-BR

---

## Papers de Avaliação e Benchmarks

- [ ] **MTEB: Massive Text Embedding Benchmark**
  - Autores: Muennighoff et al. (2022)
  - Link: https://arxiv.org/abs/2210.07316
  - **Por quê**: Framework de avaliação padrão para embeddings
  - **Foco**: Métricas, datasets, como fazer benchmark robusto

- [ ] **ASSIN 2: Evaluating Semantic Textual Similarity and Textual Entailment for Portuguese**
  - Autores: Real et al. (2020)
  - Link: https://link.springer.com/chapter/10.1007/978-3-030-41505-1_39
  - **Por quê**: Benchmark PT-BR para similaridade semântica
  - **Foco**: Dataset, métricas, resultados baseline

---

## Papers Técnicos (Métodos)

- [ ] **Efficient Natural Language Response Suggestion for Smart Reply**
  - Autores: Henderson et al. (2017)
  - Link: https://arxiv.org/abs/1705.00652
  - **Por quê**: Técnicas de retrieval semântico em produção
  - **Foco**: Approximate nearest neighbors, otimizações

- [ ] **Dense Passage Retrieval for Open-Domain Question Answering**
  - Autores: Karpukhin et al. (2020)
  - Link: https://arxiv.org/abs/2004.04906
  - **Por quê**: Uso de embeddings para retrieval (RAG)
  - **Foco**: Bi-encoder, contrastive learning, hard negatives

---

## Recursos Online

### Tutoriais e Guias

- [ ] **Sentence-Transformers Documentation**
  - Link: https://www.sbert.net/
  - Foco: Como usar biblioteca, exemplos práticos

- [ ] **HuggingFace Embeddings Guide**
  - Link: https://huggingface.co/blog/getting-started-with-embeddings
  - Foco: Overview, casos de uso, boas práticas

### Benchmarks e Leaderboards

- [ ] **MTEB Leaderboard**
  - Link: https://huggingface.co/spaces/mteb/leaderboard
  - Foco: Ver rankings, comparar modelos

- [ ] **Papers with Code - Sentence Embeddings**
  - Link: https://paperswithcode.com/task/sentence-embeddings
  - Foco: SOTA models, datasets, código

---

## Papers Complementares (Leitura Opcional)

### Arquiteturas e Variações

- [ ] **SimCSE: Simple Contrastive Learning of Sentence Embeddings**
  - Link: https://arxiv.org/abs/2104.08821
  - Foco: Contrastive learning simples e eficaz

- [ ] **ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction**
  - Link: https://arxiv.org/abs/2004.12832
  - Foco: Late interaction para retrieval

### Avaliação e Interpretabilidade

- [ ] **What Does BERT Look At? An Analysis of BERT's Attention**
  - Link: https://arxiv.org/abs/1906.04341
  - Foco: Entender o que BERT aprende

- [ ] **Evaluation of Sentence Embeddings in Downstream and Linguistic Probing Tasks**
  - Link: https://arxiv.org/abs/1806.06259
  - Foco: Como avaliar qualidade de embeddings

---

### Estudos sobre Tamanho de Queries

1. **Jansen, B. J., Spink, A., & Saracevic, T. (2000)**
   *"Real life, real users, and real needs: a study and analysis of user queries on the web"*
   Information Processing & Management, 36(2), 207-227.
   **Principais achados:** Média de 2.35 palavras por query em 51.473 queries analisadas.

2. **Spink, A., Wolfram, D., Jansen, M. B., & Saracevic, T. (2001)**
   *"Searching the Web: The public and their queries"*
   Journal of the American Society for Information Science and Technology, 52(3), 226-234.
   **Principais achados:** Média de 2.6 palavras; distribuição: 1 palavra (20%), 2 palavras (32%), 3 palavras (26%).

3. **Google Search Research (2015-2020)**
   Tendências atuais mostram aumento para 3-4 palavras em média, impulsionado por:
   - Busca em dispositivos móveis (queries mais conversacionais)
   - Busca por voz em geral (frases mais naturais)
   - Maior familiaridade com motores de busca

### Justificativa do Design

Nosso design de queries reflete **dois perfis de usuários reais**:

1. **Público Geral (~40%)**: Queries curtas (2-3 palavras), linguagem natural
   - Ex: cidadãos buscando informações sobre serviços públicos

2. **Profissionais/Especialistas (~40%)**: Queries técnicas (3-4 palavras), com jargões
   - Ex: servidores públicos, jornalistas, gestores buscando informações específicas

3. **Pesquisas Complexas (~20%)**: Queries longas (4-5 palavras), múltiplos conceitos
   - Ex: pesquisadores, analistas buscando contexto detalhado

Esta distribuição permite avaliar a capacidade dos embeddings em **ambos os cenários de uso real**.
