#!/usr/bin/env python3
"""
Testa apenas os 5 LLMs que falharam (IDs corrigidos)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_abstractive_v2 import (
    ClaudeSonnet46SummarizerV2,
    ClaudeOpus47SummarizerV2,
    NovaProSummarizerV2,
    Llama4MaverickSummarizerV2,
    MistralLarge3SummarizerV2
)
from tqdm import tqdm
import time

def main():
    print("=" * 80)
    print("TESTE DOS 5 LLMs QUE FALHARAM (IDs corrigidos)")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_real_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries_real.csv"

    print(f"\n1. Carregando 300 notícias reais...")
    df_news = pd.read_csv(news_file)
    df_ref = pd.read_csv(ref_file)

    df = pd.merge(
        df_news[['id', 'title', 'content', 'category', 'subcategory', 'length', 'agency']],
        df_ref[['id', 'reference_summary']],
        on='id'
    )

    df = df[
        (df['reference_summary'].notna()) &
        (df['reference_summary'] != '')
    ].copy()

    print(f"   Total: {len(df)} notícias")

    # Modelos a testar (5 que falharam)
    print(f"\n2. Testando 5 LLMs com IDs corrigidos:")

    techniques = [
        ("Sonnet 4.6 V2", ClaudeSonnet46SummarizerV2(), {"target_sentences": 3}),
        ("Opus 4.7 V2", ClaudeOpus47SummarizerV2(), {"target_sentences": 3}),
        ("Nova Pro V2", NovaProSummarizerV2(), {"target_sentences": 3}),
        ("Llama 4 Maverick V2", Llama4MaverickSummarizerV2(), {"target_sentences": 3}),
        ("Mistral Large 3 V2", MistralLarge3SummarizerV2(), {"target_sentences": 3}),
    ]

    for name, _, _ in techniques:
        print(f"   - {name}")

    print(f"\n   Estimativa: ~{len(techniques) * len(df) * 2 / 60:.0f} min")

    all_results = []

    for tech_name, summarizer, params in techniques:
        print(f"\n{'=' * 80}")
        print(f"3. Avaliando {tech_name}...")
        print(f"{'=' * 80}")
        results = []

        delay = 0.5

        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"   Processando"):
            try:
                result = summarizer.evaluate(
                    text=row['content'],
                    reference=row['reference_summary'],
                    **params
                )

                result.update({
                    'news_id': row['id'],
                    'technique': tech_name,
                    'category': row['category'],
                    'subcategory': row['subcategory'],
                    'agency': row['agency'],
                    'original_length': row['length']
                })

                results.append(result)
                time.sleep(delay)

            except Exception as e:
                error_msg = str(e)[:150]
                print(f"\n   ⚠️  Erro na notícia {row['id']}: {error_msg}")
                results.append({
                    'news_id': row['id'],
                    'technique': tech_name,
                    'category': row['category'],
                    'subcategory': row['subcategory'],
                    'agency': row['agency'],
                    'original_length': row['length'],
                    'success': False,
                    'error': str(e),
                    'rouge1_f1': 0,
                    'rouge2_f1': 0,
                    'rougeL_f1': 0,
                    'latency': 0
                })

        # Estatísticas
        results_df = pd.DataFrame(results)
        successful = results_df[results_df['success'] == True]

        if len(successful) > 0:
            print(f"\n   ✅ Sucesso: {len(successful)}/{len(results_df)}")
            print(f"   ROUGE-L F1: {successful['rougeL_f1'].mean():.3f} ± {successful['rougeL_f1'].std():.3f}")
            print(f"   ROUGE-1 F1: {successful['rouge1_f1'].mean():.3f}")
            print(f"   ROUGE-2 F1: {successful['rouge2_f1'].mean():.3f}")
            print(f"   Latência: {successful['latency'].mean():.2f}s")
        else:
            print(f"\n   ❌ FALHOU: Nenhum sucesso!")

        all_results.extend(results)

    # Salvar resultados
    print(f"\n{'=' * 80}")
    print(f"4. Salvando resultados...")
    print(f"{'=' * 80}")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "missing_llms_real_evaluation.csv"
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Carregar resultados anteriores e combinar
    print(f"\n5. Combinando com resultados anteriores...")
    previous_file = script_dir.parent / "results" / "all_llms_real_evaluation.csv"
    df_previous = pd.read_csv(previous_file)

    # Remover modelos que falharam anteriormente
    failed_models = ['Sonnet 4.6 V2', 'Opus 4.7 V2', 'Nova Premierer V2', 'Llama 4 Maverick V2', 'Mistral Large 3 V2']
    df_previous_clean = df_previous[~df_previous['technique'].isin(failed_models)]

    # Combinar
    df_combined = pd.concat([df_previous_clean, all_results_df], ignore_index=True)
    combined_file = script_dir.parent / "results" / "all_llms_real_evaluation_complete.csv"
    df_combined.to_csv(combined_file, index=False)
    print(f"   Arquivo combinado: {combined_file}")

    # Ranking final
    print(f"\n{'=' * 80}")
    print(f"6. RANKING FINAL COMPLETO - 9 LLMs V2")
    print(f"{'=' * 80}")

    ranking = df_combined[df_combined['success'] == True].groupby(
        'technique'
    ).agg({
        'rougeL_f1': ['mean', 'std', 'count'],
        'rouge1_f1': 'mean',
        'rouge2_f1': 'mean',
        'latency': 'mean'
    })

    ranking.columns = ['_'.join(col).strip() for col in ranking.columns.values]
    ranking = ranking.sort_values('rougeL_f1_mean', ascending=False)

    target = 0.55

    print(f"\n{'Rank':<6} {'Modelo':<30} {'ROUGE-L':<10} {'ROUGE-1':<10} {'Latência':<10} {'vs Target'}")
    print("-" * 85)

    for rank, (tech, row) in enumerate(ranking.iterrows(), 1):
        score = row['rougeL_f1_mean']
        vs_target = score - target

        if score >= target:
            indicator = "🎯"
        elif rank == 1:
            indicator = "🏆"
        elif rank == 2:
            indicator = "🥈"
        elif rank == 3:
            indicator = "🥉"
        else:
            indicator = f"#{rank}"

        print(f"  {indicator:<6} {tech:<30} {score:.3f}      {row['rouge1_f1_mean']:.3f}      {row['latency_mean']:.2f}s       {vs_target:+.3f}")

    # Melhor modelo
    best_model = ranking.index[0]
    best_score = ranking.iloc[0]['rougeL_f1_mean']

    print(f"\n{'=' * 80}")
    print(f"7. VENCEDOR:")
    print(f"{'=' * 80}")
    print(f"\n🏆 {best_model}: {best_score:.3f}")

    if best_score >= target:
        print(f"   ✅ TARGET ATINGIDO! (+{((best_score/target)-1)*100:.1f}%)")
    else:
        gap = target - best_score
        print(f"   Gap: {gap:.3f} ({abs(gap/target)*100:.1f}%)")

    print("\n" + "=" * 80)
    print("✅ TESTE COMPLETO CONCLUÍDO")
    print("=" * 80)

if __name__ == "__main__":
    main()
