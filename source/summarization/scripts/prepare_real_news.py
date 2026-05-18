#!/usr/bin/env python3
"""
Prepara amostra de notícias REAIS do gov.br para validação de sumarização
Usa a base da issue#1 (10k notícias reais)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import polars as pl

def main():
    print("=" * 80)
    print("PREPARAÇÃO DE NOTÍCIAS REAIS DO GOV.BR")
    print("=" * 80)

    # Carregar base da issue#1
    script_dir = Path(__file__).parent
    embeddings_data = script_dir.parent.parent / "embeddings" / "data" / "raw" / "govbrnews_recent_10000.parquet"

    print(f"\n1. Carregando base de notícias reais...")
    print(f"   Fonte: {embeddings_data}")

    # Usar polars para leitura eficiente
    df = pl.read_parquet(embeddings_data)

    print(f"   Total de notícias: {len(df):,}")
    print(f"   Tamanho médio: {df['content_length'].mean():.0f} chars")

    # Filtrar notícias válidas
    print(f"\n2. Filtrando notícias válidas...")

    df_filtered = df.filter(
        (pl.col('content').is_not_null()) &
        (pl.col('content').str.len_chars() >= 500) &  # Mínimo razoável
        (pl.col('content').str.len_chars() <= 10000) &  # Máximo razoável
        (pl.col('title').is_not_null()) &
        (pl.col('theme_1_level_1_label').is_not_null())
    )

    print(f"   Após filtros: {len(df_filtered):,} notícias")
    print(f"   Tamanho médio: {df_filtered['content_length'].mean():.0f} chars")
    print(f"   Min/Max: {df_filtered['content_length'].min()}/{df_filtered['content_length'].max()}")

    # Amostrar 300 notícias estratificadas por categoria
    print(f"\n3. Amostragem estratificada (300 notícias)...")

    # Contar por categoria (polars syntax)
    category_counts = df_filtered.group_by('theme_1_level_1_label').agg(
        pl.count().alias('count')
    ).sort('count', descending=True)

    print(f"   Categorias disponíveis: {len(category_counts)}")
    print(f"\n   Top 10 categorias:")
    for row in category_counts.head(10).iter_rows(named=True):
        print(f"      {row['theme_1_level_1_label'][:40]:<40} {row['count']:>5}")

    # Amostrar proporcionalmente
    sample_size = 300
    df_sample = df_filtered.sample(n=sample_size, seed=42, shuffle=True)

    # Converter para pandas para salvar
    df_pandas = df_sample.to_pandas()

    # Criar dataset simplificado
    df_output = df_pandas[[
        'unique_id',
        'title',
        'content',
        'theme_1_level_1_label',
        'theme_1_level_2_label',
        'content_length',
        'published_at',
        'agency'
    ]].copy()

    # Renomear colunas
    df_output = df_output.rename(columns={
        'unique_id': 'id',
        'theme_1_level_1_label': 'category',
        'theme_1_level_2_label': 'subcategory',
        'content_length': 'length'
    })

    # Estatísticas da amostra
    print(f"\n4. Estatísticas da amostra final:")
    print(f"   Total: {len(df_output)} notícias")
    print(f"   Categorias: {df_output['category'].nunique()}")
    print(f"   Agências: {df_output['agency'].nunique()}")
    print(f"   Tamanho médio: {df_output['length'].mean():.0f} chars")
    print(f"   Min/Max: {df_output['length'].min()}/{df_output['length'].max()}")

    print(f"\n   Distribuição por categoria:")
    cat_dist = df_output['category'].value_counts().head(10)
    for cat, count in cat_dist.items():
        print(f"      {cat[:40]:<40} {count:>3}")

    print(f"\n   Distribuição por tamanho:")
    size_bins = pd.cut(
        df_output['length'],
        bins=[0, 1000, 2000, 4000, 10000],
        labels=['Curta (<1k)', 'Média (1-2k)', 'Longa (2-4k)', 'Muito longa (4-10k)']
    )
    print(size_bins.value_counts().sort_index().to_string())

    # Salvar
    output_file = script_dir.parent / "data" / "news_real_sample.csv"
    output_file.parent.mkdir(exist_ok=True)
    df_output.to_csv(output_file, index=False)

    print(f"\n5. Arquivo salvo:")
    print(f"   {output_file}")
    print(f"   Tamanho: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

    print("\n" + "=" * 80)
    print("✅ PREPARAÇÃO CONCLUÍDA")
    print("=" * 80)
    print(f"\nPróximos passos:")
    print(f"   1. Gerar referências: python scripts/generate_references_real.py")
    print(f"   2. Testar modelos: python scripts/test_real_dataset.py")

if __name__ == "__main__":
    main()
