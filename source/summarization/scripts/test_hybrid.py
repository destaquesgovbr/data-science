#!/usr/bin/env python3
"""
Testa abordagem híbrida (Extractive + Abstractive) nos 3 melhores modelos
Objetivo: Atingir ROUGE-L > 0.55
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_hybrid import (
    HybridNovaProV2,
    HybridNova2LiteV2,
    HybridClaudeHaiku4V2
)
from tqdm import tqdm
import time

def main():
    print("=" * 80)
    print("ABORDAGEM HÍBRIDA - Extractive + Abstractive (Prompt V2)")
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

    print(f"\n2. Pipeline Híbrido:")
    print(f"   ETAPA 1: Enhanced TextRank seleciona top-6 sentenças relevantes")
    print(f"   ETAPA 2: LLM (Prompt V2) refina em 2-3 sentenças finais")
    print(f"\n   Vantagens:")
    print(f"   - Reduz ruído do texto original (extractive filtra)")
    print(f"   - LLM trabalha com input mais focado")
    print(f"   - Combina precisão extractive + fluência abstractive")

    print(f"\n3. Testando TOP 3 modelos:")
    print(f"\n   BASELINE (Abstractive puro V2):")
    print(f"   - Nova Pro V2:        0.518 → Hybrid: ???")
    print(f"   - Nova 2 Lite V2:     0.502 → Hybrid: ???")
    print(f"   - Haiku 4.5 V2:       0.485 → Hybrid: ???")
    print(f"\n   TARGET: 0.550 (precisamos +0.032)")

    techniques = [
        ("Hybrid Nova Pro V2", HybridNovaProV2(), {"extractive_sentences": 6, "target_sentences": 3}),
        ("Hybrid Nova 2 Lite V2", HybridNova2LiteV2(), {"extractive_sentences": 6, "target_sentences": 3}),
        ("Hybrid Haiku 4.5 V2", HybridClaudeHaiku4V2(), {"extractive_sentences": 6, "target_sentences": 3}),
    ]

    print(f"\n   Estimativa: ~{len(techniques) * len(df) * 2 / 60:.0f} min")

    all_results = []

    for tech_name, summarizer, params in techniques:
        print(f"\n{'=' * 80}")
        print(f"4. Avaliando {tech_name}...")
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
    print(f"5. Salvando resultados...")
    print(f"{'=' * 80}")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "hybrid_evaluation.csv"
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Análise comparativa
    print(f"\n{'=' * 80}")
    print(f"6. COMPARAÇÃO: Abstractive Puro vs Híbrido")
    print(f"{'=' * 80}")

    ranking = all_results_df[all_results_df['success'] == True].groupby(
        'technique'
    )['rougeL_f1'].mean().sort_values(ascending=False)

    pure_scores = {
        'Nova Pro': 0.518,
        'Nova 2 Lite': 0.502,
        'Haiku 4.5': 0.485
    }

    target = 0.55

    print(f"\n{'Modelo':<25} {'Puro V2':<10} {'Híbrido':<10} {'Ganho':<15} {'vs Target'}")
    print("-" * 80)

    for model_base, pure_score in pure_scores.items():
        hybrid_key = [k for k in ranking.index if model_base in k]
        if hybrid_key:
            hybrid_score = ranking[hybrid_key[0]]
            gain = hybrid_score - pure_score
            gain_pct = (gain / pure_score) * 100
            vs_target = hybrid_score - target

            if hybrid_score >= target:
                indicator = "🎯"
            elif gain > 0.01:
                indicator = "🚀"
            elif gain > 0:
                indicator = "✅"
            elif gain < -0.01:
                indicator = "⚠️"
            else:
                indicator = "➡️"

            print(f"{indicator} {model_base:<23} {pure_score:.3f}      {hybrid_score:.3f}      {gain:+.3f} ({gain_pct:+.1f}%)    {vs_target:+.3f}")

    # Resultado final
    print(f"\n{'=' * 80}")
    print("7. RESULTADO FINAL:")
    print(f"{'=' * 80}")

    if len(ranking) > 0:
        best_model = ranking.index[0]
        best_score = ranking.iloc[0]
        gap = target - best_score

        print(f"\n🏆 MELHOR MODELO: {best_model}")
        print(f"   ROUGE-L: {best_score:.3f}")

        if best_score >= target:
            print(f"\n   🎉🎯 TARGET ATINGIDO! 🎯🎉")
            print(f"   Superou {target:.3f} em {((best_score/target)-1)*100:.1f}%!")
            print(f"\n   ✅ Modelo pronto para produção!")
            print(f"\n   📊 Evolução completa do experimento:")
            print(f"   ┌─────────────────────────────────────────────┐")
            print(f"   │ Baseline Extractive:          0.381         │")
            print(f"   │ Enhanced TextRank:            0.399 (+4.7%) │")
            print(f"   │ Melhor LLM Puro V2:           0.518 (+36%)  │")
            print(f"   │ Melhor Híbrido:               {best_score:.3f} (+{((best_score/0.381)-1)*100:.1f}%) │")
            print(f"   │ TARGET FINAL:                 0.550 ✅       │")
            print(f"   └─────────────────────────────────────────────┘")
        else:
            print(f"\n   Gap para target ({target:.3f}): {gap:.3f} ({abs(gap/target)*100:.1f}%)")
            print(f"\n   📊 Evolução:")
            print(f"   - Baseline Extractive:       0.381")
            print(f"   - Enhanced TextRank:         0.399 (+4.7%)")
            print(f"   - Melhor LLM Puro V2:        0.518 (+36.0%)")
            print(f"   - Melhor Híbrido:            {best_score:.3f} (+{((best_score/0.381)-1)*100:.1f}%)")

            if gap <= 0.015:
                print(f"\n   💡 MUITO PRÓXIMO! Gap de apenas {gap:.3f}")
                print(f"   Recomendação: Aceitar resultado (ganho excelente de {((best_score/0.381)-1)*100:.0f}%)")
            else:
                print(f"\n   Próxima opção: Fine-tuning no domínio gov.br")

        # Estatísticas de produção
        best_results = all_results_df[
            (all_results_df['technique'] == best_model) &
            (all_results_df['success'] == True)
        ]

        if len(best_results) > 0:
            print(f"\n{'=' * 80}")
            print("8. ESTATÍSTICAS DE PRODUÇÃO (MELHOR MODELO):")
            print(f"{'=' * 80}")

            avg_latency = best_results['latency'].mean()

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

            print(f"\n   Pipeline: Enhanced TextRank (0.03s) + LLM ({avg_latency:.2f}s)")
            print(f"   Latência total: ~{avg_latency + 0.03:.2f}s por resumo")
            print(f"   Throughput: ~{3600/(avg_latency+0.03):.0f} resumos/hora")
            print(f"   Custo: ${cost_per_call:.4f} por resumo (apenas LLM)")
            print(f"   Custo 10k resumos/mês: ${cost_per_call * 10000:.2f}")

    print("\n" + "=" * 80)
    print("✅ TESTE HÍBRIDO CONCLUÍDO")
    print("=" * 80)

if __name__ == "__main__":
    main()
