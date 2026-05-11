#!/usr/bin/env python3
"""
Testa melhorias de quick wins no TextRank
Compara: Baseline vs Position Bias vs Enhanced (Full)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers import TextRankSummarizer
from summarizers_enhanced import EnhancedTextRankSummarizer, PositionBiasedTextRank
from tqdm import tqdm

def main():
    print("=" * 80)
    print("TESTE: QUICK WINS NO TEXTRANK")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries_sample.csv"

    print(f"\n1. Carregando amostra de 50 notícias...")
    df_news = pd.read_csv(news_file)
    df_ref = pd.read_csv(ref_file)

    df = pd.merge(
        df_news[['id', 'title', 'content', 'level_1_label', 'length']],
        df_ref[['id', 'reference_summary']],
        on='id'
    )

    df = df[df['reference_summary'].notna()].copy()
    print(f"   Total: {len(df)} notícias")

    # Técnicas a testar
    techniques = [
        ("Baseline TextRank", TextRankSummarizer(), {}),
        ("Position Biased", PositionBiasedTextRank(), {}),
        ("Enhanced (Full)", EnhancedTextRankSummarizer(), {
            "apply_position_bias": True,
            "remove_redundancy": True,
            "min_sentence_length": 50
        }),
    ]

    print(f"\n2. Testando técnicas:")
    for name, _, _ in techniques:
        print(f"   - {name}")

    # Testar diferentes números de sentenças
    sentence_counts = [3, 4]  # Focar nas melhores configs

    all_results = []

    for n_sentences in sentence_counts:
        print(f"\n3. Avaliando com {n_sentences} sentenças:")
        print("-" * 80)

        for tech_name, summarizer, extra_params in techniques:
            print(f"\n   {tech_name}:")
            results = []

            for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"      Processando"):
                params = {"sentences_count": n_sentences, **extra_params}

                result = summarizer.evaluate(
                    text=row['content'],
                    reference=row['reference_summary'],
                    **params
                )

                result.update({
                    'news_id': row['id'],
                    'technique': tech_name,
                    'sentences_count': n_sentences,
                    'original_length': row['length']
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

            all_results.extend(results)

    # Salvar resultados
    print(f"\n4. Salvando resultados...")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "quick_wins_comparison.csv"
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Comparação final
    print(f"\n5. RANKING FINAL (ROUGE-L F1):")
    print("=" * 80)

    ranking = all_results_df[all_results_df['success'] == True].groupby(
        ['technique', 'sentences_count']
    )['rougeL_f1'].mean().sort_values(ascending=False)

    baseline_3 = ranking.get(('Baseline TextRank', 3), 0)

    for (tech, sents), score in ranking.items():
        improvement = ((score / baseline_3) - 1) * 100 if baseline_3 > 0 else 0
        indicator = "🏆" if score == ranking.max() else "⭐" if improvement > 3 else "  "
        print(f"   {indicator} {tech:25s} ({sents} sent): {score:.3f}  ({improvement:+.1f}%)")

    print("\n" + "=" * 80)
    print("✅ TESTE CONCLUÍDO")
    print("=" * 80)

    # Melhor ganho
    best_improvement = ranking.max() / baseline_3 - 1 if baseline_3 > 0 else 0
    print(f"\n📈 Melhor ganho sobre baseline: {best_improvement*100:+.1f}%")

if __name__ == "__main__":
    main()
