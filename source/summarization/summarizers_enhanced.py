"""
Versões melhoradas das técnicas extractive com quick wins
Inclui BERT Extractive com embeddings semânticos
"""

from summarizers import BaseSummarizer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import warnings
warnings.filterwarnings('ignore')
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer as SumyTextRank
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
import re


class EnhancedTextRankSummarizer(BaseSummarizer):
    """
    TextRank melhorado com quick wins:
    1. Position bias (boost para início/fim)
    2. Filtro de sentenças muito curtas
    3. Penalização de redundância
    4. Normalização melhorada
    """

    def __init__(self, language: str = "portuguese"):
        super().__init__("EnhancedTextRank")
        self.language = language
        self.stemmer = Stemmer(language)
        self.summarizer = SumyTextRank(self.stemmer)
        self.summarizer.stop_words = get_stop_words(language)

    def _clean_sentence(self, sentence: str) -> str:
        """Limpa e normaliza sentença"""
        text = str(sentence)

        # Remove múltiplos espaços
        text = re.sub(r'\s+', ' ', text)

        # Remove quebras de linha
        text = text.replace('\n', ' ').replace('\r', ' ')

        # Remove markdown/HTML básico
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # Imagens markdown
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # Links markdown (extrair texto)
        text = re.sub(r'<.*?>', '', text)  # Tags HTML

        return text.strip()

    def _is_valid_sentence(self, sentence: str, min_length: int = 50) -> bool:
        """Verifica se sentença é válida para inclusão"""
        text = self._clean_sentence(sentence)

        # Filtros
        if len(text) < min_length:
            return False

        # Sentença deve ter pelo menos 3 palavras
        words = text.split()
        if len(words) < 3:
            return False

        # Não pode ser só números/pontuação
        alpha_chars = sum(c.isalpha() for c in text)
        if alpha_chars < len(text) * 0.3:
            return False

        return True

    def _apply_position_bias(self, sentences, scores):
        """
        Aplica bias de posição:
        - Primeiras sentenças (lead) geralmente mais importantes
        - Última sentença pode conter conclusão
        """
        n = len(sentences)
        boosted_scores = []

        for i, score in enumerate(scores):
            # Position weight: decai suavemente do início
            position_weight = 1.0 + (1.0 / (i + 1)) * 0.5

            # Boost extra para primeira e última
            if i == 0:
                position_weight *= 1.2
            elif i == n - 1 and n > 3:
                position_weight *= 1.1

            boosted_scores.append(score * position_weight)

        return boosted_scores

    def _remove_redundancy(self, selected_sentences):
        """
        Remove sentenças muito similares (redundância)
        Mantém a primeira ocorrência
        """
        unique_sentences = []
        seen_words = set()

        for sentence in selected_sentences:
            words = set(self._clean_sentence(sentence).lower().split())

            # Calcula overlap com sentenças já selecionadas
            if not seen_words:
                overlap = 0
            else:
                overlap = len(words & seen_words) / len(words) if words else 0

            # Se overlap < 70%, adiciona
            if overlap < 0.7:
                unique_sentences.append(sentence)
                seen_words.update(words)

        return unique_sentences

    def summarize(
        self,
        text: str,
        sentences_count: int = 3,
        min_sentence_length: int = 50,
        apply_position_bias: bool = True,
        remove_redundancy: bool = True,
        **kwargs
    ) -> str:
        """
        Gera resumo com melhorias

        Args:
            text: Texto completo
            sentences_count: Número de sentenças desejadas
            min_sentence_length: Tamanho mínimo de sentença
            apply_position_bias: Aplicar bias de posição
            remove_redundancy: Remover sentenças redundantes

        Returns:
            Resumo melhorado
        """
        # Parse do texto
        parser = PlaintextParser.from_string(text, Tokenizer(self.language))

        # Obter sentenças originais e scores
        document = parser.document
        sentences = [sent for sent in document.sentences]

        # Filtrar sentenças inválidas antes do ranking
        valid_indices = [
            i for i, sent in enumerate(sentences)
            if self._is_valid_sentence(str(sent), min_sentence_length)
        ]

        if not valid_indices:
            # Fallback: usar todas sentenças
            valid_indices = list(range(len(sentences)))

        # Recalcular com sentenças válidas
        valid_sentences = [sentences[i] for i in valid_indices]

        # Calcular scores base (TextRank)
        # Nota: sumy não expõe scores diretamente, então pegamos top N+extra
        extra = min(10, len(valid_sentences) // 2)
        ranked_sentences = list(self.summarizer(
            parser.document,
            min(sentences_count + extra, len(valid_sentences))
        ))

        # Se position bias ativado, re-ranquear
        if apply_position_bias and len(ranked_sentences) > sentences_count:
            # Criar scores fictícios baseados em ordem
            scores = [1.0 / (i + 1) for i in range(len(ranked_sentences))]

            # Aplicar position bias
            boosted_scores = self._apply_position_bias(ranked_sentences, scores)

            # Re-ordenar por score boosted
            ranked_with_scores = list(zip(ranked_sentences, boosted_scores))
            ranked_with_scores.sort(key=lambda x: x[1], reverse=True)
            ranked_sentences = [s for s, _ in ranked_with_scores[:sentences_count + 5]]

        # Pegar top N
        selected = ranked_sentences[:sentences_count * 2]  # Pegar extra para redundância

        # Remover redundância se ativado
        if remove_redundancy:
            selected = self._remove_redundancy(selected)

        # Garantir que temos pelo menos sentences_count
        selected = selected[:sentences_count]

        # Limpar e juntar
        cleaned = [self._clean_sentence(s) for s in selected]
        summary = " ".join(cleaned)

        return summary


class PositionBiasedTextRank(BaseSummarizer):
    """
    TextRank simples com apenas position bias
    (para comparação isolada do impacto)
    """

    def __init__(self, language: str = "portuguese"):
        super().__init__("PositionBiasedTextRank")
        self.language = language
        self.stemmer = Stemmer(language)
        self.summarizer = SumyTextRank(self.stemmer)
        self.summarizer.stop_words = get_stop_words(language)

    def summarize(self, text: str, sentences_count: int = 3, **kwargs) -> str:
        """TextRank com bias para primeiras sentenças"""
        parser = PlaintextParser.from_string(text, Tokenizer(self.language))

        # Pegar mais sentenças que o necessário
        extra = min(5, sentences_count * 2)
        candidates = list(self.summarizer(parser.document, sentences_count + extra))

        # Re-ranquear dando peso à posição
        # Encontrar índice original de cada sentença
        all_sentences = list(parser.document.sentences)
        sentence_positions = []

        for candidate in candidates:
            candidate_text = str(candidate)
            for idx, sent in enumerate(all_sentences):
                if str(sent) == candidate_text:
                    sentence_positions.append((candidate, idx))
                    break

        # Aplicar weight de posição
        weighted = []
        for sent, pos in sentence_positions:
            weight = 1.0 + (1.0 / (pos + 1)) * 0.5
            if pos == 0:
                weight *= 1.2
            weighted.append((sent, weight))

        # Re-ordenar e pegar top N
        weighted.sort(key=lambda x: x[1], reverse=True)
        selected = [s for s, _ in weighted[:sentences_count]]

        return " ".join(str(s) for s in selected)


class BERTExtractiveSummarizer(BaseSummarizer):
    """
    BERT Extractive usando embeddings semânticos
    
    Diferenças vs TextRank:
    - TextRank: grafo baseado em overlap de palavras
    - BERT: similaridade semântica via embeddings contextuais
    
    Algoritmo:
    1. Gera embedding BERT para cada sentença
    2. Gera embedding para documento inteiro (centroid)
    3. Calcula similaridade coseno: sentença <-> documento
    4. Seleciona sentenças mais representativas
    """

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        super().__init__("BGE-M3-Extractive")
        self.model_name = model_name
        self._model = None
        
    def _load_model(self):
        """Lazy loading do modelo (só carrega quando necessário)"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            print(f"   Carregando modelo BERT: {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    def _split_sentences(self, text: str):
        """Split simples em sentenças"""
        import re
        # Split por pontuação final
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Filtrar sentenças muito curtas
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        return sentences
    
    def _clean_sentence(self, sentence: str) -> str:
        """Limpeza básica de sentença"""
        import re
        text = str(sentence)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
        text = re.sub(r'<.*?>', '', text)
        return text.strip()
    
    def summarize(
        self,
        text: str,
        num_sentences: int = 3,
        ratio: float = None,
        use_mmr: bool = True,
        diversity_lambda: float = 0.5,
        **kwargs
    ) -> str:
        """
        Gera resumo usando embeddings BERT
        
        Args:
            text: Texto completo
            num_sentences: Número de sentenças (se ratio=None)
            ratio: Alternativa: fração do texto (0.0-1.0)
            use_mmr: Usar Maximal Marginal Relevance para diversidade
            diversity_lambda: Trade-off relevância vs diversidade (0=só relevância, 1=só diversidade)
            
        Returns:
            Resumo extractive
        """
        # Carregar modelo
        model = self._load_model()
        
        # Split em sentenças
        sentences = self._split_sentences(text)
        
        if len(sentences) == 0:
            return ""
        
        # Calcular num_sentences se ratio especificado
        if ratio is not None:
            num_sentences = max(1, int(len(sentences) * ratio))
        
        num_sentences = min(num_sentences, len(sentences))
        
        # Limpar sentenças
        clean_sentences = [self._clean_sentence(s) for s in sentences]
        
        # Gerar embeddings
        sentence_embeddings = model.encode(clean_sentences, show_progress_bar=False)
        
        # Embedding do documento (centroid)
        doc_embedding = np.mean(sentence_embeddings, axis=0).reshape(1, -1)
        
        # Calcular similaridade de cada sentença com documento
        similarities = cosine_similarity(sentence_embeddings, doc_embedding).flatten()
        
        if use_mmr:
            # Maximal Marginal Relevance: balanço relevância + diversidade
            selected_indices = self._mmr_selection(
                sentence_embeddings,
                similarities,
                num_sentences,
                diversity_lambda
            )
        else:
            # Simples: top-k por similaridade
            selected_indices = np.argsort(similarities)[-num_sentences:][::-1]
        
        # Ordenar por posição original (manter fluxo narrativo)
        selected_indices = sorted(selected_indices)
        
        # Construir resumo
        summary_sentences = [sentences[i] for i in selected_indices]
        summary = " ".join(summary_sentences)
        
        return summary
    
    def _mmr_selection(
        self,
        embeddings: np.ndarray,
        relevance_scores: np.ndarray,
        k: int,
        lambda_param: float = 0.5
    ):
        """
        Maximal Marginal Relevance: seleciona sentenças relevantes E diversas
        
        MMR = λ * Relevance - (1-λ) * max(Similarity com já selecionadas)
        
        Args:
            embeddings: Embeddings das sentenças
            relevance_scores: Scores de relevância (similaridade com documento)
            k: Número de sentenças a selecionar
            lambda_param: Trade-off relevância vs diversidade
            
        Returns:
            Índices das sentenças selecionadas
        """
        selected = []
        remaining = list(range(len(embeddings)))
        
        # Primeira sentença: mais relevante
        first = np.argmax(relevance_scores)
        selected.append(first)
        remaining.remove(first)
        
        # Demais sentenças: balancear relevância + diversidade
        while len(selected) < k and remaining:
            mmr_scores = []
            
            for idx in remaining:
                # Relevância
                relevance = relevance_scores[idx]
                
                # Similaridade máxima com sentenças já selecionadas
                selected_embeddings = embeddings[selected]
                current_embedding = embeddings[idx].reshape(1, -1)
                similarities = cosine_similarity(current_embedding, selected_embeddings).flatten()
                max_similarity = np.max(similarities)
                
                # MMR score
                mmr = lambda_param * relevance - (1 - lambda_param) * max_similarity
                mmr_scores.append((idx, mmr))
            
            # Selecionar sentença com maior MMR
            best_idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected.append(best_idx)
            remaining.remove(best_idx)
        
        return selected


class SimpleBERTSummarizer(BaseSummarizer):
    """
    Versão simplificada do BERT para comparação
    Apenas top-k por similaridade, sem MMR
    """
    
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        super().__init__("BGE-M3-Simple")
        self.bert = BERTExtractiveSummarizer(model_name)
    
    def summarize(self, text: str, num_sentences: int = 3, **kwargs) -> str:
        return self.bert.summarize(
            text,
            num_sentences=num_sentences,
            use_mmr=False,  # Sem MMR
            **kwargs
        )
