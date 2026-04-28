"""
Teste rápido do classificador JSON com um único modelo.

Testa Claude Haiku (modelo working no news-enrichment) em 5 notícias.
"""

import sys
from pathlib import Path
import pandas as pd

# Adicionar path para imports
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.bedrock_classifier_json import BedrockClassifierJSON


def main():
    """Teste rápido."""
    print("="*80)
    print("🧪 TESTE DO CLASSIFICADOR JSON")
    print("="*80)

    # Paths
    test_path = BASE_DIR / 'data' / 'classification' / 'news_classification_test.csv'
    taxonomy_path = BASE_DIR / 'data' / 'classification' / 'arvore.yaml'

    # Carregar apenas 5 notícias de teste
    print("\n📊 Carregando 5 notícias de teste...")
    test_df = pd.read_csv(test_path).head(5)
    print(f"   ✓ {len(test_df)} notícias carregadas")

    # Criar classificador (Claude Haiku - modelo working)
    print("\n🤖 Inicializando Claude Haiku...")
    classifier = BedrockClassifierJSON(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        model_name="Claude 3 Haiku",
        provider="anthropic",
        region="us-east-1",
        taxonomy_path=str(taxonomy_path)
    )
    # Configurar pricing
    classifier.input_price_per_mtok = 0.25
    classifier.output_price_per_mtok = 1.25
    print("   ✓ Classificador inicializado")

    # Testar classificação
    print("\n" + "="*80)
    print("📝 CLASSIFICANDO NOTÍCIAS")
    print("="*80)

    for idx, row in test_df.iterrows():
        # Combinar title e content
        text = f"{row['title']}\n\n{row['content']}"
        true_category = row['category']

        print(f"\n{'-'*80}")
        print(f"Notícia {idx + 1}:")
        print(f"Título: {row['title'][:80]}...")
        print(f"Texto: {text[:100]}...")
        print(f"Ground truth: {true_category}")

        # Classificar
        result = classifier.classify(text)

        print(f"\n🤖 Resposta do modelo:")
        print(f"Categoria predita: {result['category']}")
        print(f"Success: {result['success']}")
        print(f"Latência: {result['latency']:.3f}s")
        print(f"Tokens (in/out): {result['input_tokens']}/{result['output_tokens']}")

        # Mostrar JSON parseado
        if result.get('json_parsed'):
            json_res = result['json_parsed']
            print(f"\n📊 JSON estruturado:")
            print(f"   Nível 1: {json_res.get('theme_1_level_1_code')} - {json_res.get('theme_1_level_1_label')}")
            print(f"   Nível 2: {json_res.get('theme_1_level_2_code')} - {json_res.get('theme_1_level_2_label')}")
            print(f"   Nível 3: {json_res.get('theme_1_level_3_code')} - {json_res.get('theme_1_level_3_label')}")
            print(f"   Mais específico: {json_res.get('most_specific_theme_code')} - {json_res.get('most_specific_theme_label')}")
        else:
            print(f"\n⚠️ JSON não foi parseado corretamente")
            print(f"Raw response (primeiros 300 chars):")
            print(result['raw_response'][:300])

        # Verificar se acertou
        correct = result['category'] == true_category
        print(f"\n{'✅ CORRETO' if correct else '❌ INCORRETO'}")

    # Stats finais
    print("\n" + "="*80)
    print("📊 ESTATÍSTICAS")
    print("="*80)
    stats = classifier.get_stats()
    print(f"Total de chamadas: {stats['total_calls']}")
    print(f"Latência média: {stats['avg_latency']:.3f}s")
    print(f"Input tokens: {stats['total_input_tokens']:,}")
    print(f"Output tokens: {stats['total_output_tokens']:,}")
    print(f"Custo estimado: ${stats['total_cost']:.4f}")
    print(f"Erros: {len(stats.get('errors', []))}")

    print("\n✅ Teste concluído!")


if __name__ == '__main__':
    main()
