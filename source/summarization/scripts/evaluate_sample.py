#!/usr/bin/env python3
"""
Avalia TextRank na amostra de 50 notícias com referências válidas
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers import TextRankSummarizer
from tqdm import tqdm

def main():
    print("=" * 80)
    print("AVALIAÇÃO TEXTRANK - AMOSTRA (50 notícias)")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries_sample.csv"

    print(f"\n1. Carregando dados...")
    df_news = pd.read_csv(news_file)
    df_ref = pd.read_csv(ref_file)

    # Merge
    df = pd.merge(
        df_news[['id', 'title', 'content', 'level_1_label', 'length']],
        df_ref[['id', 'reference_summary']],
        on='id'
    )

    # Filtrar válidas
    df = df[df['reference_summary'].notna() & (df['reference_summary'] != '')].copy()
    print(f"   Total: {len(df)} notícias com referências válidas")

    # Inicializar TextRank
    print(f"\n2. Avaliando TextRank com diferentes configurações...")
    summarizer = TextRankSummarizer()

    all_results = []
    sentence_counts = [2, 3, 5]

    for n_sentences in sentence_counts:
        print(f"\n   TextRank com {n_sentences} sentenças:")
        results = []

        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"   Processando"):
            result = summarizer.evaluate(
                text=row['content'],
                reference=row['reference_summary'],
                sentences_count=n_sentences
            )

            result.update({
                'news_id': row['id'],
                'title': row['title'],
                'category': row['level_1_label'],
                'original_length': row['length'],
                'sentences_count': n_sentences
            })

            results.append(result)

        # Estatísticas
        results_df = pd.DataFrame(results)
        successful = results_df[results_df['success'] == True]

        print(f"      Sucesso: {len(successful)}/{len(results_df)}")
        print(f"      ROUGE-1 F1: {successful['rouge1_f1'].mean():.3f} ± {successful['rouge1_f1'].std():.3f}")
        print(f"      ROUGE-2 F1: {successful['rouge2_f1'].mean():.3f} ± {successful['rouge2_f1'].std():.3f}")
        print(f"      ROUGE-L F1: {successful['rougeL_f1'].mean():.3f} ± {successful['rougeL_f1'].std():.3f}")

        all_results.extend(results)

    # Salvar
    print(f"\n3. Salvando resultados...")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "textrank_sample_evaluation.csv"
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Melhor configuração
    print(f"\n4. Melhor configuração:")
    best_config = all_results_df[all_results_df['success'] == True].groupby(
        'sentences_count'
    )['rougeL_f1'].mean().sort_values(ascending=False).iloc[0]

    best_n = all_results_df[all_results_df['success'] == True].groupby(
        'sentences_count'
    )['rougeL_f1'].mean().idxmax()

    print(f"   TextRank com {best_n} sentenças: ROUGE-L = {best_config:.3f}")

    print("\n" + "=" * 80)
    print("✅ AVALIAÇÃO CONCLUÍDA")
    print("=" * 80)

if __name__ == "__main__":
    main()
