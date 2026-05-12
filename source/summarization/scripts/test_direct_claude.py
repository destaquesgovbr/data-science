#!/usr/bin/env python3
"""
Teste direto do summarizer
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from summarizers_abstractive import ClaudeSonnet4Summarizer

text = """O Ministério da Educação (MEC) está com inscrições abertas até o dia 13 de março para estados e municípios aderirem ao Compromisso Nacional Toda Matemática. O programa oferece apoio técnico e financeiro para fortalecer o ensino de matemática na educação básica. A adesão é voluntária e ocorre em duas etapas, sendo a primeira pela internet e a segunda presencialmente."""

print("Testando ClaudeSonnet4Summarizer...")
summarizer = ClaudeSonnet4Summarizer()

try:
    print("\nChamando summarize()...")
    summary = summarizer.summarize(text, target_sentences=3)
    print(f"\nSucesso!")
    print(f"Resumo: {summary}")
except Exception as e:
    print(f"\nErro: {str(e)}")
    import traceback
    traceback.print_exc()
