#!/usr/bin/env python3
"""
FASE FINAL: Testa Prompt V3 nos 3 melhores modelos
Objetivo: Atingir ROUGE-L > 0.55
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_abstractive_v3 import (
    NovaProSummarizerV3,
    Nova2LiteSummarizerV3,
    ClaudeHaiku4SummarizerV3
)
from tqdm import tqdm
import time

def main():
    print("=" * 80)
    print("FASE FINAL - PROMPT V3 (5-Shot + Gov.BR específico)")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_real_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries_real.csv"

    print(f"\n1. Carregando 300 notícias reais do gov.br...")
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

    # Modelos a testar (top 3 com Prompt V3)
    print(f"\n2. Testando TOP 3 modelos com Prompt V3:")
    print(f"\n   COMPARAÇÃO:")
    print(f"   - Nova Pro V2:        0.518 → V3: ???")
    print(f"   - Nova 2 Lite V2:     0.502 → V3: ???")
    print(f"   - Haiku 4.5 V2:       0.485 → V3: ???")
    print(f"\n   TARGET: 0.550 (faltam 0.032 do líder atual)")

    techniques = [
        ("Nova Pro V3", NovaProSummarizerV3(), {"target_sentences": 3}),
        ("Nova 2 Lite V3", Nova2LiteSummarizerV3(), {"target_sentences": 3}),
        ("Haiku 4.5 V3", ClaudeHaiku4SummarizerV3(), {"target_sentences": 3}),
    ]

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
    output_file = script_dir.parent / "results" / "prompt_v3_evaluation.csv"
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Análise comparativa V2 vs V3
    print(f"\n{'=' * 80}")
    print(f"5. COMPARAÇÃO: Prompt V2 vs V3")
    print(f"{'=' * 80}")

    ranking_v3 = all_results_df[all_results_df['success'] == True].groupby(
        'technique'
    )['rougeL_f1'].mean().sort_values(ascending=False)

    # Scores V2 (baseline)
    v2_scores = {
        'Nova Pro': 0.518,
        'Nova 2 Lite': 0.502,
        'Haiku 4.5': 0.485
    }

    target = 0.55

    print(f"\n{'Modelo':<20} {'V2 (3-shot)':<12} {'V3 (5-shot)':<12} {'Ganho':<12} {'vs Target'}")
    print("-" * 75)

    for model_base, v2_score in v2_scores.items():
        v3_key = [k for k in ranking_v3.index if model_base in k]
        if v3_key:
            v3_score = ranking_v3[v3_key[0]]
            gain = v3_score - v2_score
            gain_pct = (gain / v2_score) * 100
            vs_target = v3_score - target

            indicator = "🎯" if v3_score >= target else ("✅" if gain > 0 else "⚠️")

            print(f"{indicator} {model_base:<18} {v2_score:.3f}        {v3_score:.3f}        {gain:+.3f} ({gain_pct:+.1f}%)   {vs_target:+.3f}")

    # Melhor resultado
    print(f"\n{'=' * 80}")
    print("6. RESULTADO FINAL:")
    print(f"{'=' * 80}")

    if len(ranking_v3) > 0:
        best_model = ranking_v3.index[0]
        best_score = ranking_v3.iloc[0]
        gap = target - best_score

        print(f"\n🏆 MELHOR MODELO: {best_model}")
        print(f"   ROUGE-L: {best_score:.3f}")

        if best_score >= target:
            print(f"\n   🎉 TARGET ATINGIDO! Superou {target:.3f} em {((best_score/target)-1)*100:.1f}%")
            print(f"\n   ✅ Modelo pronto para produção!")
            print(f"\n   Ganho total sobre baseline extractive (0.381): {((best_score/0.381)-1)*100:.1f}%")
        else:
            print(f"\n   Gap para target ({target:.3f}): {gap:.3f} ({abs(gap/target)*100:.1f}%)")
            print(f"\n   Evolução do experimento:")
            print(f"   - Baseline Extractive:     0.381")
            print(f"   - Melhor LLM V2 (3-shot):  0.518 (+36.0%)")
            print(f"   - Melhor LLM V3 (5-shot):  {best_score:.3f} (+{((best_score/0.381)-1)*100:.1f}%)")

            if gap > 0.01:
                print(f"\n   Próximas opções:")
                print(f"   1. Abordagem híbrida (extractive + abstractive)")
                print(f"   2. Fine-tuning do modelo no domínio gov.br")
                print(f"   3. RAG com exemplos dinâmicos")

        # Estatísticas de produção
        best_results = all_results_df[
            (all_results_df['technique'] == best_model) &
            (all_results_df['success'] == True)
        ]

        if len(best_results) > 0:
            print(f"\n{'=' * 80}")
            print("7. ESTATÍSTICAS DE PRODUÇÃO:")
            print(f"{'=' * 80}")

            avg_latency = best_results['latency'].mean()
            total_time = best_results['latency'].sum()

            cost_map = {
                'Nova Pro': 0.008,
                'Nova 2 Lite': 0.0006,
                'Haiku': 0.0008
            }

            cost_per_call = 0.001
            for key, cost in cost_map.items():
                if key in best_model:
                    cost_per_call = cost
                    break

            total_cost = len(best_results) * cost_per_call

            print(f"\n   Modelo: {best_model}")
            print(f"   Latência média: {avg_latency:.2f}s")
            print(f"   Tempo total (300 resumos): {total_time/60:.1f} min")
            print(f"   Custo total: ~${total_cost:.2f}")
            print(f"   Custo por resumo: ~${cost_per_call:.4f}")
            print(f"   Custo para 10k resumos/mês: ~${cost_per_call * 10000:.2f}")
            print(f"   Throughput: ~{3600/avg_latency:.0f} resumos/hora")

    print("\n" + "=" * 80)
    print("✅ TESTE PROMPT V3 CONCLUÍDO")
    print("=" * 80)

if __name__ == "__main__":
    main()
