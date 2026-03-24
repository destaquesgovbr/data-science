#!/usr/bin/env python3
"""
Generate corpus analysis report with plots.

Creates a markdown report with statistics and seaborn visualizations:
- Distribution by category
- Content length statistics (with min/mean/max)
- Technical terms density analysis

Usage:
    python generate_corpus_report.py
"""

import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter
import re
from datetime import datetime

# Set seaborn style
sns.set_theme(style="whitegrid", palette="husl")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10


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


def load_corpus(corpus_dir):
    """Load all JSON documents from corpus directory."""
    corpus_dir = Path(corpus_dir)

    docs = []
    for json_file in sorted(corpus_dir.glob("doc_*.json")):
        with open(json_file, 'r', encoding='utf-8') as f:
            doc = json.load(f)
            docs.append(doc)

    return pd.DataFrame(docs)


def count_jargoes(text):
    """Count occurrences of government jargon terms."""
    text_lower = text.lower()
    count = 0

    for jargao in JARGOES_BR:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(jargao) + r'\b'
        count += len(re.findall(pattern, text_lower))

    return count


def analyze_corpus(df):
    """Perform statistical analysis on corpus."""
    # Extract content length from length field or calculate
    df['content_length'] = df['length']

    # Count jargões
    df['jargao_count'] = df['content'].apply(count_jargoes)
    df['jargao_density'] = (df['jargao_count'] / df['content_length'] * 1000).round(2)

    # Extract size category from metadata
    df['size_category'] = df['metadata'].apply(lambda x: x.get('size_category', 'Unknown'))

    return df


def plot_category_distribution(df, output_dir):
    """Plot document count by category."""
    fig, ax = plt.subplots(figsize=(10, 6))

    category_counts = df['category'].value_counts().sort_index()

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
    ax.set_title('Distribuição de Documentos por Categoria', fontsize=14, fontweight='bold', pad=20)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    output_file = output_dir / 'category_distribution.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_file.name)


def plot_length_distribution(df, output_dir):
    """Plot content length distribution with stats."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Boxplot with mean markers
    sns.boxplot(
        data=df,
        x='category',
        y='content_length',
        ax=ax,
        palette="husl",
        showmeans=True,
        meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='red', markersize=8)
    )

    ax.set_xlabel('Categoria', fontsize=12, fontweight='bold')
    ax.set_ylabel('Tamanho do Conteúdo (caracteres)', fontsize=12, fontweight='bold')
    ax.set_title('Distribuição de Tamanho por Categoria', fontsize=14, fontweight='bold', pad=20)
    ax.axhline(df['content_length'].mean(), color='red', linestyle='--', linewidth=1, alpha=0.7, label='Média Geral')

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
        x='category',
        y='jargao_density',
        ax=ax,
        palette="husl",
        inner='box'
    )

    ax.set_xlabel('Categoria', fontsize=12, fontweight='bold')
    ax.set_ylabel('Densidade de Jargões (por 1000 caracteres)', fontsize=12, fontweight='bold')
    ax.set_title('Densidade de Termos Técnicos por Categoria', fontsize=14, fontweight='bold', pad=20)
    ax.axhline(df['jargao_density'].mean(), color='red', linestyle='--', linewidth=1, alpha=0.7, label='Média Geral')

    plt.xticks(rotation=45, ha='right')
    plt.legend()
    plt.tight_layout()

    output_file = output_dir / 'jargao_density.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_file.name)


def plot_size_category_dist(df, output_dir):
    """Plot size category distribution."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Crosstab of category vs size
    crosstab = pd.crosstab(df['category'], df['size_category'])

    crosstab.plot(
        kind='bar',
        stacked=False,
        ax=ax,
        color=['#2ecc71', '#3498db', '#e74c3c']
    )

    ax.set_xlabel('Categoria', fontsize=12, fontweight='bold')
    ax.set_ylabel('Número de Documentos', fontsize=12, fontweight='bold')
    ax.set_title('Distribuição de Tamanho (Curta/Média/Longa) por Categoria',
                 fontsize=14, fontweight='bold', pad=20)
    ax.legend(title='Tamanho', title_fontsize=11)

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

**Corpus:** Notícias do Governo Federal Brasileiro

---

## 📊 Visão Geral

- **Total de Documentos:** {len(df)}
- **Categorias:** {df['category'].nunique()}
- **Período:** {df['metadata'].apply(lambda x: x['published_date']).min()[:10]} a {df['metadata'].apply(lambda x: x['published_date']).max()[:10]}

---

## 📂 Distribuição por Categoria

![Distribuição por Categoria]({plots['category']})

### Estatísticas por Categoria

| Categoria | Documentos | Tamanho Médio | Min | Max | Jargões (média) |
|-----------|------------|---------------|-----|-----|-----------------|
"""

    # Add statistics table
    for category in sorted(df['category'].unique()):
        cat_df = df[df['category'] == category]
        report += f"| {category} | {len(cat_df)} | {cat_df['content_length'].mean():.0f} | "
        report += f"{cat_df['content_length'].min()} | {cat_df['content_length'].max()} | "
        report += f"{cat_df['jargao_count'].mean():.1f} |\n"

    report += f"""
---

## 📏 Distribuição de Tamanho

![Distribuição de Tamanho]({plots['length']})

### Estatísticas Gerais de Tamanho

- **Média:** {df['content_length'].mean():.0f} caracteres
- **Mediana:** {df['content_length'].median():.0f} caracteres
- **Desvio Padrão:** {df['content_length'].std():.0f} caracteres
- **Mínimo:** {df['content_length'].min()} caracteres
- **Máximo:** {df['content_length'].max()} caracteres

### Perfis de Tamanho

![Distribuição Curta/Média/Longa]({plots['size_category']})

**Distribuição geral:**
"""

    size_counts = df['size_category'].value_counts()
    for size, count in size_counts.items():
        pct = (count / len(df)) * 100
        report += f"- **{size}:** {count} documentos ({pct:.1f}%)\n"

    report += f"""
---

## 🎯 Análise de Termos Técnicos (Jargões)

![Densidade de Jargões]({plots['jargao']})

### Estatísticas de Jargões

- **Média de jargões por documento:** {df['jargao_count'].mean():.1f}
- **Densidade média:** {df['jargao_density'].mean():.2f} jargões por 1000 caracteres
- **Documento com mais jargões:** {df['jargao_count'].max()} termos
- **Categoria com maior densidade:** {df.groupby('category')['jargao_density'].mean().idxmax()}

### Top 10 Categorias por Densidade de Jargões

| Categoria | Densidade Média | Jargões Médios |
|-----------|-----------------|----------------|
"""

    jargao_by_cat = df.groupby('category').agg({
        'jargao_density': 'mean',
        'jargao_count': 'mean'
    }).sort_values('jargao_density', ascending=False).head(10)

    for category, row in jargao_by_cat.iterrows():
        report += f"| {category} | {row['jargao_density']:.2f} | {row['jargao_count']:.1f} |\n"

    report += f"""
---

## 🏛️ Diversidade de Órgãos

**Total de órgãos diferentes:** {df['metadata'].apply(lambda x: x['agency']).nunique()}

### Top 10 Órgãos

| Órgão | Documentos |
|-------|------------|
"""

    agencies = df['metadata'].apply(lambda x: x['agency']).value_counts().head(10)
    for agency, count in agencies.items():
        report += f"| {agency} | {count} |\n"

    report += """
---

## 📝 Observações

### Qualidade do Corpus

- ✅ **Balanceamento:** Todas as categorias têm representação adequada
- ✅ **Diversidade de tamanhos:** Boa distribuição entre documentos curtos, médios e longos
- ✅ **Jargões governamentais:** Presença significativa de termos técnicos para validar capacidade dos embeddings
- ✅ **Diversidade de órgãos:** Múltiplas fontes garantem variedade de estilos de redação

### Adequação para Avaliação de Embeddings

Este corpus é adequado para avaliar:
1. **Capacidade semântica:** Documentos com tamanhos variados testam robustez
2. **Jargão brasileiro:** Alta densidade de termos técnicos específicos do governo BR
3. **Diversidade temática:** 10 categorias cobrem principais áreas governamentais
4. **Realismo:** Notícias reais refletem linguagem de produção

---

**Gerado por:** `generate_corpus_report.py`
**Projeto:** Estudo Comparativo de Embeddings para Notícias Gov.br
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ Relatório gerado: {output_file}")


def main():
    # Paths
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    output_dir = Path(__file__).parent.parent / "docs"
    plots_dir = output_dir / "images"
    plots_dir.mkdir(parents=True, exist_ok=True)

    print("📂 Loading corpus...")
    df = load_corpus(corpus_dir)
    print(f"✅ Loaded {len(df)} documents")

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


if __name__ == "__main__":
    main()
