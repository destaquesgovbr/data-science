#!/usr/bin/env python3
"""
Gera amostra para análise humana: notícias + resumos do melhor modelo
Seleciona casos diversos (categorias, tamanhos, qualidade ROUGE)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

def main():
    print("=" * 80)
    print("GERAÇÃO DE AMOSTRA PARA ANÁLISE HUMANA")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_real_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries_real.csv"

    # Carregar resultados do melhor modelo (Nova Pro V2)
    results_file = script_dir.parent / "results" / "all_llms_real_evaluation_complete.csv"

    print(f"\n1. Carregando dados...")
    df_news = pd.read_csv(news_file)
    df_ref = pd.read_csv(ref_file)
    df_results = pd.read_csv(results_file)

    # Filtrar apenas Nova Pro V2
    df_nova_pro = df_results[df_results['technique'] == 'Nova Pro V2'].copy()

    print(f"   Total de resumos Nova Pro V2: {len(df_nova_pro)}")

    # Merge todos os dados
    df = pd.merge(df_news, df_ref[['id', 'reference_summary']], on='id')
    df = pd.merge(df, df_nova_pro[['news_id', 'summary', 'rougeL_f1', 'rouge1_f1', 'rouge2_f1']],
                  left_on='id', right_on='news_id')

    print(f"\n2. Estratégia de amostragem:")
    print(f"   - 5 categorias diferentes (mais frequentes)")
    print(f"   - 3 tamanhos (curta, média, longa)")
    print(f"   - 3 níveis de qualidade ROUGE (alta, média, baixa)")
    print(f"   - Total: ~15 notícias para análise")

    # Selecionar amostra estratificada
    samples = []

    # Top 5 categorias
    top_categories = df['category'].value_counts().head(5).index.tolist()

    for category in top_categories:
        df_cat = df[df['category'] == category].copy()

        if len(df_cat) == 0:
            continue

        # Pegar 3 exemplos dessa categoria com diferentes níveis de ROUGE
        df_cat_sorted = df_cat.sort_values('rougeL_f1')

        # Baixo ROUGE (bottom 30%)
        low_idx = int(len(df_cat_sorted) * 0.15)
        # Médio ROUGE (around 50%)
        mid_idx = int(len(df_cat_sorted) * 0.5)
        # Alto ROUGE (top 20%)
        high_idx = int(len(df_cat_sorted) * 0.85)

        if len(df_cat_sorted) >= 3:
            samples.append(df_cat_sorted.iloc[low_idx])
            samples.append(df_cat_sorted.iloc[mid_idx])
            samples.append(df_cat_sorted.iloc[high_idx])
        elif len(df_cat_sorted) >= 1:
            samples.append(df_cat_sorted.iloc[0])

    df_sample = pd.DataFrame(samples)

    print(f"\n3. Amostra selecionada: {len(df_sample)} notícias")
    print(f"\n   Distribuição por categoria:")
    print(df_sample['category'].value_counts().to_string())

    print(f"\n   Distribuição por qualidade ROUGE-L:")
    print(f"   Baixa  (<0.45): {len(df_sample[df_sample['rougeL_f1'] < 0.45])}")
    print(f"   Média  (0.45-0.55): {len(df_sample[(df_sample['rougeL_f1'] >= 0.45) & (df_sample['rougeL_f1'] < 0.55)])}")
    print(f"   Alta   (>0.55): {len(df_sample[df_sample['rougeL_f1'] >= 0.55])}")

    # Criar arquivo formatado para análise humana
    output_file = script_dir.parent / "data" / "human_evaluation_sample.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Amostra para Análise Humana de Qualidade\n\n")
        f.write("**Modelo:** Amazon Nova Pro V2 (Prompt few-shot, 3 exemplos)\n")
        f.write(f"**ROUGE-L médio:** 0.518\n")
        f.write(f"**Amostra:** {len(df_sample)} notícias (diversas categorias e níveis de qualidade)\n\n")
        f.write("---\n\n")

        for idx, row in df_sample.iterrows():
            f.write(f"## Notícia #{idx+1}\n\n")
            f.write(f"**Categoria:** {row['category']}\n")
            f.write(f"**Tamanho:** {row['length']} caracteres\n")
            f.write(f"**ROUGE-L:** {row['rougeL_f1']:.3f} | ROUGE-1: {row['rouge1_f1']:.3f} | ROUGE-2: {row['rouge2_f1']:.3f}\n\n")

            f.write(f"### 📰 NOTÍCIA ORIGINAL:\n\n")
            f.write(f"{row['content']}\n\n")

            f.write(f"### 🎯 RESUMO REFERÊNCIA (Claude Haiku):\n\n")
            f.write(f"{row['reference_summary']}\n\n")

            f.write(f"### 🤖 RESUMO GERADO (Nova Pro V2):\n\n")
            f.write(f"{row['summary']}\n\n")

            f.write(f"### ✅ AVALIAÇÃO HUMANA:\n\n")
            f.write(f"- [ ] **Fidelidade:** O resumo contém apenas informações presentes na notícia?\n")
            f.write(f"- [ ] **Completude:** Os pontos principais foram capturados?\n")
            f.write(f"- [ ] **Concisão:** O tamanho está adequado (2-3 sentenças)?\n")
            f.write(f"- [ ] **Clareza:** A linguagem está objetiva e compreensível?\n")
            f.write(f"- [ ] **Qualidade geral:** Aceitável para produção?\n\n")
            f.write(f"**Comentários:**\n")
            f.write(f"```\n\n\n```\n\n")
            f.write("---\n\n")

    print(f"\n4. Arquivo gerado: {output_file}")
    print(f"   Tamanho: {output_file.stat().st_size / 1024:.1f} KB")

    # Também salvar CSV para análise programática
    csv_file = script_dir.parent / "data" / "human_evaluation_sample.csv"
    df_sample_export = df_sample[[
        'id', 'title', 'category', 'length',
        'content', 'reference_summary', 'summary',
        'rougeL_f1', 'rouge1_f1', 'rouge2_f1'
    ]].copy()
    df_sample_export.to_csv(csv_file, index=False)
    print(f"   CSV: {csv_file}")

    # Estatísticas da amostra
    print(f"\n5. Estatísticas da amostra:")
    print(f"   ROUGE-L médio: {df_sample['rougeL_f1'].mean():.3f}")
    print(f"   ROUGE-L std: {df_sample['rougeL_f1'].std():.3f}")
    print(f"   ROUGE-L min/max: {df_sample['rougeL_f1'].min():.3f} / {df_sample['rougeL_f1'].max():.3f}")
    print(f"\n   Tamanho médio notícias: {df_sample['length'].mean():.0f} chars")
    print(f"   Tamanho médio resumos gerados: {df_sample['summary'].str.len().mean():.0f} chars")
    print(f"   Tamanho médio resumos referência: {df_sample['reference_summary'].str.len().mean():.0f} chars")

    print("\n" + "=" * 80)
    print("✅ AMOSTRA GERADA COM SUCESSO")
    print("=" * 80)
    print(f"\n📋 Próximo passo: Revisar o arquivo {output_file.name}")
    print(f"   e avaliar a qualidade dos resumos gerados.")

if __name__ == "__main__":
    main()
