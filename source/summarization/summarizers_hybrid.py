"""
Sumarizadores Híbridos - Extractive + Abstractive
Combina Enhanced TextRank (seleção) com LLM V2 (refinamento)
"""

from summarizers_enhanced import EnhancedTextRankSummarizer
from summarizers_abstractive_v2 import (
    NovaProSummarizerV2,
    Nova2LiteSummarizerV2,
    ClaudeHaiku4SummarizerV2
)
from summarizers import BaseSummarizer
import time


class HybridSummarizer(BaseSummarizer):
    """
    Abordagem híbrida: Extractive seleciona sentenças → Abstractive refina
    """

    def __init__(self, abstractive_summarizer, name_suffix=""):
        """
        Args:
            abstractive_summarizer: Sumarizador abstractive (LLM) para refinamento
            name_suffix: Sufixo para identificação
        """
        name = f"Hybrid {abstractive_summarizer.name}{name_suffix}"
        super().__init__(name)
        self.extractive = EnhancedTextRankSummarizer()
        self.abstractive = abstractive_summarizer

    def summarize(
        self,
        text: str,
        extractive_sentences: int = 6,
        target_sentences: int = 3,
        **kwargs
    ) -> str:
        """
        Pipeline híbrido:
        1. Enhanced TextRank seleciona top-N sentenças mais relevantes
        2. LLM refina essas sentenças em resumo conciso

        Args:
            text: Texto completo original
            extractive_sentences: Quantas sentenças o extractive deve selecionar (default: 6)
            target_sentences: Quantas sentenças o abstractive deve gerar (default: 3)
        """
        # Fase 1: Extractive seleciona sentenças relevantes
        extractive_summary = self.extractive.summarize(
            text=text,
            sentences_count=extractive_sentences
        )

        # Fase 2: Abstractive refina o conteúdo pré-filtrado
        # Modificamos o prompt para indicar que já é conteúdo filtrado
        refined_summary = self.abstractive.summarize(
            text=extractive_summary,
            target_sentences=target_sentences
        )

        return refined_summary


# Versões híbridas dos 3 melhores modelos

class HybridNovaProV2(HybridSummarizer):
    """Híbrido: Enhanced TextRank + Nova Pro V2"""
    def __init__(self):
        super().__init__(
            abstractive_summarizer=NovaProSummarizerV2(),
            name_suffix=" V2"
        )


class HybridNova2LiteV2(HybridSummarizer):
    """Híbrido: Enhanced TextRank + Nova 2 Lite V2"""
    def __init__(self):
        super().__init__(
            abstractive_summarizer=Nova2LiteSummarizerV2(),
            name_suffix=" V2"
        )


class HybridClaudeHaiku4V2(HybridSummarizer):
    """Híbrido: Enhanced TextRank + Haiku 4.5 V2"""
    def __init__(self):
        super().__init__(
            abstractive_summarizer=ClaudeHaiku4SummarizerV2(),
            name_suffix=" V2"
        )
