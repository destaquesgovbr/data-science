"""
RAG Retriever - Sistema de recuperação baseado em embeddings para taxonomia

Este módulo implementa Retrieval-Augmented Generation (RAG) para selecionar
as categorias mais relevantes da taxonomia antes de enviar ao LLM.

Workflow:
1. Cria embeddings de todas as categorias da taxonomia
2. Para cada notícia, cria embedding do conteúdo
3. Busca top-k categorias mais similares (cosine similarity)
4. Passa apenas essas categorias filtradas ao LLM

Nota: Esta é uma implementação para fins de comparação. Na prática, para
uma taxonomia de 410 categorias, passar todas diretamente ao LLM (como
fazemos atualmente) geralmente produz melhores resultados.
"""

import logging
import yaml
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers não disponível. Instale com: poetry install --extras rag")


class TaxonomyRAGRetriever:
    """
    Sistema RAG para recuperar categorias relevantes da taxonomia.

    Usa embeddings semânticos para encontrar as categorias mais próximas
    ao conteúdo da notícia antes de enviar ao LLM.
    """

    def __init__(
        self,
        taxonomy_path: str,
        model_name: str = "neuralmind/bert-base-portuguese-cased",
        top_k: int = 50,
        cache_embeddings: bool = True
    ):
        """
        Inicializa o retriever RAG.

        Args:
            taxonomy_path: Caminho para o arquivo arvore.yaml
            model_name: Modelo de embeddings (padrão: BERT português)
            top_k: Número de categorias a recuperar
            cache_embeddings: Se deve cachear embeddings em memória
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers é necessário para RAG. "
                "Instale com: poetry install --extras rag"
            )

        self.taxonomy_path = taxonomy_path
        self.top_k = top_k
        self.cache_embeddings = cache_embeddings

        # Carregar modelo de embeddings
        logger.info(f"Carregando modelo de embeddings: {model_name}")
        self.model = SentenceTransformer(model_name)
        logger.info("✓ Modelo carregado")

        # Carregar e processar taxonomia
        logger.info("Processando taxonomia...")
        self.taxonomy = self._load_taxonomy()
        self.categories = self._flatten_taxonomy()
        logger.info(f"✓ {len(self.categories)} categorias processadas")

        # Criar embeddings
        logger.info("Criando embeddings da taxonomia...")
        self.category_embeddings = self._create_category_embeddings()
        logger.info("✓ Embeddings criados")

    def _load_taxonomy(self) -> Dict:
        """Carrega taxonomia do arquivo YAML."""
        with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _flatten_taxonomy(self) -> List[Dict]:
        """
        Achata a taxonomia hierárquica em lista plana de categorias.

        Cada categoria contém:
        - code: Código completo (ex: "01.01.01")
        - label: Label completo (ex: "Política Fiscal")
        - level1, level2, level3: Hierarquia completa
        - context: Texto rico para embedding (hierarquia + label)
        """
        categories = []

        for level1_key, level1_data in self.taxonomy.items():
            # Parse level 1
            level1_code = level1_key.split(" - ")[0].strip()
            level1_label = level1_key.split(" - ")[1].strip()

            if not isinstance(level1_data, dict):
                continue

            for level2_key, level2_data in level1_data.items():
                # Parse level 2
                level2_code = level2_key.split(" - ")[0].strip()
                level2_label = level2_key.split(" - ")[1].strip()

                if not isinstance(level2_data, list):
                    continue

                for level3_item in level2_data:
                    # Parse level 3
                    if isinstance(level3_item, str) and " - " in level3_item:
                        level3_code = level3_item.split(" - ")[0].strip()
                        level3_label = level3_item.split(" - ")[1].strip()

                        # Criar contexto rico para embedding
                        context = (
                            f"{level1_label} > {level2_label} > {level3_label}. "
                            f"Categoria: {level3_label}. "
                            f"Área: {level1_label}. "
                            f"Subtema: {level2_label}."
                        )

                        categories.append({
                            'code': level3_code,
                            'label': level3_label,
                            'level1_code': level1_code,
                            'level1_label': level1_label,
                            'level2_code': level2_code,
                            'level2_label': level2_label,
                            'level3_code': level3_code,
                            'level3_label': level3_label,
                            'context': context,
                            'full_path': f"{level1_label} > {level2_label} > {level3_label}"
                        })

        return categories

    def _create_category_embeddings(self) -> np.ndarray:
        """
        Cria embeddings para todas as categorias.

        Usa o campo 'context' que contém hierarquia completa para
        criar representações semânticas mais ricas.
        """
        contexts = [cat['context'] for cat in self.categories]
        embeddings = self.model.encode(
            contexts,
            convert_to_numpy=True,
            show_progress_bar=True
        )
        return embeddings

    def retrieve_relevant_categories(
        self,
        news_text: str,
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Recupera as categorias mais relevantes para uma notícia.

        Args:
            news_text: Texto da notícia (título + conteúdo)
            top_k: Número de categorias a retornar (None = usa self.top_k)

        Returns:
            Lista de dicionários com categorias e scores de similaridade
        """
        k = top_k if top_k is not None else self.top_k

        # Criar embedding da notícia
        news_embedding = self.model.encode(
            news_text,
            convert_to_numpy=True
        )

        # Calcular similaridade cosine
        similarities = self._cosine_similarity(
            news_embedding,
            self.category_embeddings
        )

        # Pegar top-k índices
        top_indices = np.argsort(similarities)[-k:][::-1]

        # Montar resultado
        results = []
        for idx in top_indices:
            cat = self.categories[idx].copy()
            cat['similarity_score'] = float(similarities[idx])
            results.append(cat)

        return results

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> np.ndarray:
        """
        Calcula similaridade cosine entre um vetor e uma matriz.

        Args:
            vec1: Vetor 1D (embedding da notícia)
            vec2: Matriz 2D (embeddings das categorias)

        Returns:
            Array 1D com similaridades
        """
        # Normalizar vetores
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2, axis=1, keepdims=True)

        # Produto escalar = similaridade cosine quando normalizados
        return np.dot(vec2_norm, vec1_norm)

    def build_filtered_taxonomy(
        self,
        relevant_categories: List[Dict]
    ) -> Dict:
        """
        Reconstrói uma taxonomia hierárquica com apenas as categorias relevantes.

        Útil para passar ao LLM no mesmo formato da taxonomia original,
        mas contendo apenas as categorias recuperadas pelo RAG.

        Args:
            relevant_categories: Lista de categorias recuperadas

        Returns:
            Dicionário no formato da taxonomia original (hierárquico)
        """
        filtered_taxonomy = {}

        for cat in relevant_categories:
            level1_key = f"{cat['level1_code']} - {cat['level1_label']}"
            level2_key = f"{cat['level2_code']} - {cat['level2_label']}"
            level3_item = f"{cat['level3_code']} - {cat['level3_label']}"

            # Criar estrutura hierárquica
            if level1_key not in filtered_taxonomy:
                filtered_taxonomy[level1_key] = {}

            if level2_key not in filtered_taxonomy[level1_key]:
                filtered_taxonomy[level1_key][level2_key] = []

            # Adicionar level 3 se não existir
            if level3_item not in filtered_taxonomy[level1_key][level2_key]:
                filtered_taxonomy[level1_key][level2_key].append(level3_item)

        return filtered_taxonomy

    def get_stats(self) -> Dict:
        """Retorna estatísticas do retriever."""
        return {
            'total_categories': len(self.categories),
            'embedding_dim': self.category_embeddings.shape[1],
            'model': self.model.get_sentence_embedding_dimension(),
            'top_k': self.top_k,
            'taxonomy_path': self.taxonomy_path
        }


def demo():
    """Demonstração de uso do RAG retriever."""
    import sys
    from pathlib import Path

    # Encontrar caminho do projeto
    project_root = Path(__file__).parent.parent.parent.parent
    taxonomy_path = project_root / "arvore.yaml"

    print("=" * 80)
    print("DEMO: RAG Retriever para Taxonomia")
    print("=" * 80)
    print()

    # Inicializar retriever
    print("Inicializando retriever...")
    retriever = TaxonomyRAGRetriever(
        taxonomy_path=str(taxonomy_path),
        top_k=20
    )

    print("\n✓ Retriever inicializado!")
    print(f"  Categorias totais: {retriever.get_stats()['total_categories']}")
    print(f"  Top-K: {retriever.get_stats()['top_k']}")
    print()

    # Exemplo de notícia
    news_text = """
    Governo anuncia reforma tributária para simplificar impostos

    O Ministério da Fazenda apresentou hoje uma proposta de reforma tributária
    que visa simplificar o sistema de impostos brasileiro, unificando tributos
    federais, estaduais e municipais. A medida deve reduzir a carga burocrática
    para empresas e facilitar a arrecadação.
    """

    print("Notícia de exemplo:")
    print("-" * 80)
    print(news_text.strip())
    print("-" * 80)
    print()

    # Recuperar categorias
    print(f"Recuperando top-{retriever.top_k} categorias mais relevantes...")
    relevant = retriever.retrieve_relevant_categories(news_text)

    print("\nCategorias recuperadas:")
    print("=" * 80)
    for i, cat in enumerate(relevant[:10], 1):
        print(f"{i}. [{cat['similarity_score']:.3f}] {cat['full_path']}")

    print("\n✓ Demo concluída!")


if __name__ == "__main__":
    demo()
