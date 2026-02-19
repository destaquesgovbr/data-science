"""
Exemplo de uso do NewsClassifier como API/Microserviço
Demonstra como usar o classificador em endpoints REST
"""

from news_enrichment import NewsClassifier
import yaml
import json
from typing import Dict, List
from pathlib import Path

# Configuração de paths (independente de onde o script é executado)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ARVORE_PATH = PROJECT_ROOT / "arvore.yaml"
DATA_DIR = PROJECT_ROOT / "data"

# ============================================================================
# 1. Setup inicial (fazer uma vez no startup da aplicação)
# ============================================================================

def setup_classifier():
    """Inicializa o classificador (executar no startup)."""
    print("Inicializando classificador...")

    # Carregar taxonomia
    with open(ARVORE_PATH, "r", encoding="utf-8") as f:
        taxonomy_raw = yaml.safe_load(f)

    # Parse taxonomia (função auxiliar)
    taxonomy = parse_taxonomy(taxonomy_raw)

    # Criar classificador
    classifier = NewsClassifier(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region="us-east-1",
        taxonomy=taxonomy,
        batch_size=4,
        sleep_between_batches=0.5,
        verbose=False  # Desabilitar logs em produção
    )

    print("✓ Classificador pronto\n")
    return classifier


def parse_taxonomy(taxonomy_raw):
    """Converte taxonomia YAML para formato estruturado."""
    taxonomy = {}

    for key, value in taxonomy_raw.items():
        code = key.split(" - ")[0].strip()
        label = key.split(" - ")[1].strip()

        taxonomy[code] = {
            "label": label,
            "subcategories": {}
        }

        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                subcode = subkey.split(" - ")[0].strip()
                sublabel = subkey.split(" - ")[1].strip()

                taxonomy[code]["subcategories"][subcode] = {
                    "label": sublabel,
                    "subcategories": {}
                }

                if isinstance(subvalue, list):
                    for item in subvalue:
                        if isinstance(item, str) and " - " in item:
                            itemcode = item.split(" - ")[0].strip()
                            itemlabel = item.split(" - ")[1].strip()

                            taxonomy[code]["subcategories"][subcode]["subcategories"][itemcode] = {
                                "label": itemlabel
                            }

    return taxonomy


# ============================================================================
# 2. Funções para endpoints (FastAPI, Flask, etc.)
# ============================================================================

def classify_news_endpoint(classifier: NewsClassifier, news_data: Dict) -> Dict:
    """
    Endpoint para classificar uma única notícia.

    Exemplo de uso com FastAPI:
        @app.post("/classify")
        def classify(news: NewsRequest):
            return classify_news_endpoint(classifier, news.dict())

    Args:
        classifier: Instância do NewsClassifier
        news_data: Dict com dados da notícia (title, content obrigatórios)

    Returns:
        Dict com classificação e status
    """
    try:
        # Validar campos obrigatórios
        if 'title' not in news_data or 'content' not in news_data:
            return {
                'status': 'error',
                'message': 'Campos obrigatórios ausentes: title e content',
                'data': None
            }

        # Classificar
        result = classifier.classify_single(news_data, return_format="dict")

        return {
            'status': 'success',
            'message': 'Notícia classificada com sucesso',
            'data': result
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'data': None
        }


def classify_batch_endpoint(classifier: NewsClassifier, news_list: List[Dict]) -> Dict:
    """
    Endpoint para classificar múltiplas notícias.

    Exemplo de uso com FastAPI:
        @app.post("/classify/batch")
        def classify_batch(news_list: List[NewsRequest]):
            return classify_batch_endpoint(classifier, [n.dict() for n in news_list])

    Args:
        classifier: Instância do NewsClassifier
        news_list: Lista de dicts com notícias

    Returns:
        Dict com classificações e status
    """
    try:
        # Validar lista não vazia
        if not news_list:
            return {
                'status': 'error',
                'message': 'Lista de notícias vazia',
                'data': None
            }

        # Validar campos obrigatórios
        for idx, news in enumerate(news_list):
            if 'title' not in news or 'content' not in news:
                return {
                    'status': 'error',
                    'message': f'Notícia {idx}: campos obrigatórios ausentes (title e content)',
                    'data': None
                }

        # Classificar batch
        results = classifier.classify_batch(news_list, return_format="list")

        return {
            'status': 'success',
            'message': f'{len(results)} notícias classificadas com sucesso',
            'data': results
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'data': None
        }


# ============================================================================
# 3. Exemplo de uso (simulando requests HTTP)
# ============================================================================

if __name__ == "__main__":
    print("="*80)
    print("EXEMPLO: NewsClassifier como API")
    print("="*80 + "\n")

    # Setup (fazer uma vez no startup)
    classifier = setup_classifier()

    # ========================================================================
    # Simular POST /classify (uma notícia)
    # ========================================================================

    print("="*80)
    print("SIMULAÇÃO: POST /classify")
    print("="*80 + "\n")

    request_payload = {
        'title': 'Governo anuncia novo programa de habitação popular',
        'content': '''
        O Ministério das Cidades anunciou hoje o lançamento do programa Minha Casa,
        Minha Vida 2.0, com meta de construir 2 milhões de moradias até 2027.
        O programa terá investimento de R$ 200 bilhões e prioriza famílias com
        renda de até 3 salários mínimos.
        '''
    }

    print("Request payload:")
    print(json.dumps(request_payload, indent=2, ensure_ascii=False))
    print()

    response = classify_news_endpoint(classifier, request_payload)

    print("Response:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    # ========================================================================
    # Simular POST /classify/batch (múltiplas notícias)
    # ========================================================================

    print("\n" + "="*80)
    print("SIMULAÇÃO: POST /classify/batch")
    print("="*80 + "\n")

    batch_payload = [
        {
            'title': 'Banco Central corta Selic em 0,5 ponto percentual',
            'content': 'Copom reduz taxa básica de juros de 11% para 10,5% ao ano...'
        },
        {
            'title': 'Ministério da Saúde distribui 50 milhões de doses de vacina',
            'content': 'Campanha nacional de vacinação inicia na próxima segunda-feira...'
        }
    ]

    print(f"Request payload: {len(batch_payload)} notícias")
    print()

    response = classify_batch_endpoint(classifier, batch_payload)

    print("Response:")
    print(f"Status: {response['status']}")
    print(f"Message: {response['message']}")
    print(f"Resultados: {len(response['data']) if response['data'] else 0}")

    if response['data']:
        for idx, result in enumerate(response['data'], 1):
            print(f"\n  Notícia {idx}:")
            print(f"    Tema: {result['most_specific_theme_label']}")
            print(f"    Resumo: {result['summary'][:60]}...")

    # ========================================================================
    # Simular erro (campos faltando)
    # ========================================================================

    print("\n" + "="*80)
    print("SIMULAÇÃO: Erro de validação")
    print("="*80 + "\n")

    invalid_payload = {
        'title': 'Título sem conteúdo'
        # Falta o campo 'content'
    }

    response = classify_news_endpoint(classifier, invalid_payload)

    print("Response (erro esperado):")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    print("\n" + "="*80)
    print("EXEMPLO CONCLUÍDO!")
    print("="*80)
    print("\nPróximos passos:")
    print("  1. Integrar com FastAPI/Flask")
    print("  2. Adicionar autenticação")
    print("  3. Implementar rate limiting")
    print("  4. Configurar logging e monitoramento")
    print("  5. Adicionar cache (Redis) para classificações frequentes")
