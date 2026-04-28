"""
Avaliação rápida com 3 modelos para validar o pipeline.

Usa models_config_quick.yaml com apenas 3 modelos:
- Claude Haiku (baseline)
- Nova Pro
- Mistral Large 3
"""

import sys
from pathlib import Path

# Modificar para usar config rápido
BASE_DIR = Path(__file__).parent.parent
config_path = BASE_DIR / 'config' / 'models_config_quick.yaml'

# Importar e executar o pipeline principal
sys.path.insert(0, str(BASE_DIR.parent))
from embeddings.scripts.evaluate_llm_apis_json import *

# Sobrescrever config_path no main
original_main = main

def quick_main():
    """Main modificado para usar config rápido."""
    print("="*80)
    print("🚀 AVALIAÇÃO RÁPIDA - 3 MODELOS")
    print("="*80)

    # Paths
    test_path = BASE_DIR / 'data' / 'classification' / 'news_classification_test_annotated.csv'
    taxonomy_path = BASE_DIR / 'data' / 'classification' / 'arvore.yaml'
    output_dir = BASE_DIR / 'results'

    # Carregar configuração
    print("\n📋 Carregando configuração...")
    config = load_config(config_path)
    models = config['models']
    eval_config = config['evaluation']

    print(f"   ✓ {len(models)} modelos configurados (teste rápido)")
    print(f"   ✓ Região: {eval_config['region']}")
    print(f"   ✓ Batch size: {eval_config['batch_size']}")

    # Carregar test data
    print(f"\n📊 Carregando dataset de teste: {test_path}")
    test_df = load_test_data(test_path)
    print(f"   ✓ {len(test_df)} notícias carregadas")
    print(f"   ✓ Categorias únicas (nível 3): {test_df['category_code'].nunique()}")
    print(f"   ✓ Ground truth: category_code (anotado por Claude Haiku)")

    # Carregar taxonomia
    print(f"\n🗂️ Carregando taxonomia: {taxonomy_path}")
    taxonomy = TaxonomyParser(taxonomy_path)
    taxonomy_stats = taxonomy.get_stats()
    print(f"   ✓ Nível 1: {taxonomy_stats['total_level1']} categorias")
    print(f"   ✓ Nível 2: {taxonomy_stats['total_level2']} categorias")
    print(f"   ✓ Nível 3: {taxonomy_stats['total_level3']} categorias")

    # Avaliar cada modelo
    results = {}

    for model_config in models:
        model_id = model_config['model_id']
        model_name = model_config['name']
        provider = model_config['provider']
        pricing = model_config['pricing']

        try:
            # Criar classificador JSON
            classifier = BedrockClassifierJSON(
                model_id=model_id,
                model_name=model_name,
                provider=provider,
                region=eval_config['region'],
                taxonomy_path=str(taxonomy_path)
            )

            # Configurar pricing
            classifier.input_price_per_mtok = pricing['input_per_mtok']
            classifier.output_price_per_mtok = pricing['output_per_mtok']

            # Avaliar
            result = evaluate_model(
                classifier,
                test_df,
                batch_size=eval_config['batch_size']
            )

            results[model_name] = result

        except Exception as e:
            print(f"\n❌ Erro ao avaliar {model_name}: {e}")
            print("   Continuando com próximo modelo...\n")
            continue

    # Gerar relatórios
    if results:
        print("\n" + "="*80)
        print("📊 GERANDO RELATÓRIOS")
        print("="*80)
        generate_comparison_report(results, output_dir)

        # Ranking
        print("\n" + "="*80)
        print("🏆 RANKING DOS MODELOS (por Accuracy)")
        print("="*80)
        sorted_results = sorted(results.items(), key=lambda x: x[1]['accuracy'], reverse=True)
        for rank, (model_name, result) in enumerate(sorted_results, 1):
            stats = result['stats']
            print(f"\n{rank}. {model_name}")
            print(f"   Accuracy: {result['accuracy']:.2%}")
            print(f"   F1-score: {result['f1_macro']:.4f}")
            print(f"   Latência: {stats['avg_latency']:.3f}s")
            print(f"   Custo: ${stats.get('total_cost', 0):.4f}")

        print("\n" + "="*80)
        print("✅ AVALIAÇÃO RÁPIDA CONCLUÍDA!")
        print("="*80)
    else:
        print("\n❌ Nenhum resultado foi gerado. Verifique os erros acima.")


if __name__ == '__main__':
    quick_main()
