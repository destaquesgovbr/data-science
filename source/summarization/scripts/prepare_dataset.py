#!/usr/bin/env python3
"""
Script para preparar dataset de 50 notícias para sumarização (Issue #4)

Estratégia de seleção:
- Amostra estratificada por categoria L1 (proporcional)
- Diversidade de tamanhos (pequeno, médio, grande)
- Apenas notícias reais (is_synthetic = False) para qualidade
- Remove notícias muito curtas (< 200 chars) ou muito longas (> 5000 chars)
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Configurações
INPUT_FILE = Path("../embeddings/data/classification/news_classification_test_annotated.csv")
OUTPUT_FILE = Path("data/news_sample.csv")
SAMPLE_SIZE = 200  # Usar todas as notícias disponíveis
MIN_LENGTH = 100   # Flexibilizar mínimo
MAX_LENGTH = 15000 # Flexibilizar máximo
RANDOM_SEED = 42

def main():
    print("=" * 80)
    print("PREPARAÇÃO DE DATASET PARA SUMARIZAÇÃO (ISSUE #4)")
    print("=" * 80)

    # Carregar dataset
    print(f"\n1. Carregando dataset: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE)
    print(f"   Total de notícias: {len(df)}")

    # Usar todas as notícias (reais + sintéticas)
    print("\n2. Análise de notícias...")
    df_real = df[df['is_synthetic'] == False]
    df_synthetic = df[df['is_synthetic'] == True]
    print(f"   Notícias reais: {len(df_real)}")
    print(f"   Notícias sintéticas: {len(df_synthetic)}")

    # Filtrar por tamanho
    print(f"\n3. Filtrando por tamanho ({MIN_LENGTH} - {MAX_LENGTH} caracteres)...")
    df_filtered = df[
        (df['length'] >= MIN_LENGTH) &
        (df['length'] <= MAX_LENGTH)
    ].copy()
    print(f"   Notícias após filtro: {len(df_filtered)}")

    # Distribuição de categorias
    print("\n4. Distribuição de categorias L1:")
    cat_counts = df_filtered['level_1_label'].value_counts()
    for cat, count in cat_counts.items():
        print(f"   - {cat}: {count}")

    # Usar todas as notícias disponíveis
    print(f"\n5. Usando todas as {len(df_filtered)} notícias disponíveis...")
    np.random.seed(RANDOM_SEED)

    # Embaralhar
    df_sample = df_filtered.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    print(f"\n6. Estatísticas da amostra final:")
    print(f"   Total: {len(df_sample)} notícias")
    print(f"   Tamanho médio: {df_sample['length'].mean():.0f} caracteres")
    print(f"   Tamanho mediano: {df_sample['length'].median():.0f} caracteres")
    print(f"   Min-Max: {df_sample['length'].min()} - {df_sample['length'].max()}")

    # Salvar
    print(f"\n7. Salvando em: {OUTPUT_FILE}")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df_sample.to_csv(OUTPUT_FILE, index=False)

    print("\n" + "=" * 80)
    print("✅ DATASET PREPARADO COM SUCESSO!")
    print("=" * 80)
    print(f"\nPróximo passo: Criar referências (ground truth) para as {len(df_sample)} notícias")
    print(f"Arquivo gerado: {OUTPUT_FILE.absolute()}")

    return df_sample

if __name__ == "__main__":
    df_sample = main()
