"""
Chunking strategies for RAG system.

Implements:
- Fixed-size chunking (baseline)
- Semantic chunking (similarity-based)
- Paragraph chunking (natural boundaries)

Based on best practices from LangChain and research papers.
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass
import numpy as np
from abc import ABC, abstractmethod

# Optional: spaCy for advanced NLP
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    content: str
    chunk_index: int
    chunk_type: str  # 'fixed', 'semantic', 'paragraph'
    char_start: int
    char_end: int
    metadata: Optional[Dict] = None

    def __len__(self) -> int:
        return len(self.content)

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Chunk({self.chunk_index}, type={self.chunk_type}, len={len(self)}, preview='{preview}')"


class Chunker(ABC):
    """Abstract base class for chunkers."""

    @abstractmethod
    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """Chunk text into smaller pieces."""
        pass


class FixedSizeChunker(Chunker):
    """
    Fixed-size chunking with overlap.

    Simple and fast, but may break sentences/paragraphs.
    Good baseline for comparison.

    Args:
        chunk_size: Number of characters per chunk
        chunk_overlap: Number of characters to overlap between chunks
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Chunk text into fixed-size pieces with overlap.

        Example:
            text = "Long document..."
            chunker = FixedSizeChunker(chunk_size=1000, chunk_overlap=200)
            chunks = chunker.chunk(text)
        """

        chunks = []
        chunk_index = 0
        start = 0

        while start < len(text):
            # Calculate end position
            end = min(start + self.chunk_size, len(text))

            # Extract chunk
            chunk_text = text[start:end]

            # Skip empty chunks
            if chunk_text.strip():
                chunks.append(Chunk(
                    content=chunk_text.strip(),
                    chunk_index=chunk_index,
                    chunk_type='fixed',
                    char_start=start,
                    char_end=end,
                    metadata={'chunk_size': self.chunk_size, 'overlap': self.chunk_overlap}
                ))
                chunk_index += 1

            # Move start position (with overlap)
            start = end - self.chunk_overlap if end < len(text) else end

        return chunks


class SemanticChunker(Chunker):
    """
    Semantic chunking based on sentence similarity.

    Groups similar sentences together to preserve semantic coherence.
    More sophisticated than fixed-size, preserves meaning.

    Based on LangChain's SemanticChunker and research on coherence.

    Args:
        embedder: Sentence embedder (e.g., BGE-M3)
        threshold: Similarity threshold for grouping (0-1)
        min_chunk_size: Minimum chunk size in characters
        max_chunk_size: Maximum chunk size in characters
    """

    def __init__(
        self,
        embedder=None,
        threshold: float = 0.8,
        min_chunk_size: int = 200,
        max_chunk_size: int = 2000
    ):
        self.embedder = embedder
        self.threshold = threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

        # Load spaCy if available
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("pt_core_news_lg")
            except OSError:
                print("Warning: pt_core_news_lg not found. Using simple sentence splitting.")
                self.nlp = None
        else:
            self.nlp = None

    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Chunk text semantically by grouping similar sentences.

        Algorithm:
        1. Split text into sentences
        2. Embed each sentence
        3. Calculate similarity between adjacent sentences
        4. Group sentences with similarity > threshold
        5. Respect min/max chunk size constraints
        """

        # Split into sentences
        sentences = self._split_sentences(text)

        if len(sentences) == 0:
            return []

        # If no embedder, fall back to paragraph chunking
        if self.embedder is None:
            return self._fallback_paragraph_chunking(text)

        # Embed sentences
        embeddings = self.embedder.encode(sentences, normalize_embeddings=True)

        # Group by similarity
        chunks = []
        current_chunk = []
        current_start = 0
        chunk_index = 0

        for i, sentence in enumerate(sentences):
            current_chunk.append(sentence)

            # Check if we should start a new chunk
            should_split = False

            # Calculate current chunk size
            current_text = ' '.join(current_chunk)
            current_size = len(current_text)

            # Split if chunk too large
            if current_size >= self.max_chunk_size:
                should_split = True

            # Split if similarity with next sentence is low
            elif i < len(sentences) - 1:
                similarity = self._cosine_similarity(embeddings[i], embeddings[i + 1])
                if similarity < self.threshold:
                    # But respect min size
                    if current_size >= self.min_chunk_size:
                        should_split = True

            # Last sentence
            elif i == len(sentences) - 1:
                should_split = True

            if should_split and current_chunk:
                chunk_text = ' '.join(current_chunk).strip()

                if chunk_text:
                    # Find char positions
                    char_start = text.find(current_chunk[0], current_start)
                    char_end = char_start + len(chunk_text)

                    chunks.append(Chunk(
                        content=chunk_text,
                        chunk_index=chunk_index,
                        chunk_type='semantic',
                        char_start=char_start,
                        char_end=char_end,
                        metadata={
                            'threshold': self.threshold,
                            'num_sentences': len(current_chunk)
                        }
                    ))

                    chunk_index += 1
                    current_start = char_end

                current_chunk = []

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""

        if self.nlp:
            # Use spaCy for better sentence splitting
            doc = self.nlp(text)
            return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        else:
            # Simple regex-based splitting
            # Handles common abbreviations in Portuguese
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ])', text)
            return [s.strip() for s in sentences if s.strip()]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(np.dot(vec1, vec2))

    def _fallback_paragraph_chunking(self, text: str) -> List[Chunk]:
        """Fallback to paragraph chunking if no embedder available."""
        paragraphs = text.split('\n\n')
        chunks = []
        char_start = 0

        for i, para in enumerate(paragraphs):
            if para.strip():
                chunks.append(Chunk(
                    content=para.strip(),
                    chunk_index=i,
                    chunk_type='paragraph',
                    char_start=char_start,
                    char_end=char_start + len(para),
                    metadata={'fallback': True}
                ))
            char_start += len(para) + 2  # +2 for '\n\n'

        return chunks


class ParagraphChunker(Chunker):
    """
    Paragraph-based chunking.

    Respects natural document boundaries (paragraphs).
    Good for well-structured documents.

    Args:
        merge_small: Merge paragraphs smaller than threshold
        merge_threshold: Minimum paragraph size (characters)
    """

    def __init__(self, merge_small: bool = True, merge_threshold: int = 100):
        self.merge_small = merge_small
        self.merge_threshold = merge_threshold

    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Chunk text by paragraphs.

        Optionally merges small paragraphs to avoid tiny chunks.
        """

        # Split by double newline
        paragraphs = text.split('\n\n')

        if not self.merge_small:
            # No merging, return as-is
            chunks = []
            char_start = 0

            for i, para in enumerate(paragraphs):
                if para.strip():
                    chunks.append(Chunk(
                        content=para.strip(),
                        chunk_index=i,
                        chunk_type='paragraph',
                        char_start=char_start,
                        char_end=char_start + len(para)
                    ))
                char_start += len(para) + 2

            return chunks

        # Merge small paragraphs
        merged = []
        current = []
        current_size = 0

        for para in paragraphs:
            if not para.strip():
                continue

            para_size = len(para)

            if current_size + para_size <= self.merge_threshold or not current:
                current.append(para.strip())
                current_size += para_size
            else:
                # Start new chunk
                merged.append('\n\n'.join(current))
                current = [para.strip()]
                current_size = para_size

        # Add last chunk
        if current:
            merged.append('\n\n'.join(current))

        # Convert to Chunk objects
        chunks = []
        char_start = 0

        for i, chunk_text in enumerate(merged):
            chunks.append(Chunk(
                content=chunk_text,
                chunk_index=i,
                chunk_type='paragraph',
                char_start=char_start,
                char_end=char_start + len(chunk_text),
                metadata={'merged': self.merge_small}
            ))
            char_start += len(chunk_text) + 2

        return chunks


class RecursiveChunker(Chunker):
    """
    Recursive chunking with multiple separators.

    LangChain-style recursive splitting.
    Tries to split on larger boundaries first (paragraphs),
    then falls back to smaller ones (sentences, words).

    Args:
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between chunks
        separators: List of separators to try (in order)
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", "! ", "? ", " "]

    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Recursively chunk text using multiple separators.
        """

        return self._recursive_split(text, self.separators)

    def _recursive_split(
        self,
        text: str,
        separators: List[str],
        char_offset: int = 0
    ) -> List[Chunk]:
        """
        Recursively split text.
        """

        # Base case: text fits in chunk
        if len(text) <= self.chunk_size:
            return [Chunk(
                content=text.strip(),
                chunk_index=0,
                chunk_type='recursive',
                char_start=char_offset,
                char_end=char_offset + len(text)
            )]

        # Try separators in order
        for i, separator in enumerate(separators):
            if separator in text:
                # Split by this separator
                splits = text.split(separator)

                # Reconstruct chunks
                chunks = []
                current = []
                current_len = 0
                chunk_index = 0
                current_start = char_offset

                for split in splits:
                    split_len = len(split) + len(separator)

                    if current_len + split_len > self.chunk_size and current:
                        # Finalize current chunk
                        chunk_text = separator.join(current)
                        chunks.append(Chunk(
                            content=chunk_text.strip(),
                            chunk_index=chunk_index,
                            chunk_type='recursive',
                            char_start=current_start,
                            char_end=current_start + len(chunk_text),
                            metadata={'separator': separator}
                        ))

                        chunk_index += 1

                        # Handle overlap
                        if self.chunk_overlap > 0 and current:
                            overlap_text = current[-1]
                            current = [overlap_text, split]
                            current_len = len(overlap_text) + split_len
                            current_start += len(chunk_text) - len(overlap_text)
                        else:
                            current = [split]
                            current_len = split_len
                            current_start += len(chunk_text)
                    else:
                        current.append(split)
                        current_len += split_len

                # Add last chunk
                if current:
                    chunk_text = separator.join(current)
                    chunks.append(Chunk(
                        content=chunk_text.strip(),
                        chunk_index=chunk_index,
                        chunk_type='recursive',
                        char_start=current_start,
                        char_end=current_start + len(chunk_text),
                        metadata={'separator': separator}
                    ))

                # Reindex
                for idx, chunk in enumerate(chunks):
                    chunk.chunk_index = idx

                return chunks

        # Fallback: split by character
        return self._split_by_char(text, char_offset)

    def _split_by_char(self, text: str, char_offset: int) -> List[Chunk]:
        """Fallback: split by character count."""
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            chunks.append(Chunk(
                content=text[start:end].strip(),
                chunk_index=chunk_index,
                chunk_type='recursive',
                char_start=char_offset + start,
                char_end=char_offset + end,
                metadata={'separator': 'character'}
            ))

            chunk_index += 1
            start = end - self.chunk_overlap if end < len(text) else end

        return chunks


def create_chunker(strategy: str, **kwargs) -> Chunker:
    """
    Factory function to create chunkers.

    Args:
        strategy: 'fixed', 'semantic', 'paragraph', 'recursive'
        **kwargs: Arguments for the specific chunker

    Returns:
        Chunker instance

    Example:
        chunker = create_chunker('semantic', threshold=0.8, embedder=model)
        chunks = chunker.chunk(text)
    """

    strategies = {
        'fixed': FixedSizeChunker,
        'semantic': SemanticChunker,
        'paragraph': ParagraphChunker,
        'recursive': RecursiveChunker,
    }

    if strategy not in strategies:
        raise ValueError(f"Unknown strategy: {strategy}. Choose from {list(strategies.keys())}")

    return strategies[strategy](**kwargs)
