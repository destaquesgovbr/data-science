"""
NewsClassifier - Serviço de classificação de notícias sem dependência de dataset
Recebe notícias via parâmetro e retorna classificações em JSON
"""

import json
import logging
from typing import Dict, List, Union, Optional
from .llm_client import BedrockLLMClient

logger = logging.getLogger(__name__)


class NewsClassifier:
    """
    Classificador de notícias standalone.

    Não acessa base de dados - recebe notícias via parâmetro e retorna JSON.
    Ideal para APIs, microserviços e integrações.

    Exemplo de uso:
        classifier = NewsClassifier(
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            taxonomy=taxonomy_dict
        )

        # Classificar uma notícia
        result = classifier.classify_single({
            'title': 'Governo anuncia reforma tributária',
            'content': 'Medida visa simplificar...'
        })

        # Classificar múltiplas notícias
        results = classifier.classify_batch([
            {'title': '...', 'content': '...'},
            {'title': '...', 'content': '...'}
        ])
    """

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1",
        taxonomy: Optional[Dict] = None,
        batch_size: int = 4, # recomendo manter pequeno para evitar timeouts e erros de rate limit
        sleep_between_batches: float = 0.5, # recomendo 0.5s para balancear velocidade e evitar rate limit
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        verbose: bool = False
    ):
        """
        Inicializa o classificador.

        Args:
            model_id: ID do modelo Bedrock (padrão: Claude Haiku)
            region: Região AWS (padrão: us-east-1)
            taxonomy: Taxonomia predefinida (opcional)
            batch_size: Tamanho do batch para processamento paralelo
            sleep_between_batches: Delay entre batches (rate limiting)
            aws_access_key_id: Credencial AWS (opcional)
            aws_secret_access_key: Credencial AWS (opcional)
            aws_session_token: Token de sessão AWS (opcional)
            verbose: Habilitar logs detalhados
        """
        self.verbose = verbose

        if verbose:
            logging.basicConfig(level=logging.INFO)
            logger.info("Inicializando NewsClassifier...")

        # Cliente LLM
        self.llm_client = BedrockLLMClient(
            model_id=model_id,
            region=region,
            taxonomy=taxonomy,
            batch_size=batch_size,
            sleep_between_batches=sleep_between_batches,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token
        )

        if verbose:
            logger.info(f"✓ Classificador inicializado (modelo: {model_id})")

    def classify_single(
        self,
        news: Dict,
        return_format: str = "json"
    ) -> Union[Dict, str]:
        """
        Classifica uma única notícia.

        Args:
            news: Dicionário com dados da notícia.
                  Campos esperados: title, content (obrigatórios)
                  Campos opcionais: subtitle, editorial_lead, unique_id
            return_format: Formato de retorno ("json" ou "dict")

        Returns:
            Classificação da notícia (dict ou JSON string)

        Exemplo:
            result = classifier.classify_single({
                'title': 'Governo anuncia reforma tributária',
                'subtitle': 'Medida visa simplificar sistema',
                'content': 'O governo federal anunciou hoje...'
            })

            # Retorna:
            {
                'theme_1_level_1': 'Economia e Finanças',
                'theme_1_level_1_code': '01',
                'theme_1_level_1_label': 'Economia e Finanças',
                'theme_1_level_2_code': '01.02',
                'theme_1_level_2_label': 'Fiscalização e Tributação',
                'theme_1_level_3_code': '01.02.03',
                'theme_1_level_3_label': 'Reforma Tributária',
                'most_specific_theme_code': '01.02.03',
                'most_specific_theme_label': 'Reforma Tributária',
                'summary': 'Governo federal anuncia proposta de reforma...'
            }
        """
        # Validar campos obrigatórios
        if 'title' not in news or 'content' not in news:
            raise ValueError("Campos obrigatórios ausentes: 'title' e 'content'")

        if self.verbose:
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            logger.info(f"Classificando: {title}")

        # Enriquecer (retorna lista com 1 item)
        enriched = self.llm_client.enrich_news_batch([news])

        # Extrair resultado
        result = enriched[0]

        # Remover campos originais, manter apenas classificação
        classification = self._extract_classification_fields(result)

        if self.verbose:
            theme = classification.get('most_specific_theme_label', 'N/A')
            logger.info(f"✓ Classificado: {theme}")

        # Retornar formato solicitado
        if return_format == "json":
            return json.dumps(classification, ensure_ascii=False, indent=2)
        else:
            return classification

    def classify_batch(
        self,
        news_list: List[Dict],
        return_format: str = "json"
    ) -> Union[List[Dict], str]:
        """
        Classifica múltiplas notícias em batch.

        Args:
            news_list: Lista de dicionários com notícias
            return_format: Formato de retorno ("json" ou "list")

        Returns:
            Lista de classificações (list ou JSON string)

        Exemplo:
            results = classifier.classify_batch([
                {
                    'title': 'Governo anuncia reforma tributária',
                    'content': 'O governo federal...'
                },
                {
                    'title': 'Nova política de saúde é aprovada',
                    'content': 'O Ministério da Saúde...'
                }
            ])
        """
        # Validar campos obrigatórios
        for idx, news in enumerate(news_list):
            if 'title' not in news or 'content' not in news:
                raise ValueError(
                    f"Notícia {idx}: campos obrigatórios ausentes ('title' e 'content')"
                )

        if self.verbose:
            logger.info(f"Classificando batch de {len(news_list)} notícias...")

        # Enriquecer todas
        enriched = self.llm_client.enrich_news_batch(news_list)

        # Extrair apenas campos de classificação
        classifications = [
            self._extract_classification_fields(result)
            for result in enriched
        ]

        if self.verbose:
            success_count = sum(
                1 for c in classifications
                if c.get('theme_1_level_1') is not None
            )
            logger.info(f"✓ Classificadas: {success_count}/{len(news_list)} notícias")

        # Retornar formato solicitado
        if return_format == "json":
            return json.dumps(classifications, ensure_ascii=False, indent=2)
        else:
            return classifications

    def _extract_classification_fields(self, enriched: Dict) -> Dict:
        """
        Extrai apenas campos de classificação do resultado enriquecido.

        Args:
            enriched: Resultado completo do enriquecimento

        Returns:
            Dicionário com apenas campos de classificação
        """
        classification_fields = [
            'theme_1_level_1',
            'theme_1_level_1_code',
            'theme_1_level_1_label',
            'theme_1_level_2_code',
            'theme_1_level_2_label',
            'theme_1_level_3_code',
            'theme_1_level_3_label',
            'most_specific_theme_code',
            'most_specific_theme_label',
            'summary',
            'sentiment',
            'entities'
        ]

        # Incluir unique_id se existir (útil para rastreabilidade)
        classification = {}
        if 'unique_id' in enriched:
            classification['unique_id'] = enriched['unique_id']

        # Adicionar campos de classificação
        for field in classification_fields:
            classification[field] = enriched.get(field)

        return classification

    def get_taxonomy_summary(self) -> Dict:
        """
        Retorna resumo da taxonomia em uso (se disponível).

        Returns:
            Dicionário com estatísticas da taxonomia
        """
        if self.llm_client.taxonomy is None:
            return {
                'mode': 'organic',
                'description': 'Classificação orgânica sem taxonomia predefinida'
            }

        # Contar categorias
        taxonomy = self.llm_client.taxonomy
        level_1_count = len(taxonomy)

        level_2_count = 0
        level_3_count = 0

        for cat in taxonomy.values():
            if 'subcategories' in cat:
                level_2_count += len(cat['subcategories'])
                for subcat in cat['subcategories'].values():
                    if 'subcategories' in subcat:
                        level_3_count += len(subcat['subcategories'])

        return {
            'mode': 'predefined',
            'level_1_categories': level_1_count,
            'level_2_categories': level_2_count,
            'level_3_categories': level_3_count,
            'total_categories': level_1_count + level_2_count + level_3_count
        }
