#!/usr/bin/env python3
"""
Prepara dataset AMPLIADO para Issue #3 (LLM Classification) usando ~10k notícias reais.

Usa govbrnews_recent_10000_clean.parquet como base (9985 notícias reais).

Output: Dataset balanceado e estratificado pronto para avaliação de LLMs.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import random

# Configuração
BASE_DIR = Path(__file__).parent.parent
RAW_DATA = BASE_DIR / "data" / "raw" / "govbrnews_recent_10000_clean.parquet"
OUTPUT_DIR = BASE_DIR / "data" / "classification"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

np.random.seed(42)
random.seed(42)


def load_govbr_news():
    """Carrega dataset de ~10k notícias."""
    print("📂 Carregando dataset gov.br...")

    df = pd.read_parquet(RAW_DATA, engine='pyarrow', use_nullable_dtypes=False)

    print(f"  ✅ {len(df):,} notícias carregadas")
    print(f"  📋 Colunas: {len(df.columns)}")

    return df


def clean_and_normalize_categories(df):
    """
    Limpa e normaliza categorias para conjunto padrão.

    Estratégia:
    1. Remove categorias genéricas ('Notícias', '', 'No Category')
    2. Mapeia categorias similares
    3. Mantém top 10-15 categorias mais frequentes
    4. Resto vai para 'Outros'
    """

    print("\n🔄 Limpando e normalizando categorias...")

    # Limpar categorias vazias/genéricas
    df = df[~df['category'].isin(['Notícias', '', 'No Category', 'notícias'])]
    df = df[df['category'].notna()]

    print(f"  ✅ Após limpeza: {len(df):,} notícias")

    # Análise de distribuição
    cat_counts = df['category'].value_counts()
    print(f"\n  📊 Top 20 categorias originais:")
    for cat, count in cat_counts.head(20).items():
        print(f"    {cat}: {count} ({count/len(df)*100:.1f}%)")

    # Mapeamento para categorias padronizadas
    category_mapping = {
        # Ciência e Tecnologia
        'Ciência e Tecnologia': 'Ciência e Tecnologia',
        'Ciência, Tecnologia e Inovação': 'Ciência e Tecnologia',
        'Tecnologia': 'Ciência e Tecnologia',

        # Meio Ambiente
        'Meio Ambiente e Clima': 'Meio Ambiente',
        'Meio Ambiente': 'Meio Ambiente',
        'Mudanças Climáticas': 'Meio Ambiente',
        'Recursos Hídricos': 'Meio Ambiente',

        # Saúde
        'Saúde': 'Saúde',
        'Saúde Pública': 'Saúde',
        'Vigilância Sanitária': 'Saúde',

        # Educação
        'Educação': 'Educação',
        'Educação Superior': 'Educação',
        'Educação Básica': 'Educação',

        # Economia
        'Economia': 'Economia',
        'Finanças': 'Economia',
        'Fazenda': 'Economia',
        'Desenvolvimento Econômico': 'Economia',
        'Comércio Exterior': 'Economia',

        # Agricultura
        'Agricultura': 'Agricultura',
        'Agricultura e Pecuária': 'Agricultura',
        'Agropecuária': 'Agricultura',
        'Pesca': 'Agricultura',

        # Segurança
        'Segurança Pública': 'Segurança',
        'Segurança': 'Segurança',
        'Justiça e Segurança': 'Segurança',
        'Defesa': 'Segurança',

        # Infraestrutura
        'Infraestrutura': 'Infraestrutura',
        'Transportes': 'Infraestrutura',
        'Cidades': 'Infraestrutura',
        'Habitação': 'Infraestrutura',
        'Obras': 'Infraestrutura',

        # Assistência Social
        'Assistência Social': 'Assistência Social',
        'Desenvolvimento Social': 'Assistência Social',
        'Cidadania': 'Assistência Social',
        'Direitos Humanos': 'Assistência Social',

        # Cultura
        'Cultura': 'Cultura',
        'Patrimônio Cultural': 'Cultura',

        # Trabalho
        'Trabalho': 'Trabalho',
        'Trabalho e Emprego': 'Trabalho',
        'Emprego': 'Trabalho',

        # Previdência
        'Previdência': 'Previdência',
        'Previdência Social': 'Previdência',

        # Energia
        'Energia': 'Energia',
        'Minas e Energia': 'Energia',

        # Turismo
        'Turismo': 'Turismo',

        # Esporte
        'Esporte': 'Esporte',
        'Esportes': 'Esporte',
    }

    # Aplicar mapeamento
    df['category_normalized'] = df['category'].map(category_mapping)

    # Categorias não mapeadas vão para 'Outros'
    df.loc[df['category_normalized'].isna(), 'category_normalized'] = 'Outros'

    # Análise pós-normalização
    normalized_counts = df['category_normalized'].value_counts()
    print(f"\n  ✅ Categorias após normalização: {len(normalized_counts)}")
    print(f"\n  📊 Distribuição normalizada:")
    for cat, count in normalized_counts.items():
        print(f"    {cat}: {count} ({count/len(df)*100:.1f}%)")

    return df, normalized_counts


def balance_categories(df, target_samples_per_category=200, min_samples=100):
    """
    Balanceia categorias para ter amostras suficientes.

    Estratégia:
    1. Remove categorias com <min_samples
    2. Para categorias com >target_samples, amostra aleatoriamente
    3. Para categorias com <target_samples, mantém todas
    """

    print(f"\n⚖️  Balanceando categorias (target: {target_samples_per_category} por categoria)...")

    category_counts = df['category_normalized'].value_counts()

    # Remover categorias pequenas
    valid_categories = category_counts[category_counts >= min_samples].index
    df_filtered = df[df['category_normalized'].isin(valid_categories)]

    print(f"  ✅ Categorias mantidas: {len(valid_categories)} (com ≥{min_samples} samples)")
    print(f"  📉 Removidas: {len(category_counts) - len(valid_categories)} categorias pequenas")

    # Balancear
    balanced_dfs = []

    for category in valid_categories:
        cat_df = df_filtered[df_filtered['category_normalized'] == category]

        if len(cat_df) > target_samples_per_category:
            # Amostra
            sampled = cat_df.sample(n=target_samples_per_category, random_state=42)
        else:
            # Mantém todas
            sampled = cat_df

        balanced_dfs.append(sampled)
        print(f"    {category}: {len(cat_df)} → {len(sampled)}")

    df_balanced = pd.concat(balanced_dfs, ignore_index=True)

    print(f"\n  ✅ Dataset balanceado: {len(df_balanced):,} notícias")
    print(f"  📊 {df_balanced['category_normalized'].nunique()} categorias finais")

    return df_balanced


def prepare_final_dataset(df):
    """Prepara DataFrame final com colunas necessárias."""

    print("\n📋 Preparando dataset final...")

    # Selecionar e renomear colunas
    df_final = df[['unique_id', 'title', 'content', 'category_normalized',
                    'agency', 'published_at']].copy()

    df_final.columns = ['id', 'title', 'content', 'category', 'agency', 'date']

    # Adicionar metadados
    df_final['is_synthetic'] = False
    df_final['length'] = df_final['content'].str.len()

    # Limpar NaNs em content
    df_final = df_final[df_final['content'].notna()]
    df_final = df_final[df_final['content'].str.len() > 50]  # Mínimo 50 chars

    print(f"  ✅ Dataset final: {len(df_final):,} notícias")
    print(f"  📏 Tamanho médio: {df_final['length'].mean():.0f} caracteres")

    return df_final


def stratified_split(df, test_size=0.15, val_size=0.10):
    """Split estratificado por categoria."""
    from sklearn.model_selection import train_test_split

    print(f"\n✂️  Criando splits estratificados...")

    # Train + temp
    train_df, test_df = train_test_split(
        df,
        test_size=test_size,
        stratify=df['category'],
        random_state=42
    )

    # Train + val
    train_df, val_df = train_test_split(
        train_df,
        test_size=val_size / (1 - test_size),
        stratify=train_df['category'],
        random_state=42
    )

    print(f"  Train: {len(train_df):,} ({len(train_df)/len(df)*100:.1f}%)")
    print(f"  Val: {len(val_df):,} ({len(val_df)/len(df)*100:.1f}%)")
    print(f"  Test: {len(test_df):,} ({len(test_df)/len(df)*100:.1f}%)")

    # Verificar distribuição no test
    print(f"\n  📊 Distribuição Test set:")
    test_dist = test_df['category'].value_counts()
    for cat, count in test_dist.items():
        print(f"    {cat}: {count} ({count/len(test_df)*100:.1f}%)")

    return train_df, val_df, test_df


def save_datasets(train_df, val_df, test_df, full_df):
    """Salva datasets."""

    print("\n💾 Salvando datasets...")

    # Full
    full_path = OUTPUT_DIR / "news_classification_full_v2.csv"
    full_df.to_csv(full_path, index=False, encoding='utf-8')
    print(f"  ✅ Full: {full_path} ({len(full_df):,} linhas)")

    # Train
    train_path = OUTPUT_DIR / "news_classification_train_v2.csv"
    train_df.to_csv(train_path, index=False, encoding='utf-8')
    print(f"  ✅ Train: {train_path} ({len(train_df):,} linhas)")

    # Val
    val_path = OUTPUT_DIR / "news_classification_val_v2.csv"
    val_df.to_csv(val_path, index=False, encoding='utf-8')
    print(f"  ✅ Val: {val_path} ({len(val_df):,} linhas)")

    # Test
    test_path = OUTPUT_DIR / "news_classification_test_v2.csv"
    test_df.to_csv(test_path, index=False, encoding='utf-8')
    print(f"  ✅ Test: {test_path} ({len(test_df):,} linhas)")

    # Metadata
    import json
    metadata = {
        'source': 'govbrnews_recent_10000_clean.parquet',
        'total_docs': len(full_df),
        'train_size': len(train_df),
        'val_size': len(val_df),
        'test_size': len(test_df),
        'n_categories': full_df['category'].nunique(),
        'categories': sorted(full_df['category'].unique().tolist()),
        'category_distribution': full_df['category'].value_counts().to_dict(),
    }

    metadata_path = OUTPUT_DIR / "dataset_metadata_v2.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  ✅ Metadata: {metadata_path}")


def generate_summary_report(df):
    """Gera relatório final."""

    print("\n" + "="*80)
    print("📊 RELATÓRIO FINAL - DATASET AMPLIADO v2")
    print("="*80)

    print(f"\n📦 Total: {len(df):,} notícias REAIS (100% originais)")

    print(f"\n🏷️  Categorias: {df['category'].nunique()}")
    for cat in sorted(df['category'].unique()):
        count = (df['category'] == cat).sum()
        print(f"  {cat}: {count} ({count/len(df)*100:.1f}%)")

    print(f"\n📏 Estatísticas de Tamanho:")
    print(f"  Média: {df['length'].mean():.0f} caracteres")
    print(f"  Mediana: {df['length'].median():.0f} caracteres")
    print(f"  Min: {df['length'].min():.0f} caracteres")
    print(f"  Max: {df['length'].max():.0f} caracteres")

    print(f"\n📰 Agências:")
    top_agencies = df['agency'].value_counts().head(10)
    for agency, count in top_agencies.items():
        print(f"  {agency}: {count} ({count/len(df)*100:.1f}%)")

    print("\n" + "="*80)


def main():
    """Pipeline principal."""

    print("="*80)
    print("PREPARAÇÃO DE DATASET AMPLIADO v2 - ISSUE #3")
    print("="*80)

    # 1. Carregar dados brutos
    df = load_govbr_news()

    # 2. Limpar e normalizar categorias
    df, normalized_counts = clean_and_normalize_categories(df)

    # 3. Balancear categorias
    df_balanced = balance_categories(df, target_samples_per_category=200, min_samples=100)

    # 4. Preparar dataset final
    df_final = prepare_final_dataset(df_balanced)

    # 5. Splits estratificados
    train_df, val_df, test_df = stratified_split(df_final, test_size=0.15, val_size=0.10)

    # 6. Salvar
    save_datasets(train_df, val_df, test_df, df_final)

    # 7. Relatório
    generate_summary_report(df_final)

    print("\n✅ Dataset ampliado v2 criado com sucesso!")
    print(f"\n📁 Arquivos em: {OUTPUT_DIR}")
    print("\n💡 Use os arquivos *_v2.csv para avaliação de LLMs")


if __name__ == "__main__":
    main()
