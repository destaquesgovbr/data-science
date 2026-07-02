#!/usr/bin/env python3
"""
Script para download do OpLexicon v3.0

OpLexicon é um léxico de sentimento para português brasileiro com 32.191 entradas.
Fonte: https://github.com/marlovss/OpLexicon

Uso:
    python scripts/download_oplexicon.py
"""

import requests
import pandas as pd
from pathlib import Path

# URLs
OPLEXICON_URL = "https://raw.githubusercontent.com/marlovss/OpLexicon/master/lexico_v3.0.txt"

# Paths
DATA_DIR = Path(__file__).parent.parent / "data" / "lexicons"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = DATA_DIR / "oplexicon_v3.txt"


def download_oplexicon():
    """
    Baixa OpLexicon v3.0 do GitHub e salva localmente.
    """
    print("Downloading OpLexicon v3.0...")
    print(f"URL: {OPLEXICON_URL}")

    response = requests.get(OPLEXICON_URL)
    response.raise_for_status()

    # Salvar arquivo raw
    OUTPUT_FILE.write_text(response.text, encoding='utf-8')
    print(f"✓ Saved to: {OUTPUT_FILE}")

    # Carregar e mostrar estatísticas
    df = pd.read_csv(OUTPUT_FILE, names=['term', 'type', 'polarity', 'source'])

    print("\n=== OpLexicon v3.0 Statistics ===")
    print(f"Total entries: {len(df):,}")
    print("\nBy type:")
    print(df['type'].value_counts())
    print("\nBy polarity:")
    print(df['polarity'].value_counts())
    print("\nBy source:")
    print(df['source'].value_counts())

    # Exemplos
    print("\n=== Sample Entries ===")
    print("\nPositive adjectives:")
    print(df[(df['type'] == 'adj') & (df['polarity'] == 1)].head(5))
    print("\nNegative adjectives:")
    print(df[(df['type'] == 'adj') & (df['polarity'] == -1)].head(5))

    print(f"\n✓ OpLexicon v3.0 downloaded successfully to {OUTPUT_FILE}")


if __name__ == "__main__":
    download_oplexicon()
