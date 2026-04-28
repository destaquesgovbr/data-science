#!/usr/bin/env python3
"""
Prepara dataset de 1000 notícias anotadas para Issue #3 (LLM Classification).

A partir do corpus de 250 documentos com categorias, expande dataset via:
1. Uso de todas 250 notícias reais como base
2. Criação de variantes sintéticas (750) com data augmentation
3. Balanceamento estratificado por categoria

Output: news_classification_dataset.csv com 1000 linhas
Colunas: id, title, content, category, agency, date, is_synthetic
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import random

# Configuração
BASE_DIR = Path(__file__).parent.parent
CORPUS_DIR = BASE_DIR / "data" / "corpus"
OUTPUT_DIR = BASE_DIR / "data" / "classification"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

np.random.seed(42)
random.seed(42)


def load_corpus():
    """Carrega todos documentos do corpus."""
    print("📂 Carregando corpus...")

    docs = []
    for doc_file in CORPUS_DIR.glob("doc_*.json"):
        with open(doc_file, 'r', encoding='utf-8') as f:
            doc = json.load(f)
            docs.append(doc)

    print(f"  ✅ {len(docs)} documentos carregados")
    return docs


def analyze_categories(docs):
    """Analisa distribuição de categorias."""
    categories = [doc['category'] for doc in docs]
    counter = Counter(categories)

    print("\n📊 Distribuição de categorias:")
    for cat, count in counter.most_common():
        print(f"  {cat}: {count} ({count/len(docs)*100:.1f}%)")

    return counter


def normalize_categories(docs):
    """
    Normaliza categorias para conjunto padrão de Issue #3.

    As categorias originais já estão boas e balanceadas:
    - Educação, Meio Ambiente, Ciência e Tecnologia, Segurança Pública,
      Agricultura, Saúde, Infraestrutura, Cultura, Assistência Social, Economia

    Vamos manter as 10 categorias originais para ter diversidade.
    """

    print("\n✅ Mantendo categorias originais (já estão balanceadas)...")

    for doc in docs:
        # Manter categoria original
        doc['category_normalized'] = doc['category']

    # Análise
    categories = [doc['category_normalized'] for doc in docs]
    counter = Counter(categories)

    print(f"  ✅ {len(counter)} categorias mantidas")
    print("\n📊 Distribuição:")
    for cat, count in counter.most_common():
        print(f"  {cat}: {count} ({count/len(docs)*100:.1f}%)")

    return docs, counter


def create_synthetic_variant(doc, variant_type='paraphrase'):
    """
    Cria variante sintética de documento.

    Estratégias:
    1. Paraphrase title (trocar palavras por sinônimos)
    2. Extract: usar apenas primeiro parágrafo
    3. Summarize: versão condensada (primeiras N sentenças)
    """

    synthetic_doc = doc.copy()
    synthetic_doc['id'] = f"{doc['id']}_syn_{variant_type}_{random.randint(1000, 9999)}"
    synthetic_doc['is_synthetic'] = True
    synthetic_doc['synthetic_method'] = variant_type

    if variant_type == 'extract_first':
        # Pega só primeiro parágrafo (antes de \n\n)
        paragraphs = doc['content'].split('\n\n')
        synthetic_doc['content'] = paragraphs[0] if paragraphs else doc['content'][:500]
        synthetic_doc['title'] = doc['title']  # Mantém título

    elif variant_type == 'extract_middle':
        # Pega parágrafo do meio
        paragraphs = [p for p in doc['content'].split('\n\n') if len(p) > 100]
        if len(paragraphs) > 1:
            mid_idx = len(paragraphs) // 2
            synthetic_doc['content'] = paragraphs[mid_idx]
        else:
            synthetic_doc['content'] = doc['content'][:500]
        synthetic_doc['title'] = doc['title']

    elif variant_type == 'short':
        # Versão curta: primeiras 3 sentenças
        sentences = doc['content'].split('. ')
        synthetic_doc['content'] = '. '.join(sentences[:3]) + '.'
        synthetic_doc['title'] = doc['title']

    return synthetic_doc


def expand_dataset(docs, target_size=1000):
    """
    Expande dataset de 250 para 1000 documentos.

    Estratégia:
    1. Mantém todos 250 originais
    2. Cria 750 sintéticos via data augmentation
    3. Balanceia por categoria
    """

    print(f"\n🔧 Expandindo dataset de {len(docs)} para {target_size}...")

    # Todos originais
    expanded = docs.copy()
    for doc in expanded:
        doc['is_synthetic'] = False

    # Quantos sintéticos precisamos por categoria
    category_counts = Counter([d['category_normalized'] for d in docs])
    total_originals = len(docs)
    total_synthetic = target_size - total_originals

    print(f"  Original: {total_originals}")
    print(f"  Synthetic: {total_synthetic}")

    # Estratégia: criar 3 variantes por documento original
    # extract_first, extract_middle, short
    variants_per_doc = ['extract_first', 'extract_middle', 'short']

    for doc in docs:
        for variant_type in variants_per_doc:
            synthetic = create_synthetic_variant(doc, variant_type)
            expanded.append(synthetic)

    print(f"  ✅ Dataset expandido para {len(expanded)} documentos")

    # Se passou de 1000, amostra
    if len(expanded) > target_size:
        print(f"  ⚠️  Reduzindo de {len(expanded)} para {target_size} (sampling estratificado)")

        # Mantém todos originais
        originals = [d for d in expanded if not d['is_synthetic']]
        synthetics = [d for d in expanded if d['is_synthetic']]

        # Amostra sintéticos proporcionalmente
        n_synthetic_needed = target_size - len(originals)

        # Agrupa sintéticos por categoria
        synthetic_by_cat = {}
        for doc in synthetics:
            cat = doc['category_normalized']
            if cat not in synthetic_by_cat:
                synthetic_by_cat[cat] = []
            synthetic_by_cat[cat].append(doc)

        # Amostra proporcionalmente
        sampled_synthetics = []
        for cat, cat_docs in synthetic_by_cat.items():
            n_cat_originals = len([d for d in originals if d['category_normalized'] == cat])
            proportion = n_cat_originals / len(originals)
            n_sample = int(n_synthetic_needed * proportion)

            if n_sample > len(cat_docs):
                n_sample = len(cat_docs)

            sampled = random.sample(cat_docs, n_sample)
            sampled_synthetics.extend(sampled)

        expanded = originals + sampled_synthetics

        print(f"  ✅ Dataset final: {len(expanded)} documentos")

    return expanded


def prepare_dataframe(docs):
    """Prepara DataFrame final."""
    print("\n📋 Preparando DataFrame...")

    data = []
    for doc in docs:
        row = {
            'id': doc['id'],
            'title': doc['title'],
            'content': doc['content'],
            'category': doc['category_normalized'],
            'category_original': doc.get('category', ''),
            'agency': doc.get('metadata', {}).get('agency', ''),
            'date': doc.get('metadata', {}).get('published_date', ''),
            'is_synthetic': doc.get('is_synthetic', False),
            'synthetic_method': doc.get('synthetic_method', ''),
            'length': len(doc['content']),
        }
        data.append(row)

    df = pd.DataFrame(data)

    print(f"  ✅ DataFrame criado: {len(df)} linhas × {len(df.columns)} colunas")

    return df


def stratified_split(df, test_size=0.2, val_size=0.1):
    """
    Split estratificado por categoria.

    - Train: 70%
    - Val: 10%
    - Test: 20%
    """
    from sklearn.model_selection import train_test_split

    print("\n✂️  Criando splits estratificados...")

    # Train + temp (80/20)
    train_df, test_df = train_test_split(
        df,
        test_size=test_size,
        stratify=df['category'],
        random_state=42
    )

    # Train + val (70/10 do total)
    train_df, val_df = train_test_split(
        train_df,
        test_size=val_size / (1 - test_size),  # 0.1/0.8 = 0.125
        stratify=train_df['category'],
        random_state=42
    )

    print(f"  Train: {len(train_df)} ({len(train_df)/len(df)*100:.1f}%)")
    print(f"  Val: {len(val_df)} ({len(val_df)/len(df)*100:.1f}%)")
    print(f"  Test: {len(test_df)} ({len(test_df)/len(df)*100:.1f}%)")

    # Verificar distribuição
    print("\n📊 Distribuição por categoria (Test set):")
    test_dist = test_df['category'].value_counts()
    for cat, count in test_dist.items():
        print(f"  {cat}: {count} ({count/len(test_df)*100:.1f}%)")

    return train_df, val_df, test_df


def save_datasets(train_df, val_df, test_df, full_df):
    """Salva datasets."""
    print("\n💾 Salvando datasets...")

    # Full dataset
    full_path = OUTPUT_DIR / "news_classification_full.csv"
    full_df.to_csv(full_path, index=False, encoding='utf-8')
    print(f"  ✅ Full: {full_path}")

    # Train
    train_path = OUTPUT_DIR / "news_classification_train.csv"
    train_df.to_csv(train_path, index=False, encoding='utf-8')
    print(f"  ✅ Train: {train_path}")

    # Val
    val_path = OUTPUT_DIR / "news_classification_val.csv"
    val_df.to_csv(val_path, index=False, encoding='utf-8')
    print(f"  ✅ Val: {val_path}")

    # Test
    test_path = OUTPUT_DIR / "news_classification_test.csv"
    test_df.to_csv(test_path, index=False, encoding='utf-8')
    print(f"  ✅ Test: {test_path}")

    # Metadata
    metadata = {
        'total_docs': len(full_df),
        'train_size': len(train_df),
        'val_size': len(val_df),
        'test_size': len(test_df),
        'n_categories': full_df['category'].nunique(),
        'categories': sorted(full_df['category'].unique().tolist()),
        'n_synthetic': int(full_df['is_synthetic'].sum()),
        'n_original': int((~full_df['is_synthetic']).sum()),
    }

    metadata_path = OUTPUT_DIR / "dataset_metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  ✅ Metadata: {metadata_path}")


def generate_summary_report(df):
    """Gera relatório resumido."""
    print("\n" + "="*80)
    print("📊 RELATÓRIO FINAL - DATASET DE CLASSIFICAÇÃO")
    print("="*80)

    print(f"\n📦 Total de Documentos: {len(df)}")
    print(f"  Originais: {(~df['is_synthetic']).sum()} ({(~df['is_synthetic']).sum()/len(df)*100:.1f}%)")
    print(f"  Sintéticos: {df['is_synthetic'].sum()} ({df['is_synthetic'].sum()/len(df)*100:.1f}%)")

    print(f"\n🏷️  Categorias: {df['category'].nunique()}")
    for cat in sorted(df['category'].unique()):
        count = (df['category'] == cat).sum()
        print(f"  {cat}: {count} ({count/len(df)*100:.1f}%)")

    print(f"\n📏 Estatísticas de Tamanho (caracteres):")
    print(f"  Média: {df['length'].mean():.0f}")
    print(f"  Mediana: {df['length'].median():.0f}")
    print(f"  Min: {df['length'].min():.0f}")
    print(f"  Max: {df['length'].max():.0f}")

    print("\n" + "="*80)


def main():
    """Pipeline principal."""

    print("="*80)
    print("PREPARAÇÃO DE DATASET - ISSUE #3: LLM CLASSIFICATION")
    print("="*80)

    # 1. Carregar corpus
    docs = load_corpus()

    # 2. Analisar categorias originais
    analyze_categories(docs)

    # 3. Normalizar categorias
    docs, normalized_counts = normalize_categories(docs)

    # 4. Expandir dataset para 1000
    expanded_docs = expand_dataset(docs, target_size=1000)

    # 5. Preparar DataFrame
    df = prepare_dataframe(expanded_docs)

    # 6. Splits estratificados
    train_df, val_df, test_df = stratified_split(df, test_size=0.2, val_size=0.1)

    # 7. Salvar
    save_datasets(train_df, val_df, test_df, df)

    # 8. Relatório
    generate_summary_report(df)

    print("\n✅ Dataset preparado com sucesso!")
    print(f"\n📁 Arquivos gerados em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
