#!/usr/bin/env python3
"""
Testa BERT Extractive vs Enhanced TextRank
Comparação: Graph-based vs Semântico (Embeddings)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_enhanced import EnhancedTextRankSummarizer, BERTExtractiveSummarizer, SimpleBERTSummarizer
from tqdm import tqdm

def main():
    print("=" * 80)
    print("FASE 2: BERT EXTRACTIVE (Semântico com Embeddings)")
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
    print(f"\n2. Técnicas a comparar:")
    print(f"   - Enhanced TextRank (baseline graph-based)")
    print(f"   - BERT Simple (similaridade pura)")
    print(f"   - BERT + MMR (similaridade + diversidade)")

    techniques = [
        ("Enhanced TextRank", EnhancedTextRankSummarizer(), {"sentences_count": 4}),
        ("BERT Simple", SimpleBERTSummarizer(), {"num_sentences": 4}),
        ("BERT + MMR", BERTExtractiveSummarizer(), {
            "num_sentences": 4,
            "use_mmr": True,
            "diversity_lambda": 0.5
        }),
    ]

    all_results = []

    for tech_name, summarizer, params in techniques:
        print(f"\n3. Avaliando {tech_name}...")
        results = []

        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"   Processando"):
            result = summarizer.evaluate(
                text=row['content'],
                reference=row['reference_summary'],
                **params
            )

            result.update({
                'news_id': row['id'],
                'technique': tech_name,
                'original_length': row['length']
            })

            results.append(result)

        # Estatísticas
        results_df = pd.DataFrame(results)
        successful = results_df[results_df['success'] == True]

        if len(successful) > 0:
            print(f"   Sucesso: {len(successful)}/{len(results_df)}")
            print(f"   ROUGE-1 F1: {successful['rouge1_f1'].mean():.3f} ± {successful['rouge1_f1'].std():.3f}")
            print(f"   ROUGE-2 F1: {successful['rouge2_f1'].mean():.3f} ± {successful['rouge2_f1'].std():.3f}")
            print(f"   ROUGE-L F1: {successful['rougeL_f1'].mean():.3f} ± {successful['rougeL_f1'].std():.3f}")
            print(f"   Latência: {successful['latency'].mean():.2f}s")

        all_results.extend(results)

    # Salvar resultados
    print(f"\n4. Salvando resultados...")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "bert_comparison.csv"
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Comparação final
    print(f"\n5. RANKING FINAL (ROUGE-L F1):")
    print("=" * 80)

    ranking = all_results_df[all_results_df['success'] == True].groupby(
        'technique'
    )['rougeL_f1'].mean().sort_values(ascending=False)

    baseline = ranking.get('Enhanced TextRank', 0.421)  # Nossa baseline

    for tech, score in ranking.items():
        improvement = ((score / baseline) - 1) * 100 if baseline > 0 else 0
        indicator = "🏆" if score == ranking.max() else "⭐" if improvement > 3 else "  "

        if "BERT" in tech:
            label = f"{tech} [SEMÂNTICO]"
        else:
            label = f"{tech} [GRAPH-BASED]"

        print(f"   {indicator} {label:40s} {score:.3f}  ({improvement:+.1f}%)")

    # Ganho BERT
    print("\n" + "=" * 80)
    best_bert = max([ranking.get('BERT Simple', 0), ranking.get('BERT + MMR', 0)])
    if best_bert > baseline:
        gain = ((best_bert / baseline) - 1) * 100
        print(f"✅ BERT superou Enhanced TextRank em {gain:+.1f}%!")
        print(f"   Embedding semântico > Graph-based")
    else:
        loss = ((best_bert / baseline) - 1) * 100
        print(f"⚠️  BERT não superou baseline ({loss:.1f}%)")
        print(f"   Graph-based ainda é melhor para este dataset")

    print("=" * 80)
    print("✅ FASE 2 CONCLUÍDA")
    print("=" * 80)

if __name__ == "__main__":
    main()
