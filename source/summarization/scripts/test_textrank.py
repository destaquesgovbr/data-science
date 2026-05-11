#!/usr/bin/env python3
"""
Script de teste piloto para TextRank
Valida o pipeline completo antes de escalar
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from summarizers import TextRankSummarizer

def main():
    print("=" * 80)
    print("TESTE PILOTO: TextRank Summarizer")
    print("=" * 80)

    # Carregar dataset
    script_dir = Path(__file__).parent
    data_file = script_dir.parent / "data" / "news_sample.csv"
    print(f"\n1. Carregando dataset: {data_file}")
    df = pd.read_csv(data_file)
    print(f"   Total: {len(df)} notícias")

    # Testar com 5 notícias de diferentes tamanhos
    print("\n2. Selecionando 5 notícias para teste...")

    # Pegar notícias de tamanhos variados
    df_sorted = df.sort_values('length')
    test_indices = [
        0,                          # Menor
        len(df) // 4,               # 25%
        len(df) // 2,               # Mediana
        3 * len(df) // 4,           # 75%
        len(df) - 1                 # Maior
    ]
    df_test = df_sorted.iloc[test_indices].reset_index(drop=True)

    for idx, row in df_test.iterrows():
        print(f"   [{idx+1}] {row['title'][:60]}... ({row['length']} chars)")

    # Inicializar TextRank
    print("\n3. Inicializando TextRank...")
    summarizer = TextRankSummarizer(language="portuguese")
    print(f"   Técnica: {summarizer.name}")

    # Testar com diferentes números de sentenças
    sentence_counts = [2, 3, 5]

    print("\n4. Gerando resumos...")
    print("-" * 80)

    results = []

    for idx, row in df_test.iterrows():
        print(f"\n📰 NOTÍCIA {idx+1}: {row['title']}")
        print(f"Categoria: {row['level_1_label']}")
        print(f"Tamanho original: {row['length']} caracteres")
        print()

        for n_sentences in sentence_counts:
            try:
                summary = summarizer.summarize(row['content'], sentences_count=n_sentences)

                print(f"Resumo ({n_sentences} sentenças):")
                print(f"  {summary[:200]}...")
                print(f"  Tamanho: {len(summary)} caracteres")
                print()

                results.append({
                    'news_id': row['id'],
                    'title': row['title'],
                    'category': row['level_1_label'],
                    'original_length': row['length'],
                    'sentences_count': n_sentences,
                    'summary': summary,
                    'summary_length': len(summary),
                    'compression_ratio': len(summary) / row['length']
                })

            except Exception as e:
                print(f"  ❌ ERRO: {str(e)}")
                print()

    # Salvar resultados
    print("-" * 80)
    print("\n5. Salvando resultados...")
    results_df = pd.DataFrame(results)
    output_file = script_dir.parent / "results" / "textrank_pilot_test.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Estatísticas
    print("\n6. Estatísticas:")
    print(f"   Total de resumos gerados: {len(results_df)}")
    print(f"   Taxa de compressão média: {results_df['compression_ratio'].mean():.2%}")
    print(f"   Tamanho médio de resumo: {results_df['summary_length'].mean():.0f} caracteres")

    print("\n" + "=" * 80)
    print("✅ TESTE PILOTO CONCLUÍDO")
    print("=" * 80)
    print("\nPróxima etapa: Avaliar com ROUGE usando referências humanas")

if __name__ == "__main__":
    main()
