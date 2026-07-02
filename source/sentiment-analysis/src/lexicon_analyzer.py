"""
Analisador de sentimento baseado em léxico (OpLexicon v3.0)

Implementa baseline léxico para análise de sentimento em notícias governamentais
brasileiras usando OpLexicon v3.0 (32.191 termos).

Autor: Luis Felipe de Moraes
Data: 2026-06-30
Issue: #6 - Análise de Sentimento em Notícias Governamentais
"""

import re
from pathlib import Path
from typing import Dict, Tuple, List
from dataclasses import dataclass
import pandas as pd


@dataclass
class SentimentResult:
    """Resultado da análise de sentimento."""
    score: float  # -1.0 a 1.0
    label: str  # "positive", "neutral", "negative"
    positive_count: int
    negative_count: int
    neutral_count: int
    total_sentiment_terms: int
    total_tokens: int
    matched_terms: List[Tuple[str, int]]  # [(term, polarity), ...]


class LexiconSentimentAnalyzer:
    """
    Analisador de sentimento baseado em léxico OpLexicon v3.0.

    Abordagem baseline:
    - Preprocessamento simples (lowercase, tokenização)
    - Contagem de termos positivos/negativos/neutros
    - Score normalizado: (pos - neg) / total_sentiment_terms
    - Classificação por threshold (0.1 / -0.1)

    Limitações conhecidas:
    - Não trata negação
    - Não trata intensificadores
    - Bag-of-words (ignora contexto)
    - Pode perder termos governamentais específicos
    """

    def __init__(self, lexicon_path: str = None, threshold: float = 0.1):
        """
        Inicializa analisador com OpLexicon.

        Args:
            lexicon_path: caminho para oplexicon_v3.txt (None = auto-detect)
            threshold: threshold para classificação pos/neg (default: 0.1)
        """
        self.threshold = threshold
        self.lexicon = self._load_lexicon(lexicon_path)

    def _load_lexicon(self, lexicon_path: str = None) -> Dict[str, int]:
        """
        Carrega OpLexicon v3.0 em dicionário {term: polarity}.

        Args:
            lexicon_path: caminho custom ou None para auto-detect

        Returns:
            dict {term: polarity} onde polarity in {-1, 0, 1}
        """
        if lexicon_path is None:
            # Auto-detect: procura em data/lexicons/
            base_path = Path(__file__).parent.parent / "data" / "lexicons"
            lexicon_path = base_path / "oplexicon_v3.txt"

        if not Path(lexicon_path).exists():
            raise FileNotFoundError(
                f"OpLexicon not found at {lexicon_path}. "
                "Run scripts/download_oplexicon.py first."
            )

        # Carregar CSV
        df = pd.read_csv(
            lexicon_path,
            names=['term', 'type', 'polarity', 'source']
        )

        # Converter para dict {term: polarity}
        lexicon = dict(zip(df['term'], df['polarity']))

        print(f"✓ Loaded OpLexicon v3.0: {len(lexicon):,} terms")
        return lexicon

    def preprocess_text(self, text: str) -> List[str]:
        """
        Preprocessa texto para análise léxica.

        Args:
            text: texto bruto

        Returns:
            lista de tokens preprocessados
        """
        # Lowercase
        text = text.lower()

        # Remove pontuação mas mantém palavras
        # Regex: split em não-letras, não-hífens
        tokens = re.findall(r'[\w-]+', text)

        # Remove tokens muito curtos (< 2 chars)
        tokens = [t for t in tokens if len(t) >= 2]

        return tokens

    def analyze(self, text: str, return_details: bool = True) -> SentimentResult:
        """
        Analisa sentimento de um texto.

        Args:
            text: texto para análise
            return_details: se True, retorna termos matched

        Returns:
            SentimentResult com score, label e detalhes
        """
        # Preprocessamento
        tokens = self.preprocess_text(text)

        # Contadores
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        matched_terms = []

        # Busca no léxico
        for token in tokens:
            if token in self.lexicon:
                polarity = self.lexicon[token]

                if polarity == 1:
                    positive_count += 1
                elif polarity == -1:
                    negative_count += 1
                else:  # polarity == 0
                    neutral_count += 1

                if return_details:
                    matched_terms.append((token, polarity))

        # Cálculo de score
        total_sentiment_terms = positive_count + negative_count

        if total_sentiment_terms == 0:
            # Nenhum termo de sentimento encontrado
            score = 0.0
            label = "neutral"
        else:
            # Score normalizado: (pos - neg) / total
            score = (positive_count - negative_count) / total_sentiment_terms

            # Classificação por threshold
            if score > self.threshold:
                label = "positive"
            elif score < -self.threshold:
                label = "negative"
            else:
                label = "neutral"

        return SentimentResult(
            score=score,
            label=label,
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            total_sentiment_terms=total_sentiment_terms,
            total_tokens=len(tokens),
            matched_terms=matched_terms if return_details else []
        )

    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """
        Analisa batch de textos.

        Args:
            texts: lista de textos

        Returns:
            lista de SentimentResult
        """
        return [self.analyze(text, return_details=False) for text in texts]

    def get_lexicon_stats(self) -> Dict:
        """
        Retorna estatísticas do léxico carregado.

        Returns:
            dict com contagens por polaridade
        """
        polarities = list(self.lexicon.values())
        return {
            "total_terms": len(self.lexicon),
            "positive_terms": polarities.count(1),
            "negative_terms": polarities.count(-1),
            "neutral_terms": polarities.count(0)
        }


def main():
    """Exemplo de uso do analisador léxico."""

    # Inicializar analyzer
    analyzer = LexiconSentimentAnalyzer()

    # Stats do léxico
    stats = analyzer.get_lexicon_stats()
    print("\n=== Lexicon Statistics ===")
    for key, value in stats.items():
        print(f"{key}: {value:,}")

    # Exemplos de análise
    print("\n=== Example Analyses ===\n")

    examples = [
        # Positivo
        "O governo anuncia novo investimento em educação com resultados excelentes e promissores para o futuro.",

        # Negativo
        "Escândalo de corrupção prejudica imagem do governo e gera crise institucional grave.",

        # Neutro (factual)
        "O Ministério da Saúde divulga nota técnica sobre vacinação contra gripe.",

        # Misto
        "Apesar dos avanços na economia, críticos apontam problemas persistentes na área social."
    ]

    for i, text in enumerate(examples, 1):
        print(f"Example {i}:")
        print(f"Text: {text[:80]}...")

        result = analyzer.analyze(text)

        print(f"  Score: {result.score:+.3f}")
        print(f"  Label: {result.label.upper()}")
        print(f"  Sentiment terms: {result.positive_count} pos, {result.negative_count} neg, {result.neutral_count} neu")
        print(f"  Total tokens: {result.total_tokens}")

        if result.matched_terms:
            print(f"  Matched terms ({len(result.matched_terms)}): ", end="")
            preview = result.matched_terms[:5]
            print(", ".join([f"{t}({p:+d})" for t, p in preview]))
            if len(result.matched_terms) > 5:
                print(f"    ... and {len(result.matched_terms) - 5} more")

        print()


if __name__ == "__main__":
    main()
