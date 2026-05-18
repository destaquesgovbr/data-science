#!/usr/bin/env python3
"""
VALIDAÇÃO FINAL: Teste com notícias REAIS do gov.br
Compara os 2 melhores modelos com baseline em dados reais
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_abstractive_v2 import (
    ClaudeHaiku4SummarizerV2,
    Nova2LiteSummarizerV2
)
from summarizers_enhanced import EnhancedTextRankSummarizer
from tqdm import tqdm
import time

def main():
    print("=" * 80)
    print("VALIDAÇÃO FINAL - NOTÍCIAS REAIS DO GOV.BR")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_real_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries_real.csv"

    if not news_file.exists():
        print(f"\n❌ ERRO: {news_file} não encontrado!")
        print(f"   Execute: python scripts/prepare_real_news.py")
        return

    if not ref_file.exists():
        print(f"\n❌ ERRO: {ref_file} não encontrado!")
        print(f"   Execute: python scripts/generate_references_real.py")
        return

    print(f"\n1. Carregando notícias reais do gov.br...")
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

    print(f"   Total de notícias com referências válidas: {len(df)}")

    # Estatísticas do dataset
    print(f"\n2. Estatísticas do dataset REAL:")
    print(f"   Fonte: gov.br (issue#1)")
    print(f"   Categorias: {df['category'].nunique()}")
    print(f"   Agências: {df['agency'].nunique()}")
    print(f"   Tamanho médio: {df['length'].mean():.0f} chars")
    print(f"   Tamanho min/max: {df['length'].min()}/{df['length'].max()}")

    print(f"\n   Top 5 categorias:")
    for cat, count in df['category'].value_counts().head(5).items():
        print(f"      {cat[:40]:<40} {count:>3}")

    # Modelos a testar
    print(f"\n3. Modelos selecionados:")
    print(f"   - Enhanced TextRank (baseline extractive)")
    print(f"   - Claude Haiku 4.5 V2 (líder: 0.515 em 50 sintéticas)")
    print(f"   - Amazon Nova 2 Lite V2 (segundo: 0.513 em 50 sintéticas)")

    techniques = [
        ("Enhanced TextRank", EnhancedTextRankSummarizer(), {"sentences_count": 4}, False),
        ("Haiku 4.5 V2", ClaudeHaiku4SummarizerV2(), {"target_sentences": 3}, True),
        ("Nova 2 Lite V2", Nova2LiteSummarizerV2(), {"target_sentences": 3}, True),
    ]

    all_results = []

    for tech_name, summarizer, params, is_api in techniques:
        print(f"\n{'=' * 80}")
        print(f"4. Avaliando {tech_name}...")
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
                    'category': row['category'],
                    'subcategory': row['subcategory'],
                    'agency': row['agency'],
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
            print(f"   ROUGE-1 F1: {successful['rouge1_f1'].mean():.3f} ± {successful['rouge1_f1'].std():.3f}")
            print(f"   ROUGE-2 F1: {successful['rouge2_f1'].mean():.3f} ± {successful['rouge2_f1'].std():.3f}")
            print(f"   ROUGE-L F1: {successful['rougeL_f1'].mean():.3f} ± {successful['rougeL_f1'].std():.3f}")
            print(f"   Latência média: {successful['latency'].mean():.2f}s")
            print(f"   Tempo total: {successful['latency'].sum()/60:.1f} min")
        else:
            print(f"\n   ❌ FALHOU: Nenhum sucesso!")

        all_results.extend(results)

    # Salvar resultados
    print(f"\n{'=' * 80}")
    print(f"5. Salvando resultados...")
    print(f"{'=' * 80}")
    all_results_df = pd.DataFrame(all_results)
    output_file = script_dir.parent / "results" / "real_dataset_evaluation.csv"
    output_file.parent.mkdir(exist_ok=True)
    all_results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Análise final
    print(f"\n{'=' * 80}")
    print(f"6. ANÁLISE FINAL - NOTÍCIAS REAIS ({len(df)} notícias)")
    print(f"{'=' * 80}")

    ranking = all_results_df[all_results_df['success'] == True].groupby(
        'technique'
    )['rougeL_f1'].mean().sort_values(ascending=False)

    baseline = ranking.get('Enhanced TextRank', 0)
    target = 0.55

    print(f"\n{'Rank':<6} {'Modelo':<30} {'ROUGE-L':<10} {'vs Baseline':<12} {'vs Target'}")
    print("-" * 80)

    for rank, (tech, score) in enumerate(ranking.items(), 1):
        improvement = ((score / baseline) - 1) * 100 if baseline > 0 and tech != 'Enhanced TextRank' else 0
        vs_target = score - target

        if score >= target:
            indicator = "🎯"
        elif rank == 1:
            indicator = "🏆"
        else:
            indicator = f"#{rank}"

        vs_baseline_str = f"{improvement:+.1f}%" if tech != 'Enhanced TextRank' else "baseline"

        print(f"  {indicator:<6} {tech:<30} {score:.3f}      {vs_baseline_str:<12} {vs_target:+.3f}")

    # Análise por categoria
    print(f"\n{'=' * 80}")
    print("7. ANÁLISE POR CATEGORIA:")
    print(f"{'=' * 80}")

    for tech in ranking.index:
        tech_results = all_results_df[
            (all_results_df['technique'] == tech) &
            (all_results_df['success'] == True)
        ]

        if len(tech_results) > 0:
            print(f"\n{tech}:")
            by_category = tech_results.groupby('category')['rougeL_f1'].agg(['mean', 'count'])
            by_category = by_category.sort_values('mean', descending=False)

            for cat, row in by_category.head(5).iterrows():
                print(f"   {cat[:40]:<40} {row['mean']:.3f} (n={int(row['count'])})")

    # Análise por tamanho
    print(f"\n{'=' * 80}")
    print("8. ANÁLISE POR TAMANHO DE NOTÍCIA:")
    print(f"{'=' * 80}")

    # Criar bins de tamanho
    all_results_df['size_bin'] = pd.cut(
        all_results_df['original_length'],
        bins=[0, 1000, 2000, 4000, 10000],
        labels=['Curta (<1k)', 'Média (1-2k)', 'Longa (2-4k)', 'Muito longa (4-10k)']
    )

    for tech in ranking.index:
        tech_results = all_results_df[
            (all_results_df['technique'] == tech) &
            (all_results_df['success'] == True)
        ]

        if len(tech_results) > 0:
            print(f"\n{tech}:")
            by_size = tech_results.groupby('size_bin')['rougeL_f1'].agg(['mean', 'count'])

            for size, row in by_size.iterrows():
                print(f"   {size:<25} {row['mean']:.3f} (n={int(row['count'])})")

    # Comparação: sintéticas vs reais
    print(f"\n{'=' * 80}")
    print("9. COMPARAÇÃO: SINTÉTICAS vs REAIS")
    print(f"{'=' * 80}")

    comparison = {
        'Haiku 4.5 V2': {'sintéticas_50': 0.515, 'reais': ranking.get('Haiku 4.5 V2', 0)},
        'Nova 2 Lite V2': {'sintéticas_50': 0.513, 'reais': ranking.get('Nova 2 Lite V2', 0)},
        'Enhanced TextRank': {'sintéticas_50': 0.421, 'reais': ranking.get('Enhanced TextRank', 0)}
    }

    print(f"\n{'Modelo':<30} {'50 sintéticas':<15} {'~300 reais':<15} {'Diferença'}")
    print("-" * 80)

    for model, scores in comparison.items():
        diff = scores['reais'] - scores['sintéticas_50']
        diff_pct = (diff / scores['sintéticas_50']) * 100 if scores['sintéticas_50'] > 0 else 0

        print(f"{model:<30} {scores['sintéticas_50']:.3f}          {scores['reais']:.3f}          {diff:+.3f} ({diff_pct:+.1f}%)")

    # Conclusão
    print(f"\n{'=' * 80}")
    print("10. CONCLUSÃO:")
    print(f"{'=' * 80}")

    best_model = ranking.index[0]
    best_score = ranking.iloc[0]
    gap = target - best_score

    print(f"\nMelhor modelo em notícias REAIS: {best_model}")
    print(f"ROUGE-L: {best_score:.3f}")

    if best_score >= target:
        print(f"✅ TARGET ATINGIDO! Superou {target:.3f} em {((best_score/target)-1)*100:.1f}%")
    else:
        print(f"Gap para target ({target:.3f}): {gap:.3f} ({(gap/target)*100:.1f}%)")

    # Estatísticas de custo/tempo
    if best_model != 'Enhanced TextRank':
        best_results = all_results_df[
            (all_results_df['technique'] == best_model) &
            (all_results_df['success'] == True)
        ]

        if len(best_results) > 0:
            total_time = best_results['latency'].sum()
            avg_latency = best_results['latency'].mean()

            # Estimativa de custo
            if 'Haiku' in best_model:
                cost_per_call = 0.0008
            elif 'Nova' in best_model:
                cost_per_call = 0.0006
            else:
                cost_per_call = 0.001

            total_cost = len(best_results) * cost_per_call

            print(f"\nEstatísticas de produção ({len(best_results)} resumos):")
            print(f"   Latência média: {avg_latency:.2f}s")
            print(f"   Tempo total: {total_time/60:.1f} min")
            print(f"   Custo total: ~${total_cost:.2f}")
            print(f"   Custo para 10k resumos/mês: ~${cost_per_call * 10000:.2f}")

    print("\n" + "=" * 80)
    print("✅ VALIDAÇÃO COM NOTÍCIAS REAIS CONCLUÍDA")
    print("=" * 80)

if __name__ == "__main__":
    main()
