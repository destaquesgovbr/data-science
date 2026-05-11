#!/usr/bin/env python3
"""
Avalia técnicas extractive (TextRank, LexRank) no dataset completo

Calcula ROUGE scores comparando com referências do Claude
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers import TextRankSummarizer, LexRankSummarizer
from tqdm import tqdm
import argparse

def main():
    parser = argparse.ArgumentParser(description='Avalia técnicas extractive')
    parser.add_argument('--technique', type=str, default='all',
                       choices=['textrank', 'lexrank', 'all'],
                       help='Técnica a avaliar')
    parser.add_argument('--sentences', type=int, nargs='+', default=[2, 3, 5],
                       help='Números de sentenças a testar')
    parser.add_argument('--sample', type=int, default=None,
                       help='Testar apenas N notícias (para debug)')

    args = parser.parse_args()

    print("=" * 80)
    print("AVALIAÇÃO DE TÉCNICAS EXTRACTIVE")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries.csv"

    print(f"\n1. Carregando dados...")
    df_news = pd.read_csv(news_file)
    df_ref = pd.read_csv(ref_file)

    # Merge
    df = pd.merge(df_news[['id', 'title', 'content', 'level_1_label', 'length']],
                  df_ref[['id', 'reference_summary']],
                  on='id')

    # Filtrar apenas referências válidas
    df = df[df['reference_summary'].notna() & (df['reference_summary'] != '')].copy()

    print(f"   Notícias: {len(df)}")
    print(f"   Com referências válidas: {len(df)}")

    # Sample se especificado
    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42)
        print(f"   Sample para teste: {len(df)}")

    # Técnicas a avaliar
    techniques = []
    if args.technique in ['textrank', 'all']:
        techniques.append(('TextRank', TextRankSummarizer()))
    if args.technique in ['lexrank', 'all']:
        techniques.append(('LexRank', LexRankSummarizer()))

    print(f"\n2. Técnicas: {[t[0] for t in techniques]}")
    print(f"   Sentenças: {args.sentences}")

    # Avaliar
    all_results = []

    for tech_name, summarizer in techniques:
        print(f"\n3. Avaliando {tech_name}...")

        for n_sentences in args.sentences:
            print(f"\n   Com {n_sentences} sentenças:")

            results = []
            for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"   {tech_name}-{n_sentences}"):
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

            if len(successful) > 0:
                print(f"      Sucesso: {len(successful)}/{len(results_df)}")
                print(f"      ROUGE-1 F1: {successful['rouge1_f1'].mean():.3f} ± {successful['rouge1_f1'].std():.3f}")
                print(f"      ROUGE-2 F1: {successful['rouge2_f1'].mean():.3f} ± {successful['rouge2_f1'].std():.3f}")
                print(f"      ROUGE-L F1: {successful['rougeL_f1'].mean():.3f} ± {successful['rougeL_f1'].std():.3f}")
                print(f"      Latência média: {successful['latency'].mean():.3f}s")

            all_results.extend(results)

    # Salvar resultados completos
    print(f"\n4. Salvando resultados...")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "extractive_evaluation.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Ranking
    print("\n5. Ranking geral (ROUGE-L F1):")
    ranking = all_results_df[all_results_df['success'] == True].groupby(
        ['technique', 'sentences_count']
    )['rougeL_f1'].mean().sort_values(ascending=False)

    for (tech, sents), score in ranking.head(10).items():
        print(f"   {tech:12s} ({sents} sent): {score:.3f}")

    print("\n" + "=" * 80)
    print("✅ AVALIAÇÃO CONCLUÍDA")
    print("=" * 80)

if __name__ == "__main__":
    main()
