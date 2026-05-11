"""
Implementações de técnicas de sumarização para Issue #4

Grupos de técnicas:
- Extractive: TextRank, LexRank, BERT
- Abstractive: mT5, BART, Claude
- Hybrid: Extract-then-Abstract
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import warnings
warnings.filterwarnings('ignore')

# Extractive
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer as SumyTextRank
from sumy.summarizers.lex_rank import LexRankSummarizer as SumyLexRank
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

# Métricas
from rouge_score import rouge_scorer
import time


class BaseSummarizer(ABC):
    """Classe base para todos os sumarizadores"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def summarize(self, text: str, **kwargs) -> str:
        """
        Gera resumo do texto

        Args:
            text: Texto completo a ser sumarizado
            **kwargs: Parâmetros específicos de cada técnica

        Returns:
            Resumo gerado
        """
        pass

    def evaluate(self, text: str, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Gera resumo e calcula métricas

        Args:
            text: Texto completo
            reference: Resumo de referência (ground truth)
            **kwargs: Parâmetros para summarize()

        Returns:
            Dict com resumo, métricas e metadados
        """
        start_time = time.time()

        # Gerar resumo
        try:
            summary = self.summarize(text, **kwargs)
            success = True
            error_msg = None
        except Exception as e:
            summary = ""
            success = False
            error_msg = str(e)

        latency = time.time() - start_time

        # Calcular ROUGE
        if success and summary and reference:
            scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
            scores = scorer.score(reference, summary)

            rouge_scores = {
                'rouge1_precision': scores['rouge1'].precision,
                'rouge1_recall': scores['rouge1'].recall,
                'rouge1_f1': scores['rouge1'].fmeasure,
                'rouge2_precision': scores['rouge2'].precision,
                'rouge2_recall': scores['rouge2'].recall,
                'rouge2_f1': scores['rouge2'].fmeasure,
                'rougeL_precision': scores['rougeL'].precision,
                'rougeL_recall': scores['rougeL'].recall,
                'rougeL_f1': scores['rougeL'].fmeasure,
            }
        else:
            rouge_scores = {k: 0.0 for k in [
                'rouge1_precision', 'rouge1_recall', 'rouge1_f1',
                'rouge2_precision', 'rouge2_recall', 'rouge2_f1',
                'rougeL_precision', 'rougeL_recall', 'rougeL_f1'
            ]}

        return {
            'technique': self.name,
            'summary': summary,
            'success': success,
            'error': error_msg,
            'latency': latency,
            'summary_length': len(summary) if summary else 0,
            **rouge_scores
        }


class TextRankSummarizer(BaseSummarizer):
    """
    TextRank: Graph-based extractive summarization
    Baseado no algoritmo PageRank aplicado a sentenças
    """

    def __init__(self, language: str = "portuguese"):
        super().__init__("TextRank")
        self.language = language
        self.stemmer = Stemmer(language)
        self.summarizer = SumyTextRank(self.stemmer)
        self.summarizer.stop_words = get_stop_words(language)

    def summarize(
        self,
        text: str,
        sentences_count: int = 3,
        **kwargs
    ) -> str:
        """
        Gera resumo extractive usando TextRank

        Args:
            text: Texto completo
            sentences_count: Número de sentenças no resumo

        Returns:
            Resumo (sentenças concatenadas)
        """
        parser = PlaintextParser.from_string(text, Tokenizer(self.language))
        sentences = self.summarizer(parser.document, sentences_count)

        summary = " ".join(str(sentence) for sentence in sentences)
        return summary


class LexRankSummarizer(BaseSummarizer):
    """
    LexRank: Similar ao TextRank mas usa TF-IDF para similaridade
    Mais robusto em alguns casos
    """

    def __init__(self, language: str = "portuguese"):
        super().__init__("LexRank")
        self.language = language
        self.stemmer = Stemmer(language)
        self.summarizer = SumyLexRank(self.stemmer)
        self.summarizer.stop_words = get_stop_words(language)

    def summarize(
        self,
        text: str,
        sentences_count: int = 3,
        **kwargs
    ) -> str:
        """
        Gera resumo extractive usando LexRank

        Args:
            text: Texto completo
            sentences_count: Número de sentenças no resumo

        Returns:
            Resumo (sentenças concatenadas)
        """
        parser = PlaintextParser.from_string(text, Tokenizer(self.language))
        sentences = self.summarizer(parser.document, sentences_count)

        summary = " ".join(str(sentence) for sentence in sentences)
        return summary


# Placeholder para técnicas futuras
class BERTExtractiveSummarizer(BaseSummarizer):
    """BERT Extractive - A implementar"""

    def __init__(self):
        super().__init__("BERT-Extractive")
        # TODO: Implementar

    def summarize(self, text: str, ratio: float = 0.3, **kwargs) -> str:
        raise NotImplementedError("BERT Extractive ainda não implementado")


class MT5Summarizer(BaseSummarizer):
    """mT5 Abstractive - A implementar"""

    def __init__(self):
        super().__init__("mT5")
        # TODO: Implementar

    def summarize(self, text: str, max_length: int = 150, **kwargs) -> str:
        raise NotImplementedError("mT5 ainda não implementado")


class ClaudeSummarizer(BaseSummarizer):
    """Claude Abstractive - A implementar"""

    def __init__(self):
        super().__init__("Claude-Haiku")
        # TODO: Implementar (reutilizar Issue #3)

    def summarize(self, text: str, max_sentences: int = 3, **kwargs) -> str:
        raise NotImplementedError("Claude ainda não implementado")


class HybridSummarizer(BaseSummarizer):
    """Hybrid Extract-then-Abstract - A implementar"""

    def __init__(self, extractive, abstractive):
        super().__init__("Hybrid")
        self.extractive = extractive
        self.abstractive = abstractive

    def summarize(self, text: str, extract_ratio: float = 0.5, **kwargs) -> str:
        raise NotImplementedError("Hybrid ainda não implementado")


# Factory function
def get_summarizer(name: str, **kwargs) -> BaseSummarizer:
    """
    Factory para criar sumarizadores

    Args:
        name: Nome da técnica ('textrank', 'lexrank', 'bert', 'mt5', 'claude', 'hybrid')
        **kwargs: Parâmetros de inicialização

    Returns:
        Instância do sumarizador
    """
    summarizers = {
        'textrank': TextRankSummarizer,
        'lexrank': LexRankSummarizer,
        'bert': BERTExtractiveSummarizer,
        'mt5': MT5Summarizer,
        'claude': ClaudeSummarizer,
        'hybrid': HybridSummarizer,
    }

    if name.lower() not in summarizers:
        raise ValueError(f"Técnica desconhecida: {name}. Opções: {list(summarizers.keys())}")

    return summarizers[name.lower()](**kwargs)
