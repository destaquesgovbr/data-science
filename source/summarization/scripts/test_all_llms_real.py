#!/usr/bin/env python3
"""
VALIDAÇÃO COMPLETA: Testa TODOS os 9 LLMs V2 em notícias REAIS
Objetivo: Encontrar o melhor modelo para atingir ROUGE-L > 0.55
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_abstractive_v2 import (
    Nova2LiteSummarizerV2,
    ClaudeHaiku4SummarizerV2,
    Llama33SummarizerV2,
    ClaudeSonnet46SummarizerV2,
    ClaudeOpus47SummarizerV2,
    NovaProSummarizerV2,
    Llama4MaverickSummarizerV2,
    DeepSeekR1SummarizerV2,
    MistralLarge3SummarizerV2
)
from tqdm import tqdm
import time

def main():
    print("=" * 80)
    print("VALIDAÇÃO COMPLETA - 9 LLMs V2 em NOTÍCIAS REAIS")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_real_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries_real.csv"

    if not news_file.exists() or not ref_file.exists():
        print(f"\n❌ ERRO: Arquivos necessários não encontrados!")
        print(f"   Execute: python scripts/prepare_real_news.py")
        print(f"   Execute: python scripts/generate_references_real.py")
        return

    print(f"\n1. Carregando 300 notícias reais do gov.br...")
    df_news = pd.read_csv(news_file)
    df_ref = pd.read_csv(ref_file)

    df = pd.merge(
        df_news[['id', 'title', 'content', 'category', 'subcategory', 'length', 'agency']],
        df_ref[['id', 'reference_summary']],
        on='id'
    )

    # Filtrar válidas
    df = df[
        (df['reference_summary'].notna()) &
        (df['reference_summary'] != '')
    ].copy()

    print(f"   Total: {len(df)} notícias com referências")
    print(f"   Tamanho médio: {df['length'].mean():.0f} chars")
    print(f"   Categorias: {df['category'].nunique()}")

    # Modelos a testar (9 LLMs V2)
    print(f"\n2. Testando 9 LLMs com Prompt V2 (few-shot):")

    techniques = [
        # Já testados (top 3)
        ("Nova 2 Lite V2", Nova2LiteSummarizerV2(), {"target_sentences": 3}),
        ("Haiku 4.5 V2", ClaudeHaiku4SummarizerV2(), {"target_sentences": 3}),
        ("Llama 3.3 V2", Llama33SummarizerV2(), {"target_sentences": 3}),

        # Novos (6 restantes)
        ("Sonnet 4.6 V2", ClaudeSonnet46SummarizerV2(), {"target_sentences": 3}),
        ("Opus 4.7 V2", ClaudeOpus47SummarizerV2(), {"target_sentences": 3}),
        ("Nova Pro V2", NovaProSummarizerV2(), {"target_sentences": 3}),
        ("Llama 4 Maverick V2", Llama4MaverickSummarizerV2(), {"target_sentences": 3}),
        ("DeepSeek R1 V2", DeepSeekR1SummarizerV2(), {"target_sentences": 3}),
        ("Mistral Large 3 V2", MistralLarge3SummarizerV2(), {"target_sentences": 3}),
    ]

    for name, _, _ in techniques:
        print(f"   - {name}")

    print(f"\n   Estimativa: ~{len(techniques) * len(df) * 2 / 60:.0f} min (~{len(techniques) * 2:.0f} min por modelo)")
    print(f"   Custo estimado: ~${len(techniques) * len(df) * 0.0008:.2f}")

    all_results = []

    for tech_name, summarizer, params in techniques:
        print(f"\n{'=' * 80}")
        print(f"3. Avaliando {tech_name}...")
        print(f"{'=' * 80}")
        results = []

        # Rate limiting
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

                # Rate limiting
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
            print(f"   Tempo total: {successful['latency'].sum()/60:.1f} min")
        else:
            print(f"\n   ❌ FALHOU: Nenhum sucesso!")

        all_results.extend(results)

    # Salvar resultados
    print(f"\n{'=' * 80}")
    print(f"4. Salvando resultados...")
    print(f"{'=' * 80}")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "all_llms_real_evaluation.csv"
    output_file.parent.mkdir(exist_ok=True)
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Análise final
    print(f"\n{'=' * 80}")
    print(f"5. RANKING FINAL - 9 LLMs V2 em NOTÍCIAS REAIS")
    print(f"{'=' * 80}")

    ranking = all_results_df[all_results_df['success'] == True].groupby(
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

    print(f"\n{'Rank':<6} {'Modelo':<30} {'ROUGE-L':<10} {'ROUGE-1':<10} {'ROUGE-2':<10} {'Latência':<10} {'vs Target'}")
    print("-" * 95)

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

        print(f"  {indicator:<6} {tech:<30} {score:.3f}      {row['rouge1_f1_mean']:.3f}      {row['rouge2_f1_mean']:.3f}      {row['latency_mean']:.2f}s       {vs_target:+.3f}")

    # Identificar vencedor
    print(f"\n{'=' * 80}")
    print("6. ANÁLISE DO MELHOR MODELO:")
    print(f"{'=' * 80}")

    best_model = ranking.index[0]
    best_score = ranking.iloc[0]['rougeL_f1_mean']
    gap = target - best_score

    print(f"\n🏆 LÍDER: {best_model}")
    print(f"   ROUGE-L: {best_score:.3f}")
    print(f"   ROUGE-1: {ranking.iloc[0]['rouge1_f1_mean']:.3f}")
    print(f"   ROUGE-2: {ranking.iloc[0]['rouge2_f1_mean']:.3f}")
    print(f"   Latência: {ranking.iloc[0]['latency_mean']:.2f}s")

    if best_score >= target:
        print(f"\n   ✅ TARGET ATINGIDO! Superou {target:.3f} em {((best_score/target)-1)*100:.1f}%")
        print(f"\n   🎉 Sucesso! Modelo pronto para produção.")
    else:
        print(f"\n   Gap para target ({target:.3f}): {gap:.3f} ({abs(gap/target)*100:.1f}%)")
        print(f"\n   Próximos passos:")
        print(f"   - Prompt V3 (5-shot, chain-of-thought)")
        print(f"   - Abordagem híbrida (extractive + abstractive)")
        print(f"   - Fine-tuning do melhor modelo")

    # Estatísticas de custo
    print(f"\n{'=' * 80}")
    print("7. ESTATÍSTICAS DE PRODUÇÃO:")
    print(f"{'=' * 80}")

    best_results = all_results_df[
        (all_results_df['technique'] == best_model) &
        (all_results_df['success'] == True)
    ]

    if len(best_results) > 0:
        total_time = best_results['latency'].sum()
        avg_latency = best_results['latency'].mean()

        # Custo por modelo
        cost_map = {
            'Haiku': 0.0008,
            'Sonnet': 0.003,
            'Opus': 0.015,
            'Nova 2 Lite': 0.0006,
            'Nova Premierer': 0.008,
            'Llama': 0.001,
            'DeepSeek': 0.0014,
            'Mistral': 0.002
        }

        cost_per_call = 0.001  # default
        for key, cost in cost_map.items():
            if key in best_model:
                cost_per_call = cost
                break

        total_cost = len(best_results) * cost_per_call

        print(f"\n   Modelo: {best_model}")
        print(f"   Resumos testados: {len(best_results)}")
        print(f"   Latência média: {avg_latency:.2f}s")
        print(f"   Tempo total: {total_time/60:.1f} min")
        print(f"   Custo total: ~${total_cost:.2f}")
        print(f"   Custo por resumo: ~${cost_per_call:.4f}")
        print(f"   Custo para 10k resumos/mês: ~${cost_per_call * 10000:.2f}")

    print("\n" + "=" * 80)
    print("✅ VALIDAÇÃO COMPLETA CONCLUÍDA")
    print("=" * 80)

if __name__ == "__main__":
    main()
