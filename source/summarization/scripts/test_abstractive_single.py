#!/usr/bin/env python3
"""
Teste rápido com 1 notícia para validar integração Bedrock
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers_abstractive import ClaudeSonnet4Summarizer

def main():
    print("=" * 80)
    print("TESTE UNITÁRIO: Claude Sonnet 4.6 via Bedrock")
    print("=" * 80)

    # Carregar dados
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_sample.csv"
    ref_file = script_dir.parent / "data" / "reference_summaries_sample.csv"

    df_news = pd.read_csv(news_file)
    df_ref = pd.read_csv(ref_file)

    df = pd.merge(
        df_news[['id', 'title', 'content', 'level_1_label', 'length']],
        df_ref[['id', 'reference_summary']],
        on='id'
    )

    df = df[df['reference_summary'].notna()].iloc[:1]  # Apenas primeira

    row = df.iloc[0]

    print(f"\n1. Testando com notícia:")
    print(f"   ID: {row['id']}")
    print(f"   Título: {row['title'][:60]}...")
    print(f"   Tamanho: {row['length']} chars")

    print(f"\n2. Gerando resumo com Claude Sonnet 4.6...")
    summarizer = ClaudeSonnet4Summarizer()

    try:
        result = summarizer.evaluate(
            text=row['content'],
            reference=row['reference_summary'],
            target_sentences=3
        )

        print(f"\n3. Resultado:")
        print(f"   Sucesso: {result['success']}")
        print(f"   ROUGE-1 F1: {result['rouge1_f1']:.3f}")
        print(f"   ROUGE-2 F1: {result['rouge2_f1']:.3f}")
        print(f"   ROUGE-L F1: {result['rougeL_f1']:.3f}")
        print(f"   Latência: {result['latency']:.2f}s")

        print(f"\n4. Resumo gerado:")
        print(f"   {result['summary'][:300]}...")

        print(f"\n5. Referência:")
        print(f"   {row['reference_summary'][:300]}...")

        print("\n" + "=" * 80)
        print("✅ TESTE PASSOU - Integração OK!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
