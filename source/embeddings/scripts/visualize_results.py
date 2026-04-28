"""
Visualização dos resultados da avaliação.

Gera gráficos comparativos de:
- Accuracy vs Custo
- Accuracy vs Latência
- F1-score vs Custo
- Distribuição de erros por categoria

Usage:
    python visualize_results.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Setup
BASE_DIR = Path(__file__).parent.parent
results_dir = BASE_DIR / 'results'
figures_dir = results_dir / 'figures'
figures_dir.mkdir(parents=True, exist_ok=True)

# Estilo
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


def load_results():
    """Carrega resultados da avaliação."""
    summary_path = results_dir / 'comparison_summary_json.csv'

    if not summary_path.exists():
        print(f"❌ Arquivo não encontrado: {summary_path}")
        print("   Execute evaluate_llm_apis_json.py primeiro.")
        return None

    df = pd.read_csv(summary_path)
    return df


def plot_accuracy_vs_cost(df):
    """Gráfico: Accuracy vs Custo."""
    fig, ax = plt.subplots(figsize=(12, 7))

    scatter = ax.scatter(
        df['total_cost_usd'],
        df['accuracy'] * 100,
        s=200,
        alpha=0.6,
        c=range(len(df)),
        cmap='viridis'
    )

    # Anotar modelos
    for idx, row in df.iterrows():
        ax.annotate(
            row['model'],
            (row['total_cost_usd'], row['accuracy'] * 100),
            xytext=(5, 5),
            textcoords='offset points',
            fontsize=9,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.3)
        )

    ax.set_xlabel('Custo Total (USD)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_title('Accuracy vs Custo - Comparação de Modelos LLM', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = figures_dir / 'accuracy_vs_cost.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Gráfico salvo: {output_path}")
    plt.close()


def plot_accuracy_vs_latency(df):
    """Gráfico: Accuracy vs Latência."""
    fig, ax = plt.subplots(figsize=(12, 7))

    scatter = ax.scatter(
        df['avg_latency_s'],
        df['accuracy'] * 100,
        s=200,
        alpha=0.6,
        c=range(len(df)),
        cmap='plasma'
    )

    # Anotar modelos
    for idx, row in df.iterrows():
        ax.annotate(
            row['model'],
            (row['avg_latency_s'], row['accuracy'] * 100),
            xytext=(5, 5),
            textcoords='offset points',
            fontsize=9,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.3)
        )

    ax.set_xlabel('Latência Média (s)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_title('Accuracy vs Latência - Comparação de Modelos LLM', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = figures_dir / 'accuracy_vs_latency.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Gráfico salvo: {output_path}")
    plt.close()


def plot_f1_vs_cost(df):
    """Gráfico: F1-score vs Custo."""
    fig, ax = plt.subplots(figsize=(12, 7))

    scatter = ax.scatter(
        df['total_cost_usd'],
        df['f1_macro'],
        s=200,
        alpha=0.6,
        c=range(len(df)),
        cmap='coolwarm'
    )

    # Anotar modelos
    for idx, row in df.iterrows():
        ax.annotate(
            row['model'],
            (row['total_cost_usd'], row['f1_macro']),
            xytext=(5, 5),
            textcoords='offset points',
            fontsize=9,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.3)
        )

    ax.set_xlabel('Custo Total (USD)', fontsize=12, fontweight='bold')
    ax.set_ylabel('F1-score (Macro)', fontsize=12, fontweight='bold')
    ax.set_title('F1-score vs Custo - Comparação de Modelos LLM', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = figures_dir / 'f1_vs_cost.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Gráfico salvo: {output_path}")
    plt.close()


def plot_metrics_comparison(df):
    """Gráfico de barras: Comparação de todas as métricas."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Accuracy
    ax1 = axes[0, 0]
    df_sorted = df.sort_values('accuracy', ascending=True)
    ax1.barh(df_sorted['model'], df_sorted['accuracy'] * 100, color='skyblue')
    ax1.set_xlabel('Accuracy (%)', fontweight='bold')
    ax1.set_title('Accuracy por Modelo', fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)

    # F1-score
    ax2 = axes[0, 1]
    df_sorted = df.sort_values('f1_macro', ascending=True)
    ax2.barh(df_sorted['model'], df_sorted['f1_macro'], color='lightcoral')
    ax2.set_xlabel('F1-score (Macro)', fontweight='bold')
    ax2.set_title('F1-score por Modelo', fontweight='bold')
    ax2.grid(axis='x', alpha=0.3)

    # Latência
    ax3 = axes[1, 0]
    df_sorted = df.sort_values('avg_latency_s', ascending=False)
    ax3.barh(df_sorted['model'], df_sorted['avg_latency_s'], color='lightgreen')
    ax3.set_xlabel('Latência Média (s)', fontweight='bold')
    ax3.set_title('Latência por Modelo', fontweight='bold')
    ax3.grid(axis='x', alpha=0.3)

    # Custo
    ax4 = axes[1, 1]
    df_sorted = df.sort_values('total_cost_usd', ascending=False)
    ax4.barh(df_sorted['model'], df_sorted['total_cost_usd'], color='lightyellow')
    ax4.set_xlabel('Custo Total (USD)', fontweight='bold')
    ax4.set_title('Custo por Modelo', fontweight='bold')
    ax4.grid(axis='x', alpha=0.3)

    plt.tight_layout()
    output_path = figures_dir / 'metrics_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Gráfico salvo: {output_path}")
    plt.close()


def plot_pareto_frontier(df):
    """Gráfico: Fronteira de Pareto (Accuracy vs Custo)."""
    fig, ax = plt.subplots(figsize=(12, 7))

    # Scatter plot
    scatter = ax.scatter(
        df['total_cost_usd'],
        df['accuracy'] * 100,
        s=300,
        alpha=0.6,
        c=df['avg_latency_s'],
        cmap='RdYlGn_r',
        edgecolors='black',
        linewidth=1.5
    )

    # Colorbar para latência
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Latência Média (s)', fontweight='bold')

    # Anotar modelos
    for idx, row in df.iterrows():
        ax.annotate(
            row['model'],
            (row['total_cost_usd'], row['accuracy'] * 100),
            xytext=(8, 8),
            textcoords='offset points',
            fontsize=9,
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.7, edgecolor='black')
        )

    # Identificar fronteira de Pareto (dominância)
    pareto_points = []
    for idx, row in df.iterrows():
        dominated = False
        for _, other in df.iterrows():
            if (other['accuracy'] >= row['accuracy'] and
                other['total_cost_usd'] <= row['total_cost_usd'] and
                (other['accuracy'] > row['accuracy'] or other['total_cost_usd'] < row['total_cost_usd'])):
                dominated = True
                break
        if not dominated:
            pareto_points.append(idx)

    # Destacar pontos de Pareto
    pareto_df = df.iloc[pareto_points].sort_values('total_cost_usd')
    if len(pareto_df) > 1:
        ax.plot(pareto_df['total_cost_usd'], pareto_df['accuracy'] * 100,
                'r--', linewidth=2, alpha=0.7, label='Fronteira de Pareto')
        ax.legend(fontsize=10)

    ax.set_xlabel('Custo Total (USD)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_title('Fronteira de Pareto: Accuracy vs Custo\n(Cor indica Latência)',
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = figures_dir / 'pareto_frontier.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Gráfico salvo: {output_path}")
    plt.close()


def main():
    """Pipeline principal."""
    print("="*80)
    print("📊 VISUALIZAÇÃO DE RESULTADOS")
    print("="*80)

    # Carregar dados
    print("\n📂 Carregando resultados...")
    df = load_results()

    if df is None:
        return

    print(f"   ✓ {len(df)} modelos carregados")

    # Gerar gráficos
    print("\n🎨 Gerando visualizações...")

    plot_accuracy_vs_cost(df)
    plot_accuracy_vs_latency(df)
    plot_f1_vs_cost(df)
    plot_metrics_comparison(df)
    plot_pareto_frontier(df)

    print("\n" + "="*80)
    print("✅ VISUALIZAÇÕES CONCLUÍDAS!")
    print("="*80)
    print(f"\n📁 Gráficos salvos em: {figures_dir}")
    print("\nArquivos gerados:")
    print("  - accuracy_vs_cost.png")
    print("  - accuracy_vs_latency.png")
    print("  - f1_vs_cost.png")
    print("  - metrics_comparison.png")
    print("  - pareto_frontier.png")


if __name__ == '__main__':
    main()
