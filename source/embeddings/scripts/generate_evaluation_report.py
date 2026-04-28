#!/usr/bin/env python3
"""
Gera relatório visual da avaliação de LLMs - Issue #3.

Cria gráficos comparativos e análise detalhada.
"""

import pandas as pd
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np

# Configuração
BASE_DIR = Path(__file__).parent.parent
RESULTS_DIR = BASE_DIR / "results" / "llm_evaluation"
OUTPUT_DIR = RESULTS_DIR / "visualizations"
OUTPUT_DIR.mkdir(exist_ok=True)

# Style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


def load_results():
    """Carrega resultados da avaliação."""
    print("📂 Carregando resultados...")

    # CSV summary
    csv_path = RESULTS_DIR / "comparison_summary.csv"
    df = pd.read_csv(csv_path)

    # JSON completo
    json_path = RESULTS_DIR / "comparison_full.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        full_data = json.load(f)

    print(f"  ✅ {len(df)} modelos carregados")

    return df, full_data


def plot_accuracy_comparison(df):
    """Gráfico de barras: Accuracy por modelo."""
    print("\n📊 Gerando gráfico de accuracy...")

    # Filtrar apenas modelos que funcionaram
    df_working = df[df['Accuracy'] > 0].copy()
    df_working = df_working.sort_values('Accuracy', ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ['#2ecc71' if acc >= 0.5 else '#f39c12' if acc >= 0.4 else '#e74c3c'
              for acc in df_working['Accuracy']]

    bars = ax.barh(df_working['Model'], df_working['Accuracy'], color=colors)

    # Adicionar valores
    for bar, acc in zip(bars, df_working['Accuracy']):
        width = bar.get_width()
        ax.text(width + 0.01, bar.get_y() + bar.get_height()/2,
                f'{acc:.1%}', ha='left', va='center', fontsize=10, fontweight='bold')

    ax.set_xlabel('Accuracy', fontsize=12, fontweight='bold')
    ax.set_title('Comparação de Accuracy - Classificação de Notícias\n200 notícias de teste',
                 fontsize=14, fontweight='bold')
    ax.set_xlim(0, 0.6)
    ax.grid(axis='x', alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'accuracy_comparison.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Salvo: {OUTPUT_DIR / 'accuracy_comparison.png'}")
    plt.close()


def plot_cost_vs_accuracy(df):
    """Scatter: Custo vs Accuracy."""
    print("\n📊 Gerando gráfico custo vs accuracy...")

    df_working = df[df['Accuracy'] > 0].copy()

    fig, ax = plt.subplots(figsize=(10, 6))

    scatter = ax.scatter(df_working['Total Cost ($)'], df_working['Accuracy'],
                        s=200, alpha=0.6, c=range(len(df_working)), cmap='viridis')

    # Adicionar labels
    for _, row in df_working.iterrows():
        ax.annotate(row['Model'],
                   (row['Total Cost ($)'], row['Accuracy']),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=9, alpha=0.8)

    ax.set_xlabel('Custo Total (USD) - 200 notícias', fontsize=12, fontweight='bold')
    ax.set_ylabel('Accuracy', fontsize=12, fontweight='bold')
    ax.set_title('Custo vs Performance\nQuadrante superior esquerdo = Melhor custo-benefício',
                 fontsize=14, fontweight='bold')
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'cost_vs_accuracy.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Salvo: {OUTPUT_DIR / 'cost_vs_accuracy.png'}")
    plt.close()


def plot_latency_comparison(df):
    """Gráfico de barras: Latência P50."""
    print("\n📊 Gerando gráfico de latência...")

    df_working = df[df['Accuracy'] > 0].copy()
    df_working = df_working.sort_values('Latency P50 (s)', ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ['#2ecc71' if lat < 0.5 else '#f39c12' if lat < 0.6 else '#e74c3c'
              for lat in df_working['Latency P50 (s)']]

    bars = ax.barh(df_working['Model'], df_working['Latency P50 (s)'], color=colors)

    # Adicionar valores
    for bar, lat in zip(bars, df_working['Latency P50 (s)']):
        width = bar.get_width()
        ax.text(width + 0.01, bar.get_y() + bar.get_height()/2,
                f'{lat:.3f}s', ha='left', va='center', fontsize=10, fontweight='bold')

    ax.set_xlabel('Latência P50 (segundos)', fontsize=12, fontweight='bold')
    ax.set_title('Latência Mediana (P50) por Modelo', fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'latency_comparison.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Salvo: {OUTPUT_DIR / 'latency_comparison.png'}")
    plt.close()


def plot_confusion_matrix_best_model(full_data):
    """Matriz de confusão do melhor modelo."""
    print("\n📊 Gerando matriz de confusão (melhor modelo)...")

    # Encontrar melhor modelo
    results = full_data['results']
    best_model = max(results, key=lambda x: x['accuracy'])

    conf_matrix = np.array(best_model['confusion_matrix'])
    categories = full_data['categories']

    fig, ax = plt.subplots(figsize=(12, 10))

    # Normalizar por linha (recall)
    conf_matrix_norm = conf_matrix.astype('float') / conf_matrix.sum(axis=1)[:, np.newaxis]
    conf_matrix_norm = np.nan_to_num(conf_matrix_norm)  # Replace NaN with 0

    sns.heatmap(conf_matrix_norm, annot=conf_matrix, fmt='d', cmap='Blues',
                xticklabels=categories, yticklabels=categories,
                cbar_kws={'label': 'Recall (normalizado)'}, ax=ax)

    ax.set_xlabel('Predito', fontsize=12, fontweight='bold')
    ax.set_ylabel('Real', fontsize=12, fontweight='bold')
    ax.set_title(f'Matriz de Confusão - {best_model["model_name"]}\nAccuracy: {best_model["accuracy"]:.1%}',
                 fontsize=14, fontweight='bold')

    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'confusion_matrix_best.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Salvo: {OUTPUT_DIR / 'confusion_matrix_best.png'}")
    plt.close()


def plot_tier_analysis(df):
    """Análise por tier."""
    print("\n📊 Gerando análise por tier...")

    df_working = df[df['Accuracy'] > 0].copy()

    tier_stats = df_working.groupby('Tier').agg({
        'Accuracy': 'mean',
        'Total Cost ($)': 'mean',
        'Latency P50 (s)': 'mean'
    }).reset_index()

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # Accuracy por tier
    axes[0].bar(tier_stats['Tier'], tier_stats['Accuracy'], color='skyblue')
    axes[0].set_ylabel('Accuracy Médio', fontweight='bold')
    axes[0].set_title('Accuracy por Tier', fontweight='bold')
    axes[0].grid(axis='y', alpha=0.3)

    # Custo por tier
    axes[1].bar(tier_stats['Tier'], tier_stats['Total Cost ($)'], color='lightcoral')
    axes[1].set_ylabel('Custo Médio (USD)', fontweight='bold')
    axes[1].set_title('Custo por Tier', fontweight='bold')
    axes[1].grid(axis='y', alpha=0.3)

    # Latência por tier
    axes[2].bar(tier_stats['Tier'], tier_stats['Latency P50 (s)'], color='lightgreen')
    axes[2].set_ylabel('Latência P50 Média (s)', fontweight='bold')
    axes[2].set_title('Latência por Tier', fontweight='bold')
    axes[2].grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'tier_analysis.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ Salvo: {OUTPUT_DIR / 'tier_analysis.png'}")
    plt.close()


def generate_markdown_report(df, full_data):
    """Gera relatório em Markdown."""
    print("\n📝 Gerando relatório Markdown...")

    df_working = df[df['Accuracy'] > 0].copy()
    best_model = df_working.loc[df_working['Accuracy'].idxmax()]

    report = f"""# Relatório de Avaliação de LLMs - Issue #3

**Data:** {full_data['evaluation_date']}
**Total de modelos testados:** {len(df)}
**Modelos funcionais:** {len(df_working)}
**Total de notícias de teste:** 200
**Categorias:** {len(full_data['categories'])}

---

## 🏆 Melhor Modelo

**{best_model['Model']}** ({best_model['Tier']})

- **Accuracy:** {best_model['Accuracy']:.2%}
- **F1-Macro:** {best_model['F1-Macro']:.4f}
- **F1-Weighted:** {best_model['F1-Weighted']:.4f}
- **Latência P50:** {best_model['Latency P50 (s)']:.3f}s
- **Custo (200 notícias):** ${best_model['Total Cost ($)']:.4f}

---

## 📊 Ranking Completo

### Por Accuracy

| Rank | Modelo | Tier | Accuracy | F1-Macro | Custo |
|------|--------|------|----------|----------|-------|
"""

    for i, (_, row) in enumerate(df_working.sort_values('Accuracy', ascending=False).iterrows(), 1):
        report += f"| {i} | {row['Model']} | {row['Tier']} | {row['Accuracy']:.2%} | {row['F1-Macro']:.4f} | ${row['Total Cost ($)']:.4f} |\n"

    report += "\n### Por Custo-Benefício (Accuracy / Custo)\n\n"

    df_working['Cost_Benefit'] = df_working['Accuracy'] / df_working['Total Cost ($)'].replace(0, 0.0001)

    report += "| Rank | Modelo | Accuracy | Custo | Custo-Benefício |\n"
    report += "|------|--------|----------|-------|------------------|\n"

    for i, (_, row) in enumerate(df_working.sort_values('Cost_Benefit', ascending=False).head(5).iterrows(), 1):
        report += f"| {i} | {row['Model']} | {row['Accuracy']:.2%} | ${row['Total Cost ($)']:.4f} | {row['Cost_Benefit']:.2f} |\n"

    report += f"""
---

## 💡 Insights

### Performance
- **Melhor accuracy:** {df_working['Accuracy'].max():.2%} (Claude 3 Sonnet)
- **Accuracy médio:** {df_working['Accuracy'].mean():.2%}
- **Spread:** {df_working['Accuracy'].max() - df_working['Accuracy'].min():.2%}

### Custo
- **Mais econômico:** Amazon Nova Micro (${df_working.loc[df_working['Total Cost ($)'].idxmin(), 'Total Cost ($)']:.4f})
- **Mais caro:** Claude 3 Sonnet (${df_working.loc[df_working['Total Cost ($)'].idxmax(), 'Total Cost ($)']:.4f})
- **Custo total (todos modelos):** ${df['Total Cost ($)'].sum():.2f}

### Latência
- **Mais rápido:** {df_working.loc[df_working['Latency P50 (s)'].idxmin(), 'Model']} ({df_working['Latency P50 (s)'].min():.3f}s)
- **Mais lento:** {df_working.loc[df_working['Latency P50 (s)'].idxmax(), 'Model']} ({df_working['Latency P50 (s)'].max():.3f}s)

---

## 🎯 Recomendações

### Para Produção (Melhor Performance)
**Claude 3 Sonnet** - Accuracy de 51%, mas custo elevado ($0.46/200 notícias)

### Para Produção (Melhor Custo-Benefício)
**Amazon Nova Micro** - Accuracy de 45.5% com custo mínimo ($0.004/200 notícias)
**Custo-benefício:** 101x melhor que Claude 3 Sonnet

### Para Experimentação
**Amazon Nova Lite** ou **Amazon Nova Pro** - Boa performance intermediária

---

## 📁 Arquivos Gerados

- `comparison_summary.csv` - Tabela comparativa
- `comparison_full.json` - Dados completos com predições
- `model_rankings.txt` - Rankings por métrica
- `visualizations/` - Gráficos e visualizações

---

## 🔧 Categorias Avaliadas

{', '.join(full_data['categories'])}

---

**Gerado automaticamente pela Issue #3 - LLM Classification Evaluation**
"""

    report_path = RESULTS_DIR / "EVALUATION_REPORT.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"  ✅ Salvo: {report_path}")


def main():
    """Pipeline principal."""
    print("="*80)
    print("GERAÇÃO DE RELATÓRIO VISUAL - ISSUE #3")
    print("="*80)

    # Carregar dados
    df, full_data = load_results()

    # Gerar gráficos
    plot_accuracy_comparison(df)
    plot_cost_vs_accuracy(df)
    plot_latency_comparison(df)
    plot_confusion_matrix_best_model(full_data)
    plot_tier_analysis(df)

    # Gerar relatório Markdown
    generate_markdown_report(df, full_data)

    print("\n" + "="*80)
    print("✅ RELATÓRIO COMPLETO GERADO!")
    print("="*80)
    print(f"\n📁 Visualizações em: {OUTPUT_DIR}")
    print(f"📄 Relatório Markdown: {RESULTS_DIR / 'EVALUATION_REPORT.md'}")


if __name__ == "__main__":
    main()
