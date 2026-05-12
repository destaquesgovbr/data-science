#!/usr/bin/env python3
"""
FASE 3B: Prompt Engineering - Teste V2 (Few-Shot)
Compara Prompt V1 (zero-shot) vs V2 (few-shot) nos 3 melhores modelos
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_abstractive import (
    Nova2LiteSummarizer,
    ClaudeHaiku4Summarizer,
    Llama33Summarizer
)
from summarizers_abstractive_v2 import (
    Nova2LiteSummarizerV2,
    ClaudeHaiku4SummarizerV2,
    Llama33SummarizerV2
)
from tqdm import tqdm
import time

def main():
    print("=" * 80)
    print("FASE 3B: PROMPT ENGINEERING - V1 vs V2")
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
    print(f"\n2. Comparação: Prompt V1 (zero-shot) vs V2 (few-shot)")
    print(f"\n   MODELOS SELECIONADOS:")
    print(f"   - Amazon Nova 2 Lite (V1 baseline: 0.481)")
    print(f"   - Claude Haiku 4.5 (V1 baseline: 0.471)")
    print(f"   - Llama 3.3 70B (V1 baseline: 0.458)")

    techniques = [
        # V1 - Baseline (zero-shot)
        ("Nova 2 Lite V1", Nova2LiteSummarizer(), {"target_sentences": 3}, True),
        ("Haiku 4.5 V1", ClaudeHaiku4Summarizer(), {"target_sentences": 3}, True),
        ("Llama 3.3 V1", Llama33Summarizer(), {"target_sentences": 3}, True),

        # V2 - Few-shot
        ("Nova 2 Lite V2", Nova2LiteSummarizerV2(), {"target_sentences": 3}, True),
        ("Haiku 4.5 V2", ClaudeHaiku4SummarizerV2(), {"target_sentences": 3}, True),
        ("Llama 3.3 V2", Llama33SummarizerV2(), {"target_sentences": 3}, True),
    ]

    all_results = []

    for tech_name, summarizer, params, is_api in techniques:
        print(f"\n{'=' * 80}")
        print(f"3. Avaliando {tech_name}...")
        print(f"{'=' * 80}")
        results = []

        # Rate limiting
        delay = 0.5 if is_api else 0

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
                    'original_length': row['length']
                })

                results.append(result)

                # Rate limiting
                if is_api and delay > 0:
                    time.sleep(delay)

            except Exception as e:
                error_msg = str(e)[:150]
                print(f"\n   ⚠️  Erro na notícia {row['id']}: {error_msg}")
                results.append({
                    'news_id': row['id'],
                    'technique': tech_name,
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
            print(f"   ROUGE-1 F1: {successful['rouge1_f1'].mean():.3f} ± {successful['rouge1_f1'].std():.3f}")
            print(f"   ROUGE-2 F1: {successful['rouge2_f1'].mean():.3f} ± {successful['rouge2_f1'].std():.3f}")
            print(f"   ROUGE-L F1: {successful['rougeL_f1'].mean():.3f} ± {successful['rougeL_f1'].std():.3f}")
            print(f"   Latência: {successful['latency'].mean():.2f}s")
        else:
            print(f"\n   ❌ FALHOU: Nenhum sucesso!")

        all_results.extend(results)

    # Salvar resultados
    print(f"\n{'=' * 80}")
    print(f"4. Salvando resultados...")
    print(f"{'=' * 80}")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "prompt_v1_vs_v2_comparison.csv"
    output_file.parent.mkdir(exist_ok=True)
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Análise comparativa
    print(f"\n{'=' * 80}")
    print(f"5. ANÁLISE: V1 (Zero-Shot) vs V2 (Few-Shot)")
    print(f"{'=' * 80}")

    ranking = all_results_df[all_results_df['success'] == True].groupby(
        'technique'
    )['rougeL_f1'].mean().sort_values(ascending=False)

    target = 0.55

    print(f"\n{'Rank':<6} {'Modelo':<25} {'Versão':<10} {'ROUGE-L':<10} {'vs V1':<12} {'vs Target'}")
    print("-" * 80)

    # Mapear V1 baselines
    v1_baselines = {
        'Nova 2 Lite': ranking.get('Nova 2 Lite V1', 0),
        'Haiku 4.5': ranking.get('Haiku 4.5 V1', 0),
        'Llama 3.3': ranking.get('Llama 3.3 V1', 0),
    }

    for rank, (tech, score) in enumerate(ranking.items(), 1):
        # Extrair nome base e versão
        if 'V2' in tech:
            base_name = tech.replace(' V2', '')
            version = "V2 (few)"
            baseline = v1_baselines.get(base_name, 0)
            improvement = ((score / baseline) - 1) * 100 if baseline > 0 else 0
            vs_v1 = f"{improvement:+.1f}%"
        else:
            base_name = tech.replace(' V1', '')
            version = "V1 (zero)"
            vs_v1 = "baseline"
            improvement = 0

        vs_target = score - target

        # Indicador
        if score >= target:
            indicator = "🎯"
        elif rank == 1:
            indicator = "🏆"
        elif improvement > 3:
            indicator = "⭐"
        else:
            indicator = "  "

        print(f"{indicator} #{rank:<4} {base_name:<25} {version:<10} {score:.3f}      {vs_v1:<12} {vs_target:+.3f}")

    # Análise de ganhos
    print(f"\n{'=' * 80}")
    print("6. GANHOS DO PROMPT V2 (Few-Shot):")
    print(f"{'=' * 80}")

    for model in ['Nova 2 Lite', 'Haiku 4.5', 'Llama 3.3']:
        v1_score = ranking.get(f'{model} V1', 0)
        v2_score = ranking.get(f'{model} V2', 0)

        if v1_score > 0 and v2_score > 0:
            gain = ((v2_score / v1_score) - 1) * 100
            abs_gain = v2_score - v1_score

            if gain > 3:
                emoji = "🚀"
            elif gain > 0:
                emoji = "✅"
            else:
                emoji = "⚠️"

            print(f"\n{emoji} {model}:")
            print(f"   V1: {v1_score:.3f} → V2: {v2_score:.3f}")
            print(f"   Ganho: {abs_gain:+.3f} ({gain:+.1f}%)")

    # Melhor modelo overall
    print(f"\n{'=' * 80}")
    print("7. MELHOR MODELO APÓS OTIMIZAÇÃO:")
    print(f"{'=' * 80}")

    best_model = ranking.index[0]
    best_score = ranking.iloc[0]
    gap = target - best_score

    print(f"\n🏆 {best_model}: ROUGE-L = {best_score:.3f}")

    if best_score >= target:
        print(f"   ✅ TARGET ATINGIDO! (+{((best_score/target)-1)*100:.1f}%)")
    else:
        print(f"   Gap para target (0.55): {gap:.3f} ({(gap/target)*100:.1f}%)")

    # Estatísticas finais
    print(f"\n{'=' * 80}")
    print("8. ESTATÍSTICAS FINAIS:")
    print(f"{'=' * 80}")

    v2_models = [k for k in ranking.index if 'V2' in k]
    if v2_models:
        v2_mean = ranking[v2_models].mean()
        v1_models = [k for k in ranking.index if 'V1' in k]
        v1_mean = ranking[v1_models].mean()
        overall_gain = ((v2_mean / v1_mean) - 1) * 100

        print(f"\n   Média V1 (zero-shot): {v1_mean:.3f}")
        print(f"   Média V2 (few-shot): {v2_mean:.3f}")
        print(f"   Ganho médio: {overall_gain:+.1f}%")

    print("\n" + "=" * 80)
    print("✅ TESTE PROMPT V2 CONCLUÍDO")
    print("=" * 80)

if __name__ == "__main__":
    main()
