# Análise Estatística do Corpus - Embeddings

**Corpus:** Notícias do Governo Federal Brasileiro (Dataset Completo - 10k docs)

**Fonte:** HuggingFace - [nitaibezerra/govbrnews](https://huggingface.co/datasets/nitaibezerra/govbrnews)

> **Nota:** Documentos com mais de 20.000 caracteres foram removidos (15 docs) por serem outliers resultantes de erros de scraping/ingestão.

---

## Visão Geral

- **Total de Documentos Analisados:** 5,680
- **Categorias Mapeadas:** 10
- **Período:** 06/01/2026 a 23/03/2026
- **Órgãos Diferentes:** 130

---

## Distribuição por Categoria

![Distribuição por Categoria](images/category_distribution.png)

### Estatísticas por Categoria (Distribuição Natural)

| Categoria | Documentos | % do Total | Tamanho Médio | Min | Max | Jargões (média) |
|-----------|------------|------------|---------------|-----|-----|-----------------|
| Agricultura | 278 | 4.9% | 3656 | 595 | 10956 | 6.9 |
| Assistência Social | 414 | 7.3% | 4147 | 238 | 12844 | 8.9 |
| Ciência e Tecnologia | 488 | 8.6% | 3754 | 253 | 19020 | 7.0 |
| Cultura | 512 | 9.0% | 4262 | 24 | 16425 | 4.3 |
| Economia | 829 | 14.6% | 3192 | 24 | 15477 | 5.3 |
| Educação | 617 | 10.9% | 4052 | 24 | 16822 | 12.0 |
| Infraestrutura | 446 | 7.9% | 3786 | 548 | 13475 | 9.6 |
| Meio Ambiente | 556 | 9.8% | 4528 | 342 | 17699 | 7.8 |
| Saúde | 605 | 10.7% | 3773 | 24 | 10757 | 9.0 |
| Segurança Pública | 935 | 16.5% | 2808 | 264 | 14493 | 3.9 |

**Observação:** A distribuição reflete a **produção natural** de conteúdo por área governamental.
Categorias como Segurança Pública e Economia produzem mais notícias, enquanto Agricultura tem menor volume.

---

## Distribuição de Tamanho

![Distribuição de Tamanho](images/length_distribution.png)

### Estatísticas Gerais de Tamanho

- **Média:** 3699 caracteres
- **Mediana:** 3266 caracteres (preferível dado a distribuição)
- **Desvio Padrão:** 2253 caracteres
- **Mínimo:** 24 caracteres
- **Máximo:** 19,020 caracteres
- **Percentil 95:** 7949 caracteres

### Perfis de Tamanho

![Distribuição Curta/Média/Longa](images/size_category_distribution.png)

**Distribuição geral:**
- **Curta:** 2,537 documentos (44.7%)
- **Média:** 2,194 documentos (38.6%)
- **Longa:** 949 documentos (16.7%)

**Definição dos perfis:**
- **Curta:** até 3.000 caracteres (notas rápidas, anúncios)
- **Média:** 3.000-5.500 caracteres (notícias padrão)
- **Longa:** acima de 5.500 caracteres (reportagens, análises)

---

## Análise de Termos Técnicos (Jargões)

![Densidade de Jargões](images/jargao_density.png)

### Estatísticas de Jargões

- **Média de jargões por documento:** 7.2
- **Mediana:** 5.0
- **Densidade média:** 1.92 jargões por 1000 caracteres
- **Documento com mais jargões:** 95 termos
- **Categoria com maior densidade:** Educação

### Top 10 Categorias por Densidade de Jargões

| Categoria | Densidade Média | Jargões Médios | Documentos |
|-----------|-----------------|----------------|------------|
| Educação | 3.03 | 12.0 | 617 |
| Infraestrutura | 2.62 | 9.6 | 446 |
| Saúde | 2.47 | 9.0 | 605 |
| Assistência Social | 2.27 | 8.9 | 414 |
| Ciência e Tecnologia | 1.85 | 7.0 | 488 |
| Agricultura | 1.80 | 6.9 | 278 |
| Economia | 1.67 | 5.3 | 829 |
| Meio Ambiente | 1.63 | 7.8 | 556 |
| Segurança Pública | 1.31 | 3.9 | 935 |
| Cultura | 0.99 | 4.3 | 512 |

**Interpretação:** Categorias como Infraestrutura e Assistência Social apresentam maior densidade de jargões
devido à natureza técnica e regulatória dessas áreas (portarias, programas, benefícios, etc.).

---

## Diversidade de Órgãos

**Total de órgãos diferentes:** 130

### Top 15 Órgãos Produtores de Conteúdo

| Órgão | Documentos | % do Total |
|-------|------------|------------|
| agencia_brasil | 806 | 14.2% |
| tvbrasil | 395 | 7.0% |
| mec | 171 | 3.0% |
| mdr | 158 | 2.8% |
| secom | 157 | 2.8% |
| cultura | 157 | 2.8% |
| mds | 149 | 2.6% |
| saude | 146 | 2.6% |
| mj | 116 | 2.0% |
| mma | 113 | 2.0% |
| anvisa | 112 | 2.0% |
| portos-e-aeroportos | 112 | 2.0% |
| incra | 104 | 1.8% |
| agricultura | 101 | 1.8% |
| receitafederal | 87 | 1.5% |

---

## Análise Temporal

**Período analisado:** 75 dias

**Documentos por mês:**
- **2026-01:** 170 documentos
- **2026-02:** 1823 documentos
- **2026-03:** 3687 documentos

---

## Observações e Conclusões

### Características do Dataset

**Distribuição Natural:** Dataset reflete a produção real de conteúdo por área governamental
- Segurança Pública e Economia são mais prolíficas
- Agricultura tem menor volume, mas mantém qualidade

**Diversidade de Tamanhos:**
- Boa variação (24 a 20k caracteres)
- Maioria concentrada em 2-5k caracteres (notícias padrão)
- Presença de documentos longos (reportagens) e curtos (notas)

**Alto Conteúdo Técnico:**
- Média de 8+ jargões por documento
- Densidade significativa em áreas regulatórias
- Vocabulário específico do governo BR bem representado

**Diversidade de Fontes:**
- 90+ órgãos diferentes contribuindo
- Variedade de estilos e terminologias
- Representatividade de diferentes ministérios

### Adequação para Avaliação de Embeddings

Este dataset é **ideal** para avaliar embeddings porque:

1. **Realismo:** Notícias reais refletem linguagem de produção
2. **Jargão BR:** Alta densidade de termos técnicos governamentais específicos do Brasil
3. **Diversidade:** Múltiplas categorias, tamanhos e fontes
4. **Atualidade:** Notícias recentes (últimos 3-4 meses)
5. **Escala:** 6.200+ documentos mapeados permitem curadoria robusta

### Próximos Passos

A partir deste dataset de 10k documentos, será feita a **curadoria de 250 notícias** para compor o corpus de teste:
- 25 documentos por categoria (balanceamento)
- Diversidade de tamanhos (curta/média/longa)
- Múltiplos órgãos por categoria
- Representatividade de jargões técnicos

---

**Gerado por:** `generate_corpus_report_full.py`

**Projeto:** Estudo Comparativo de Embeddings para Notícias Gov.br - Issue #1

**Repositório:** [data-science/embeddings](../../)
