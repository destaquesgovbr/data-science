#!/usr/bin/env python3
"""
FASE 3: Teste completo de TODOS os modelos LLM disponíveis no Bedrock
Compara com baseline extractive
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_abstractive import (
    ClaudeSonnet4Summarizer,
    ClaudeHaiku4Summarizer,
    Nova2LiteSummarizer,
    Llama4MaverickSummarizer,
    Llama33Summarizer,
    DeepSeekR1Summarizer
)
from summarizers_enhanced import EnhancedTextRankSummarizer
from tqdm import tqdm
import time

def main():
    print("=" * 80)
    print("FASE 3: TESTE COMPLETO - TODOS OS MODELOS LLM DISPONÍVEIS")
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
    print(f"\n2. Modelos a avaliar:")
    print(f"   BASELINE:")
    print(f"   - Enhanced TextRank (extractive)")
    print(f"\n   TIER 1 - Performance:")
    print(f"   - Claude Sonnet 4.6")
    print(f"\n   TIER 2 - Speed & Efficiency:")
    print(f"   - Claude Haiku 4.5")
    print(f"   - Amazon Nova 2 Lite")
    print(f"   - Llama 4 Maverick 17B")
    print(f"\n   TIER 3 - Open-Source:")
    print(f"   - Llama 3.3 70B")
    print(f"   - DeepSeek-R1")

    techniques = [
        # Baseline
        ("Enhanced TextRank", EnhancedTextRankSummarizer(), {"sentences_count": 4}, False),

        # Tier 1
        ("Claude Sonnet 4.6", ClaudeSonnet4Summarizer(), {"target_sentences": 3}, True),

        # Tier 2
        ("Claude Haiku 4.5", ClaudeHaiku4Summarizer(), {"target_sentences": 3}, True),
        ("Amazon Nova 2 Lite", Nova2LiteSummarizer(), {"target_sentences": 3}, True),
        ("Llama 4 Maverick 17B", Llama4MaverickSummarizer(), {"target_sentences": 3}, True),

        # Tier 3
        ("Llama 3.3 70B", Llama33Summarizer(), {"target_sentences": 3}, True),
        ("DeepSeek-R1", DeepSeekR1Summarizer(), {"target_sentences": 3}, True),
    ]

    all_results = []
    successful_techniques = []

    for tech_name, summarizer, params, is_api in techniques:
        print(f"\n{'=' * 80}")
        print(f"3. Avaliando {tech_name}...")
        print(f"{'=' * 80}")
        results = []

        # Rate limiting para APIs
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
            successful_techniques.append(tech_name)
        else:
            print(f"\n   ❌ FALHOU: {tech_name} - Nenhum sucesso!")
            if len(results_df) > 0:
                first_error = results_df.iloc[0]['error']
                print(f"   Erro: {first_error[:200]}")

        all_results.extend(results)

    # Salvar resultados
    print(f"\n{'=' * 80}")
    print(f"4. Salvando resultados...")
    print(f"{'=' * 80}")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "all_llms_comparison.csv"
    output_file.parent.mkdir(exist_ok=True)
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Comparação final
    print(f"\n{'=' * 80}")
    print(f"5. RANKING FINAL (ROUGE-L F1):")
    print(f"{'=' * 80}")

    ranking = all_results_df[all_results_df['success'] == True].groupby(
        'technique'
    )['rougeL_f1'].mean().sort_values(ascending=False)

    baseline = ranking.get('Enhanced TextRank', 0.421)
    target = 0.55

    print(f"\n{'Rank':<6} {'Modelo':<35} {'Tipo':<15} {'ROUGE-L':<10} {'vs Baseline':<12} {'vs Target'}")
    print("-" * 90)

    for rank, (tech, score) in enumerate(ranking.items(), 1):
        improvement = ((score / baseline) - 1) * 100 if baseline > 0 else 0
        vs_target = score - target

        # Indicadores
        if score >= target:
            indicator = "🎯"  # Atingiu target
        elif rank == 1:
            indicator = "🏆"  # Melhor score
        elif improvement > 5:
            indicator = "⭐"  # Melhoria significativa
        else:
            indicator = "  "

        # Tipo
        if "TextRank" in tech:
            tipo = "EXTRACTIVE"
        else:
            tipo = "ABSTRACTIVE"

        print(f"{indicator} #{rank:<4} {tech:<35} {tipo:<15} {score:.3f}      {improvement:+6.1f}%       {vs_target:+.3f}")

    # Análise
    print("\n" + "=" * 80)
    print("6. ANÁLISE DE RESULTADOS:")
    print("=" * 80)

    # Melhor LLM
    llm_scores = {k: v for k, v in ranking.items() if k != 'Enhanced TextRank'}
    if llm_scores:
        best_llm_name = max(llm_scores, key=llm_scores.get)
        best_llm_score = llm_scores[best_llm_name]

        print(f"\n🏆 MELHOR MODELO LLM: {best_llm_name}")
        print(f"   ROUGE-L: {best_llm_score:.3f}")

        if best_llm_score >= target:
            print(f"   ✅ TARGET ATINGIDO! (+{((best_llm_score/target)-1)*100:.1f}%)")
        elif best_llm_score > baseline:
            gain = ((best_llm_score / baseline) - 1) * 100
            remaining = target - best_llm_score
            print(f"   ✅ Superou baseline em {gain:+.1f}%")
            print(f"   ⚠️  Faltam {remaining:.3f} pontos para target ({(remaining/target)*100:.1f}%)")
        else:
            print(f"   ❌ Não superou baseline extractive")

    # Estatísticas gerais
    print(f"\n📊 ESTATÍSTICAS:")
    print(f"   Total de modelos testados: {len(techniques)}")
    print(f"   Modelos com sucesso: {len(successful_techniques)}")
    print(f"   Baseline (Enhanced TextRank): {baseline:.3f}")
    print(f"   Target: {target:.3f}")
    print(f"   Melhor score: {ranking.max():.3f}")

    # Custo estimado
    print(f"\n{'=' * 80}")
    print("7. ANÁLISE DE CUSTO/LATÊNCIA (50 notícias):")
    print("=" * 80)
    print(f"\n{'Modelo':<35} {'Latência Média':<15} {'Tempo Total':<15} {'Custo Est.'}")
    print("-" * 90)

    cost_map = {
        'Claude Sonnet 4.6': 0.003,
        'Claude Haiku 4.5': 0.0008,
        'Amazon Nova 2 Lite': 0.0006,
        'Llama 4 Maverick 17B': 0.0003,
        'Llama 3.3 70B': 0.0005,
        'DeepSeek-R1': 0.0010,
    }

    for tech in successful_techniques:
        if tech == 'Enhanced TextRank':
            continue

        tech_results = all_results_df[
            (all_results_df['technique'] == tech) &
            (all_results_df['success'] == True)
        ]

        if len(tech_results) > 0:
            avg_latency = tech_results['latency'].mean()
            total_time = tech_results['latency'].sum()
            cost_per_call = cost_map.get(tech, 0.001)
            total_cost = len(tech_results) * cost_per_call

            print(f"{tech:<35} {avg_latency:>6.2f}s         {total_time:>6.1f}s         ~${total_cost:.3f}")

    print("\n" + "=" * 80)
    print("✅ TESTE COMPLETO CONCLUÍDO")
    print("=" * 80)

if __name__ == "__main__":
    main()
