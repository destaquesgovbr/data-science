#!/usr/bin/env python3
"""
FASE 3: Sumarização Abstractive com LLMs via Bedrock
Testa múltiplos modelos e compara com baseline extractive
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_abstractive import (
    ClaudeSonnet4Summarizer,
    ClaudeOpus4Summarizer,
    NovaPremiererSummarizer
)
from summarizers_enhanced import EnhancedTextRankSummarizer
from tqdm import tqdm
import time

def main():
    print("=" * 80)
    print("FASE 3: SUMARIZAÇÃO ABSTRACTIVE (LLMs via Bedrock)")
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
    print(f"\n2. Modelos LLM a avaliar (Tier 1 - Top Performance):")
    print(f"   - Claude Sonnet 4.6 (melhor custo-benefício)")
    print(f"   - Claude Opus 4.7 (máxima qualidade)")
    print(f"   - Amazon Nova Premier (flagship AWS)")
    print(f"   - Enhanced TextRank (baseline extractive = 0.421)")

    techniques = [
        ("Enhanced TextRank", EnhancedTextRankSummarizer(), {"sentences_count": 4}),
        ("Claude Sonnet 4.6", ClaudeSonnet4Summarizer(), {"target_sentences": 3}),
        ("Claude Opus 4.7", ClaudeOpus4Summarizer(), {"target_sentences": 3}),
        ("Amazon Nova Premier", NovaPremiererSummarizer(), {"target_sentences": 3}),
    ]

    all_results = []

    for tech_name, summarizer, params in techniques:
        print(f"\n3. Avaliando {tech_name}...")
        results = []

        # Rate limiting para APIs
        is_api = "Claude" in tech_name or "Nova" in tech_name
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
                print(f"\n   ⚠️  Erro na notícia {row['id']}: {str(e)[:100]}")
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
            print(f"   Sucesso: {len(successful)}/{len(results_df)}")
            print(f"   ROUGE-1 F1: {successful['rouge1_f1'].mean():.3f} ± {successful['rouge1_f1'].std():.3f}")
            print(f"   ROUGE-2 F1: {successful['rouge2_f1'].mean():.3f} ± {successful['rouge2_f1'].std():.3f}")
            print(f"   ROUGE-L F1: {successful['rougeL_f1'].mean():.3f} ± {successful['rougeL_f1'].std():.3f}")
            print(f"   Latência: {successful['latency'].mean():.2f}s")
        else:
            print(f"   ⚠️  Nenhum sucesso!")

        all_results.extend(results)

    # Salvar resultados
    print(f"\n4. Salvando resultados...")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "abstractive_comparison.csv"
    output_file.parent.mkdir(exist_ok=True)
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Comparação final
    print(f"\n5. RANKING FINAL (ROUGE-L F1):")
    print("=" * 80)

    ranking = all_results_df[all_results_df['success'] == True].groupby(
        'technique'
    )['rougeL_f1'].mean().sort_values(ascending=False)

    baseline = ranking.get('Enhanced TextRank', 0.421)
    target = 0.55

    for tech, score in ranking.items():
        improvement = ((score / baseline) - 1) * 100 if baseline > 0 else 0
        vs_target = score - target

        # Indicadores
        if score >= target:
            indicator = "🎯"  # Atingiu target
        elif score == ranking.max():
            indicator = "🏆"  # Melhor score
        elif improvement > 10:
            indicator = "⭐"  # Melhoria significativa
        else:
            indicator = "  "

        # Tipo
        if "TextRank" in tech:
            label = f"{tech:35s} [EXTRACTIVE]"
        else:
            label = f"{tech:35s} [ABSTRACTIVE]"

        print(f"   {indicator} {label} {score:.3f}  ({improvement:+.1f}% vs baseline, {vs_target:+.3f} vs target)")

    # Análise
    print("\n" + "=" * 80)
    best_llm_score = max([ranking.get(k, 0) for k in ranking.index if k != 'Enhanced TextRank'])
    best_llm_name = [k for k in ranking.index if k != 'Enhanced TextRank' and ranking.get(k, 0) == best_llm_score][0] if best_llm_score > 0 else None

    if best_llm_score >= target:
        print(f"✅ TARGET ATINGIDO! {best_llm_name}: {best_llm_score:.3f}")
        print(f"   Abstractive superou target de {target:.3f}")
    elif best_llm_score > baseline:
        gain = ((best_llm_score / baseline) - 1) * 100
        remaining = target - best_llm_score
        print(f"✅ PROGRESSO! {best_llm_name}: {best_llm_score:.3f} (+{gain:.1f}%)")
        print(f"   Faltam {remaining:.3f} pontos para target de {target:.3f}")
    else:
        print(f"⚠️  LLMs não superaram baseline extractive ({baseline:.3f})")
        print(f"   Melhor LLM: {best_llm_name} = {best_llm_score:.3f}")

    # Custo estimado
    print("\n" + "=" * 80)
    print("ANÁLISE DE CUSTO (estimado para 50 notícias):")

    for tech in ['Claude Sonnet 4.6', 'Claude Opus 4.7', 'Amazon Nova Premier']:
        tech_results = all_results_df[
            (all_results_df['technique'] == tech) &
            (all_results_df['success'] == True)
        ]

        if len(tech_results) > 0:
            avg_latency = tech_results['latency'].mean()
            total_time = tech_results['latency'].sum()

            # Estimativa de custo (aproximado)
            if "Opus" in tech:
                cost_per_call = 0.015  # ~$15/1M tokens input, assume ~1k tokens
            elif "Sonnet" in tech:
                cost_per_call = 0.003  # ~$3/1M tokens input
            elif "Nova" in tech:
                cost_per_call = 0.001  # Menor custo AWS
            else:
                cost_per_call = 0

            total_cost = len(tech_results) * cost_per_call

            print(f"   {tech:30s} Latência: {avg_latency:.2f}s  Tempo total: {total_time:.1f}s  Custo: ~${total_cost:.3f}")

    print("=" * 80)
    print("✅ FASE 3 CONCLUÍDA")
    print("=" * 80)

if __name__ == "__main__":
    main()
