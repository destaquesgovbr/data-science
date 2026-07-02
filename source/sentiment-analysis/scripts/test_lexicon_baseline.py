#!/usr/bin/env python3
"""
Script para testar baseline léxico em notícias reais do corpus.

Carrega amostra de notícias do PostgreSQL, aplica análise de sentimento léxica
e gera relatório de distribuição e exemplos.

Uso:
    python scripts/test_lexicon_baseline.py --sample 50
"""

import sys
import argparse
from pathlib import Path
import psycopg2
import pandas as pd
from tabulate import tabulate

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lexicon_analyzer import LexiconSentimentAnalyzer


def get_news_sample(limit: int = 50, random: bool = True) -> pd.DataFrame:
    """
    Carrega amostra de notícias do PostgreSQL.

    Args:
        limit: número de notícias a carregar
        random: se True, amostra aleatória; se False, primeiras N

    Returns:
        DataFrame com colunas: id, title, content, category, published_at
    """
    print(f"Loading {limit} news from PostgreSQL...")

    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="news_db",
        user="rag_user",
        password=""  # Assuming no password for local dev
    )

    order_clause = "RANDOM()" if random else "id"

    query = f"""
        SELECT
            id,
            title,
            content,
            category,
            published_at,
            source_agency
        FROM news_documents
        ORDER BY {order_clause}
        LIMIT {limit}
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print(f"✓ Loaded {len(df)} news articles")
    return df


def analyze_corpus(df: pd.DataFrame, analyzer: LexiconSentimentAnalyzer) -> pd.DataFrame:
    """
    Aplica análise de sentimento ao corpus.

    Args:
        df: DataFrame com notícias
        analyzer: LexiconSentimentAnalyzer instance

    Returns:
        DataFrame com colunas adicionais de sentimento
    """
    print("\nAnalyzing sentiment...")

    results = []
    for idx, row in df.iterrows():
        text = f"{row['title']} {row['content']}"
        result = analyzer.analyze(text, return_details=False)

        results.append({
            'id': row['id'],
            'sentiment_score': result.score,
            'sentiment_label': result.label,
            'positive_count': result.positive_count,
            'negative_count': result.negative_count,
            'neutral_count': result.neutral_count,
            'total_sentiment_terms': result.total_sentiment_terms,
            'total_tokens': result.total_tokens
        })

    results_df = pd.DataFrame(results)
    df_with_sentiment = df.merge(results_df, on='id')

    print(f"✓ Analyzed {len(df_with_sentiment)} articles")
    return df_with_sentiment


def generate_report(df: pd.DataFrame):
    """
    Gera relatório de análise de sentimento.

    Args:
        df: DataFrame com resultados de análise
    """
    print("\n" + "=" * 80)
    print("SENTIMENT ANALYSIS BASELINE REPORT - OpLexicon v3.0")
    print("=" * 80)

    # 1. Distribuição de sentimentos
    print("\n=== Sentiment Distribution ===")
    dist = df['sentiment_label'].value_counts()
    dist_pct = (dist / len(df) * 100).round(1)

    dist_table = pd.DataFrame({
        'Sentiment': dist.index,
        'Count': dist.values,
        'Percentage': [f"{p}%" for p in dist_pct.values]
    })
    print(tabulate(dist_table, headers='keys', tablefmt='psql', showindex=False))

    # 2. Estatísticas de score
    print("\n=== Sentiment Score Statistics ===")
    stats = df['sentiment_score'].describe()
    print(f"Mean:   {stats['mean']:+.3f}")
    print(f"Std:    {stats['std']:.3f}")
    print(f"Min:    {stats['min']:+.3f}")
    print(f"25%:    {stats['25%']:+.3f}")
    print(f"Median: {stats['50%']:+.3f}")
    print(f"75%:    {stats['75%']:+.3f}")
    print(f"Max:    {stats['max']:+.3f}")

    # 3. Coverage (termos matched)
    print("\n=== Lexicon Coverage ===")
    avg_sentiment_terms = df['total_sentiment_terms'].mean()
    avg_total_tokens = df['total_tokens'].mean()
    coverage = (avg_sentiment_terms / avg_total_tokens * 100) if avg_total_tokens > 0 else 0

    print(f"Avg sentiment terms per article: {avg_sentiment_terms:.1f}")
    print(f"Avg total tokens per article:    {avg_total_tokens:.1f}")
    print(f"Average coverage:                {coverage:.1f}%")

    # 4. Exemplos por sentimento
    print("\n=== Examples by Sentiment ===")

    for sentiment in ['positive', 'neutral', 'negative']:
        subset = df[df['sentiment_label'] == sentiment]
        if len(subset) == 0:
            continue

        print(f"\n--- {sentiment.upper()} ({len(subset)} articles) ---")

        # Pegar 2 exemplos com maior magnitude de score
        if sentiment == 'neutral':
            examples = subset.nsmallest(2, 'sentiment_score', keep='first')
        else:
            examples = subset.nlargest(2, 'sentiment_score' if sentiment == 'positive' else 'sentiment_score', keep='first')

        for idx, row in examples.iterrows():
            print(f"\nTitle: {row['title'][:100]}...")
            print(f"Score: {row['sentiment_score']:+.3f}")
            print(f"Terms: {row['positive_count']} pos, {row['negative_count']} neg, {row['neutral_count']} neu")
            print(f"Category: {row['category']}")

    # 5. Distribuição por categoria (se disponível)
    if 'category' in df.columns and df['category'].notna().any():
        print("\n=== Sentiment by Category (Top 5) ===")

        cat_sentiment = df.groupby('category')['sentiment_label'].value_counts().unstack(fill_value=0)
        cat_sentiment = cat_sentiment.sort_values(by='neutral', ascending=False).head(5)

        print(tabulate(cat_sentiment, headers='keys', tablefmt='psql'))

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Test lexicon baseline on news corpus'
    )
    parser.add_argument(
        '--sample',
        type=int,
        default=50,
        help='Number of news articles to sample (default: 50)'
    )
    parser.add_argument(
        '--random',
        action='store_true',
        default=True,
        help='Random sampling (default: True)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV file for results (optional)'
    )

    args = parser.parse_args()

    # Inicializar analyzer
    analyzer = LexiconSentimentAnalyzer()

    # Carregar notícias
    df = get_news_sample(limit=args.sample, random=args.random)

    # Analisar sentimento
    df_results = analyze_corpus(df, analyzer)

    # Gerar relatório
    generate_report(df_results)

    # Salvar resultados se especificado
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_results.to_csv(output_path, index=False)
        print(f"\n✓ Results saved to {output_path}")


if __name__ == "__main__":
    main()
