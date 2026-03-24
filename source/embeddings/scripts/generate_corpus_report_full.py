#!/usr/bin/env python3
"""
Generate corpus analysis report from full dataset (10k docs).

Analyzes the ORIGINAL dataset before curation to show natural distributions.

Usage:
    python generate_corpus_report_full.py
"""

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import re
from datetime import datetime

# Set seaborn style
sns.set_theme(style="whitegrid", palette="husl")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10


# Category mapping
CATEGORY_MAPPING = {
    "Saúde": "Saúde",
    "Educação": "Educação",
    "Economia e Finanças": "Economia",
    "Meio Ambiente e Sustentabilidade": "Meio Ambiente",
    "Segurança Pública": "Segurança Pública",
    "Desenvolvimento Social": "Assistência Social",
    "Infraestrutura e Transportes": "Infraestrutura",
    "Cultura, Artes e Patrimônio": "Cultura",
    "Ciência, Tecnologia e Inovação": "Ciência e Tecnologia",
    "Agricultura, Pecuária e Abastecimento": "Agricultura",
}


# Common government/technical terms (jargões)
JARGOES_BR = [
    # Órgãos
    'ministério', 'secretaria', 'agência', 'autarquia', 'fundação',
    # Políticas
    'portaria', 'decreto', 'medida provisória', 'resolução', 'instrução normativa',
    'lei federal', 'lei complementar', 'emenda constitucional',
    # Programas
    'programa', 'projeto', 'plano nacional', 'política pública',
    # Orçamento
    'orçamento', 'recursos', 'investimento', 'repasse', 'crédito',
    'loa', 'ppa', 'ldo', 'emenda parlamentar',
    # Saúde
    'sus', 'anvisa', 'vigilância sanitária', 'atenção básica', 'ubs',
    # Educação
    'mec', 'enem', 'sisu', 'fies', 'prouni', 'ideb', 'bncc',
    # Economia
    'pib', 'ipca', 'selic', 'copom', 'bc', 'bacen', 'cvm',
    # Social
    'bolsa família', 'cadastro único', 'bpc', 'benefício',
    # Meio Ambiente
    'ibama', 'icmbio', 'licença ambiental', 'desmatamento',
    # Segurança
    'polícia federal', 'polícia rodoviária', 'seop', 'senasp',
    # Agricultura
    'embrapa', 'conab', 'paa', 'pronaf', 'safra',
    # Infraestrutura
    'dnit', 'antt', 'anac', 'antaq', 'concessão',
    # C&T
    'cnpq', 'capes', 'finep', 'mcti', 'pesquisa e desenvolvimento',
]


def load_full_dataset():
    """Load full dataset (10k docs - cleaned version)."""
    data_dir = Path(__file__).parent.parent / "data" / "raw"
    parquet_file = data_dir / "govbrnews_recent_10000_clean.parquet"

    print(f"📂 Loading: {parquet_file.name}")
    df = pd.read_parquet(parquet_file)

    # Map to target categories
    df['target_category'] = df['theme_1_level_1'].map(CATEGORY_MAPPING)

    # Filter to only mapped categories
    df_filtered = df[df['target_category'].notna()].copy()

    print(f"✅ Loaded {len(df)} total documents")
    print(f"✅ Filtered to {len(df_filtered)} mapped documents ({len(df_filtered)/len(df)*100:.1f}%)")

    return df_filtered


def count_jargoes(text):
    """Count occurrences of government jargon terms."""
    if pd.isna(text):
        return 0

    text_lower = str(text).lower()
    count = 0

    for jargao in JARGOES_BR:
        pattern = r'\b' + re.escape(jargao) + r'\b'
        count += len(re.findall(pattern, text_lower))

    return count


def analyze_corpus(df):
    """Perform statistical analysis on corpus."""
    # Content length
    df['content_length'] = df['content'].str.len()

    # Size categories
    df['size_category'] = pd.cut(
        df['content_length'],
        bins=[0, 3000, 5500, float('inf')],
        labels=['Curta', 'Média', 'Longa']
    )

    # Count jargões
    print("📊 Analyzing jargões (may take 1-2 minutes)...")
    df['jargao_count'] = df['content'].apply(count_jargoes)
    df['jargao_density'] = (df['jargao_count'] / df['content_length'] * 1000).round(2)

    return df


def plot_category_distribution(df, output_dir):
    """Plot document count by category."""
    fig, ax = plt.subplots(figsize=(10, 6))

    category_counts = df['target_category'].value_counts().sort_index()

    sns.barplot(
        x=category_counts.index,
        y=category_counts.values,
        ax=ax,
        hue=category_counts.index,
        palette="husl",
        legend=False
    )

    ax.set_xlabel('Categoria', fontsize=12, fontweight='bold')
    ax.set_ylabel('Número de Documentos', fontsize=12, fontweight='bold')
    ax.set_title('Distribuição de Documentos por Categoria (Dataset Completo)',
                 fontsize=14, fontweight='bold', pad=20)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    output_file = output_dir / 'category_distribution.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_file.name)


def plot_length_distribution(df, output_dir):
    """Plot content length distribution with stats."""
    fig, ax = plt.subplots(figsize=(12, 6))

    sns.boxplot(
        data=df,
        x='target_category',
        y='content_length',
        ax=ax,
        hue='target_category',
        palette="husl",
        legend=False,
        showmeans=True,
        meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='red', markersize=8)
    )

    ax.set_xlabel('Categoria', fontsize=12, fontweight='bold')
    ax.set_ylabel('Tamanho do Conteúdo (caracteres)', fontsize=12, fontweight='bold')
    ax.set_title('Distribuição de Tamanho por Categoria (Dataset Limpo)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.axhline(df['content_length'].median(), color='red', linestyle='--',
               linewidth=1, alpha=0.7, label=f'Mediana Geral ({df["content_length"].median():.0f})')

    plt.xticks(rotation=45, ha='right')
    plt.legend()
    plt.tight_layout()

    output_file = output_dir / 'length_distribution.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_file.name)


def plot_jargao_density(df, output_dir):
    """Plot jargão density by category."""
    fig, ax = plt.subplots(figsize=(12, 6))

    sns.violinplot(
        data=df,
        x='target_category',
        y='jargao_density',
        ax=ax,
        hue='target_category',
        palette="husl",
        legend=False,
        inner='box'
    )

    ax.set_xlabel('Categoria', fontsize=12, fontweight='bold')
    ax.set_ylabel('Densidade de Jargões (por 1000 caracteres)', fontsize=12, fontweight='bold')
    ax.set_title('Densidade de Termos Técnicos por Categoria (Dataset Completo)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.axhline(df['jargao_density'].mean(), color='red', linestyle='--',
               linewidth=1, alpha=0.7, label='Média Geral')

    plt.xticks(rotation=45, ha='right')
    plt.legend()
    plt.tight_layout()

    output_file = output_dir / 'jargao_density.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_file.name)


def plot_size_category_dist(df, output_dir):
    """Plot size category distribution as stacked proportions."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Crosstab of category vs size, normalized by category (rows)
    crosstab = pd.crosstab(df['target_category'], df['size_category'], normalize='index')

    # Convert to percentage
    crosstab_pct = crosstab * 100

    # Plot stacked bars
    crosstab_pct.plot(
        kind='bar',
        stacked=True,
        ax=ax,
        color=['#2ecc71', '#3498db', '#e74c3c'],
        width=0.7
    )

    ax.set_xlabel('Categoria', fontsize=12, fontweight='bold')
    ax.set_ylabel('Proporção (%)', fontsize=12, fontweight='bold')
    ax.set_title('Proporção de Tamanho (Curta/Média/Longa) por Categoria',
                 fontsize=14, fontweight='bold', pad=20)
    ax.legend(title='Tamanho', title_fontsize=11, loc='upper right')
    ax.set_ylim(0, 100)

    # Add grid for easier reading
    ax.yaxis.grid(True, linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    output_file = output_dir / 'size_category_distribution.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_file.name)


def generate_markdown_report(df, plots, output_file):
    """Generate markdown report with statistics and plots."""

    report = f"""# Análise Estatística do Corpus - Embeddings

**Data da Análise:** {datetime.now().strftime('%d/%m/%Y %H:%M')}

**Corpus:** Notícias do Governo Federal Brasileiro (Dataset Completo - 10k docs)

**Fonte:** HuggingFace - [nitaibezerra/govbrnews](https://huggingface.co/datasets/nitaibezerra/govbrnews)

> **Nota:** Documentos com mais de 20.000 caracteres foram removidos (15 docs) por serem outliers resultantes de erros de scraping/ingestão.

---

## 📊 Visão Geral

- **Total de Documentos Analisados:** {len(df):,}
- **Categorias Mapeadas:** {df['target_category'].nunique()}
- **Período:** {df['published_at'].min().strftime('%d/%m/%Y')} a {df['published_at'].max().strftime('%d/%m/%Y')}
- **Órgãos Diferentes:** {df['agency'].nunique()}

---

## 📂 Distribuição por Categoria

![Distribuição por Categoria]({plots['category']})

### Estatísticas por Categoria (Distribuição Natural)

| Categoria | Documentos | % do Total | Tamanho Médio | Min | Max | Jargões (média) |
|-----------|------------|------------|---------------|-----|-----|-----------------|
"""

    # Add statistics table
    total = len(df)
    for category in sorted(df['target_category'].unique()):
        cat_df = df[df['target_category'] == category]
        pct = (len(cat_df) / total) * 100
        report += f"| {category} | {len(cat_df)} | {pct:.1f}% | "
        report += f"{cat_df['content_length'].mean():.0f} | "
        report += f"{cat_df['content_length'].min()} | {cat_df['content_length'].max()} | "
        report += f"{cat_df['jargao_count'].mean():.1f} |\n"

    report += f"""
**Observação:** A distribuição reflete a **produção natural** de conteúdo por área governamental.
Categorias como Segurança Pública e Economia produzem mais notícias, enquanto Agricultura tem menor volume.

---

## 📏 Distribuição de Tamanho

![Distribuição de Tamanho]({plots['length']})

### Estatísticas Gerais de Tamanho

- **Média:** {df['content_length'].mean():.0f} caracteres
- **Mediana:** {df['content_length'].median():.0f} caracteres
- **Desvio Padrão:** {df['content_length'].std():.0f} caracteres
- **Mínimo:** {df['content_length'].min()} caracteres
- **Máximo:** {df['content_length'].max():,} caracteres
- **Percentil 95:** {df['content_length'].quantile(0.95):.0f} caracteres

### Perfis de Tamanho

![Distribuição Curta/Média/Longa]({plots['size_category']})

**Distribuição geral:**
"""

    size_counts = df['size_category'].value_counts()
    for size in ['Curta', 'Média', 'Longa']:
        if size in size_counts.index:
            count = size_counts[size]
            pct = (count / len(df)) * 100
            report += f"- **{size}:** {count:,} documentos ({pct:.1f}%)\n"

    report += f"""
**Definição dos perfis:**
- **Curta:** até 3.000 caracteres (notas rápidas, anúncios)
- **Média:** 3.000-5.500 caracteres (notícias padrão)
- **Longa:** acima de 5.500 caracteres (reportagens, análises)

---

## 🎯 Análise de Termos Técnicos (Jargões)

![Densidade de Jargões]({plots['jargao']})

### Estatísticas de Jargões

- **Média de jargões por documento:** {df['jargao_count'].mean():.1f}
- **Mediana:** {df['jargao_count'].median():.1f}
- **Densidade média:** {df['jargao_density'].mean():.2f} jargões por 1000 caracteres
- **Documento com mais jargões:** {df['jargao_count'].max()} termos
- **Categoria com maior densidade:** {df.groupby('target_category')['jargao_density'].mean().idxmax()}

### Top 10 Categorias por Densidade de Jargões

| Categoria | Densidade Média | Jargões Médios | Documentos |
|-----------|-----------------|----------------|------------|
"""

    jargao_by_cat = df.groupby('target_category').agg({
        'jargao_density': 'mean',
        'jargao_count': 'mean',
        'target_category': 'count'
    }).rename(columns={'target_category': 'doc_count'})
    jargao_by_cat = jargao_by_cat.sort_values('jargao_density', ascending=False).head(10)

    for category in jargao_by_cat.index:
        row = jargao_by_cat.loc[category]
        report += f"| {category} | {row['jargao_density']:.2f} | {row['jargao_count']:.1f} | {int(row['doc_count'])} |\n"

    report += f"""
**Interpretação:** Categorias como Infraestrutura e Assistência Social apresentam maior densidade de jargões
devido à natureza técnica e regulatória dessas áreas (portarias, programas, benefícios, etc.).

---

## 🏛️ Diversidade de Órgãos

**Total de órgãos diferentes:** {df['agency'].nunique()}

### Top 15 Órgãos Produtores de Conteúdo

| Órgão | Documentos | % do Total |
|-------|------------|------------|
"""

    agencies = df['agency'].value_counts().head(15)
    for agency, count in agencies.items():
        pct = (count / len(df)) * 100
        report += f"| {agency} | {count} | {pct:.1f}% |\n"

    report += f"""
---

## 📈 Análise Temporal

**Período analisado:** {(df['published_at'].max() - df['published_at'].min()).days} dias

**Documentos por mês:**
"""

    df['month'] = df['published_at'].dt.to_period('M')
    monthly = df.groupby('month').size().sort_index()
    for month, count in monthly.items():
        report += f"- **{month}:** {count} documentos\n"

    report += """
---

## 📝 Observações e Conclusões

### Características do Dataset

✅ **Distribuição Natural:** Dataset reflete a produção real de conteúdo por área governamental
- Segurança Pública e Economia são mais prolíficas
- Agricultura tem menor volume, mas mantém qualidade

✅ **Diversidade de Tamanhos:**
- Boa variação (24 a 7M+ caracteres)
- Maioria concentrada em 2-5k caracteres (notícias padrão)
- Presença de documentos longos (reportagens) e curtos (notas)

✅ **Alto Conteúdo Técnico:**
- Média de 8+ jargões por documento
- Densidade significativa em áreas regulatórias
- Vocabulário específico do governo BR bem representado

✅ **Diversidade de Fontes:**
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
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ Relatório gerado: {output_file}")


def main():
    # Paths
    output_dir = Path(__file__).parent.parent / "docs"
    plots_dir = output_dir / "images"
    plots_dir.mkdir(parents=True, exist_ok=True)

    print("📂 Loading full dataset (10k docs)...")
    df = load_full_dataset()

    print("\n📊 Analyzing corpus...")
    df = analyze_corpus(df)

    print("\n📈 Generating plots...")
    plots = {}
    plots['category'] = plot_category_distribution(df, plots_dir)
    print(f"  ✅ {plots['category']}")

    plots['length'] = plot_length_distribution(df, plots_dir)
    print(f"  ✅ {plots['length']}")

    plots['jargao'] = plot_jargao_density(df, plots_dir)
    print(f"  ✅ {plots['jargao']}")

    plots['size_category'] = plot_size_category_dist(df, plots_dir)
    print(f"  ✅ {plots['size_category']}")

    print("\n📝 Generating markdown report...")
    # Update plot paths to include images/ directory
    plots = {k: f"images/{v}" for k, v in plots.items()}

    report_file = output_dir / "ANALISE_CORPUS.md"
    generate_markdown_report(df, plots, report_file)

    print(f"\n🎉 Done! Report saved to: {report_file}")
    print(f"📊 Plots saved to: {plots_dir}")
    print(f"\n📄 Total documents analyzed: {len(df):,}")


if __name__ == "__main__":
    main()
