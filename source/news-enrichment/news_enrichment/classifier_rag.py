"""
NewsClassifierRAG - Classificador com Retrieval-Augmented Generation

Este módulo implementa uma versão do classificador que usa RAG para filtrar
a taxonomia antes de enviar ao LLM.

Workflow RAG:
1. Recebe notícia
2. Usa embeddings para encontrar top-k categorias mais relevantes
3. Passa apenas essas k categorias ao LLM (ao invés das 410 completas)
4. LLM classifica usando taxonomia filtrada

Nota comparativa:
- Abordagem Direta (atual): Passa todas 410 categorias → LLM decide
- Abordagem RAG (esta): Embeddings filtram 50 categorias → LLM decide

Trade-offs:
+ RAG: Menor contexto, potencialmente mais rápido
- RAG: Depende da qualidade dos embeddings, pode perder categorias corretas
"""

import json
import logging
from typing import Dict, List, Union, Optional
from pathlib import Path

from .llm_client import BedrockLLMClient
from .rag_retriever import TaxonomyRAGRetriever

logger = logging.getLogger(__name__)


class NewsClassifierRAG:
    """
    Classificador de notícias com RAG.

    Usa embeddings semânticos para pré-filtrar a taxonomia antes
    de enviar ao LLM, reduzindo o tamanho do contexto.

    Exemplo de uso:
        classifier = NewsClassifierRAG(
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            taxonomy_path="arvore.yaml",
            top_k=50  # Recupera 50 categorias mais relevantes
        )

        result = classifier.classify_single({
            'title': 'Governo anuncia reforma tributária',
            'content': 'Medida visa simplificar...'
        })
    """

    def __init__(
        self,
        taxonomy_path: str,
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1",
        embedding_model: str = "neuralmind/bert-base-portuguese-cased",
        top_k: int = 50,
        batch_size: int = 4,
        sleep_between_batches: float = 0.5,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        verbose: bool = False
    ):
        """
        Inicializa o classificador RAG.

        Args:
            taxonomy_path: Caminho para arvore.yaml
            model_id: ID do modelo Bedrock (padrão: Claude Haiku)
            region: Região AWS (padrão: us-east-1)
            embedding_model: Modelo para embeddings (padrão: BERT português)
            top_k: Número de categorias a recuperar via RAG
            batch_size: Tamanho do batch para processamento paralelo
            sleep_between_batches: Delay entre batches (rate limiting)
            aws_access_key_id: Credencial AWS (opcional)
            aws_secret_access_key: Credencial AWS (opcional)
            aws_session_token: Token de sessão AWS (opcional)
            verbose: Habilitar logs detalhados
        """
        self.verbose = verbose
        self.top_k = top_k

        if verbose:
            logging.basicConfig(level=logging.INFO)
            logger.info("Inicializando NewsClassifierRAG...")

        # 1. Inicializar RAG retriever
        logger.info("Inicializando sistema RAG...")
        self.rag_retriever = TaxonomyRAGRetriever(
            taxonomy_path=taxonomy_path,
            model_name=embedding_model,
            top_k=top_k
        )
        logger.info(f"✓ RAG inicializado (top_k={top_k})")

        # 2. Inicializar LLM client (sem taxonomia fixa - será dinâmica)
        self.llm_client = BedrockLLMClient(
            model_id=model_id,
            region=region,
            taxonomy=None,  # Será passada dinamicamente por notícia
            batch_size=batch_size,
            sleep_between_batches=sleep_between_batches,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token
        )

        if verbose:
            logger.info(f"✓ Classificador RAG inicializado (modelo: {model_id})")

    def classify_single(
        self,
        news: Dict,
        return_format: str = "json",
        include_rag_metadata: bool = False
    ) -> Union[Dict, str]:
        """
        Classifica uma única notícia usando RAG.

        Args:
            news: Dicionário com dados da notícia.
                  Campos esperados: title, content (obrigatórios)
            return_format: Formato de retorno ("json" ou "dict")
            include_rag_metadata: Incluir metadados do RAG (categorias recuperadas)

        Returns:
            Dict ou JSON string com classificação + metadados RAG
        """
        # 1. Preparar texto para RAG
        news_text = f"{news.get('title', '')} {news.get('content', '')}"

        # 2. Recuperar categorias relevantes via RAG
        if self.verbose:
            logger.info(f"Recuperando top-{self.top_k} categorias relevantes...")

        relevant_categories = self.rag_retriever.retrieve_relevant_categories(
            news_text,
            top_k=self.top_k
        )

        if self.verbose:
            logger.info(f"✓ {len(relevant_categories)} categorias recuperadas")
            logger.info(f"  Top-3: {[c['full_path'] for c in relevant_categories[:3]]}")

        # 3. Construir taxonomia filtrada
        filtered_taxonomy = self.rag_retriever.build_filtered_taxonomy(
            relevant_categories
        )

        # 4. Classificar usando taxonomia filtrada
        # Nota: BedrockLLMClient espera taxonomy no init, mas podemos
        # passar no enrich_single via parâmetro (se suportado)
        # Por enquanto, vamos atualizar o client temporariamente
        original_taxonomy = self.llm_client.taxonomy
        self.llm_client.taxonomy = filtered_taxonomy

        try:
            result = self.llm_client.enrich_single(
                news.get('title', ''),
                news.get('content', ''),
                news.get('unique_id', '')
            )
        finally:
            # Restaurar taxonomia original (None)
            self.llm_client.taxonomy = original_taxonomy

        # 5. Adicionar metadados RAG se solicitado
        if include_rag_metadata:
            result['rag_metadata'] = {
                'top_k': self.top_k,
                'categories_retrieved': len(relevant_categories),
                'top_5_similarities': [
                    {
                        'category': cat['full_path'],
                        'score': cat['similarity_score']
                    }
                    for cat in relevant_categories[:5]
                ]
            }

        if return_format == "json":
            return json.dumps(result, ensure_ascii=False, indent=2)
        return result

    def classify_batch(
        self,
        news_list: List[Dict],
        return_format: str = "list",
        include_rag_metadata: bool = False
    ) -> Union[List[Dict], str]:
        """
        Classifica múltiplas notícias usando RAG.

        IMPORTANTE: Para batch, cada notícia terá sua própria taxonomia
        filtrada via RAG. Isso pode ser mais lento que a abordagem direta
        devido ao overhead de embeddings por notícia.

        Args:
            news_list: Lista de dicionários com notícias
            return_format: "list" ou "json"
            include_rag_metadata: Incluir metadados do RAG

        Returns:
            Lista de resultados ou JSON string
        """
        results = []

        for news in news_list:
            try:
                result = self.classify_single(
                    news,
                    return_format="dict",
                    include_rag_metadata=include_rag_metadata
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Erro ao classificar notícia: {e}")
                results.append({
                    'unique_id': news.get('unique_id', ''),
                    'error': str(e)
                })

        if return_format == "json":
            return json.dumps(results, ensure_ascii=False, indent=2)
        return results

    def get_stats(self) -> Dict:
        """Retorna estatísticas do classificador RAG."""
        return {
            'approach': 'RAG (Retrieval-Augmented Generation)',
            'top_k': self.top_k,
            'rag_stats': self.rag_retriever.get_stats(),
            'llm_model': self.llm_client.model_id,
            'llm_region': self.llm_client.region
        }


def demo():
    """Demonstração de uso do classificador RAG."""
    from pathlib import Path

    # Encontrar caminho do projeto
    project_root = Path(__file__).parent.parent.parent.parent
    taxonomy_path = project_root / "arvore.yaml"

    print("=" * 80)
    print("DEMO: Classificador com RAG")
    print("=" * 80)
    print()

    # Inicializar classificador
    print("Inicializando classificador RAG...")
    print("(Isso pode demorar ~30s para carregar modelo de embeddings)")
    print()

    classifier = NewsClassifierRAG(
        taxonomy_path=str(taxonomy_path),
        top_k=30,
        verbose=True
    )

    print("\n✓ Classificador inicializado!")
    stats = classifier.get_stats()
    print(f"  Abordagem: {stats['approach']}")
    print(f"  Top-K: {stats['top_k']}")
    print(f"  Categorias totais: {stats['rag_stats']['total_categories']}")
    print()

    # Exemplo de notícia
    news = {
        'unique_id': 'demo-001',
        'title': 'Governo anuncia reforma tributária para simplificar impostos',
        'content': (
            'O Ministério da Fazenda apresentou hoje uma proposta de reforma '
            'tributária que visa simplificar o sistema de impostos brasileiro, '
            'unificando tributos federais, estaduais e municipais.'
        )
    }

    print("Notícia de exemplo:")
    print("-" * 80)
    print(f"Título: {news['title']}")
    print(f"Conteúdo: {news['content']}")
    print("-" * 80)
    print()

    # Classificar
    print("Classificando com RAG...")
    result = classifier.classify_single(
        news,
        return_format="dict",
        include_rag_metadata=True
    )

    print("\nResultado:")
    print("=" * 80)
    print(f"Tema: {result.get('most_specific_theme_label', 'N/A')}")
    print(f"Nível 1: {result.get('theme_1_level_1_label', 'N/A')}")
    print(f"Nível 2: {result.get('theme_1_level_2_label', 'N/A')}")
    print(f"Nível 3: {result.get('theme_1_level_3_label', 'N/A')}")

    if 'rag_metadata' in result:
        print("\nMetadados RAG:")
        print(f"  Categorias recuperadas: {result['rag_metadata']['categories_retrieved']}")
        print("  Top-5 categorias mais similares:")
        for item in result['rag_metadata']['top_5_similarities']:
            print(f"    - [{item['score']:.3f}] {item['category']}")

    print("\n✓ Demo concluída!")


if __name__ == "__main__":
    demo()
