"""
Avaliação de modelos LLM usando formato JSON.

Baseado na implementação working de news-enrichment.
Usa prompts que retornam JSON estruturado com campos separados
para cada nível da hierarquia.

Usage:
    python evaluate_llm_apis_json.py

Outputs:
    - results/comparison_summary_json.csv
    - results/detailed_predictions_json.csv
    - results/classification_report_json.txt
"""

import sys
from pathlib import Path
import pandas as pd
import yaml
from tqdm import tqdm
from datetime import datetime

# Adicionar path para imports
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.bedrock_classifier_json import BedrockClassifierJSON
from embeddings.utils.taxonomy_parser import TaxonomyParser
from sklearn.metrics import accuracy_score, f1_score, classification_report


def load_config(config_path: Path) -> dict:
    """Carrega configuração de models_config.yaml."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_test_data(test_path: Path) -> pd.DataFrame:
    """Carrega dataset de teste."""
    return pd.read_csv(test_path)


def evaluate_model(
    classifier: BedrockClassifierJSON,
    test_df: pd.DataFrame,
    batch_size: int = 10
) -> dict:
    """
    Avalia um modelo no dataset de teste.

    Args:
        classifier: Instância do classificador
        test_df: DataFrame com colunas 'text' e 'category'
        batch_size: Tamanho do batch para feedback visual

    Returns:
        Dict com predictions, ground_truth e metadata
    """
    predictions = []
    ground_truth = []
    raw_responses = []
    json_results = []

    total = len(test_df)
    print(f"\n{'='*80}")
    print(f"📊 Avaliando: {classifier.model_name}")
    print(f"{'='*80}")

    for idx, row in tqdm(test_df.iterrows(), total=total, desc=f"{classifier.model_name}"):
        # Combinar title e content como faz o news-enrichment
        text = f"{row['title']}\n\n{row['content']}"
        # Usar category_code anotado como ground truth
        true_category = row['category_code']

        # Classificar
        result = classifier.classify(text, prompt_strategy='json')

        predictions.append(result['category'])
        ground_truth.append(true_category)
        raw_responses.append(result['raw_response'])
        json_results.append(result.get('json_parsed'))

        # Feedback visual a cada batch
        if (idx + 1) % batch_size == 0:
            current_accuracy = accuracy_score(
                ground_truth[:idx+1],
                predictions[:idx+1]
            )
            print(f"  Progresso: {idx+1}/{total} | Accuracy parcial: {current_accuracy:.2%}")

    # Calcular métricas finais
    accuracy = accuracy_score(ground_truth, predictions)

    # F1-score com zero_division para lidar com categorias ausentes
    try:
        # Pegar apenas categorias que aparecem nos dados
        unique_labels = sorted(set(ground_truth + predictions))
        f1_macro = f1_score(
            ground_truth,
            predictions,
            average='macro',
            zero_division=0,
            labels=unique_labels
        )
    except Exception as e:
        print(f"  ⚠️ Aviso ao calcular F1: {e}")
        f1_macro = 0.0

    # Stats
    stats = classifier.get_stats()

    print(f"\n✅ Concluído!")
    print(f"   Accuracy: {accuracy:.2%}")
    print(f"   F1-score (macro): {f1_macro:.4f}")
    print(f"   Latência média: {stats['avg_latency']:.3f}s")
    print(f"   Custo total: ${stats['total_cost']:.4f}")

    return {
        'predictions': predictions,
        'ground_truth': ground_truth,
        'raw_responses': raw_responses,
        'json_results': json_results,
        'accuracy': accuracy,
        'f1_macro': f1_macro,
        'stats': stats
    }


def generate_comparison_report(results: dict, output_dir: Path):
    """
    Gera relatórios de comparação entre modelos.

    Args:
        results: Dict com resultados de todos os modelos
        output_dir: Diretório para salvar resultados
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Comparison Summary CSV
    summary_rows = []
    for model_name, result in results.items():
        stats = result['stats']
        summary_rows.append({
            'model': model_name,
            'accuracy': result['accuracy'],
            'f1_macro': result['f1_macro'],
            'avg_latency_s': stats['avg_latency'],
            'total_calls': stats['total_calls'],
            'total_input_tokens': stats['total_input_tokens'],
            'total_output_tokens': stats['total_output_tokens'],
            'total_cost_usd': stats['total_cost'],
            'errors': len(stats.get('errors', []))
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values('accuracy', ascending=False)

    summary_path = output_dir / 'comparison_summary_json.csv'
    summary_df.to_csv(summary_path, index=False)
    print(f"\n✅ Comparison summary salvo em: {summary_path}")

    # 2. Detailed Predictions CSV
    detailed_rows = []
    for model_name, result in results.items():
        for idx, (pred, truth, raw, json_res) in enumerate(zip(
            result['predictions'],
            result['ground_truth'],
            result['raw_responses'],
            result['json_results']
        )):
            detailed_rows.append({
                'model': model_name,
                'index': idx,
                'predicted': pred,
                'ground_truth': truth,
                'correct': pred == truth,
                'raw_response': raw[:200],  # Truncar para não ficar muito grande
                'json_level_1': json_res.get('theme_1_level_1_code') if json_res else None,
                'json_level_2': json_res.get('theme_1_level_2_code') if json_res else None,
                'json_level_3': json_res.get('theme_1_level_3_code') if json_res else None,
            })

    detailed_df = pd.DataFrame(detailed_rows)
    detailed_path = output_dir / 'detailed_predictions_json.csv'
    detailed_df.to_csv(detailed_path, index=False)
    print(f"✅ Detailed predictions salvo em: {detailed_path}")

    # 3. Classification Report TXT
    report_path = output_dir / 'classification_report_json.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RELATÓRIO DE AVALIAÇÃO - FORMATO JSON\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

        for model_name, result in results.items():
            f.write(f"\n{'='*80}\n")
            f.write(f"MODELO: {model_name}\n")
            f.write(f"{'='*80}\n\n")

            # Métricas gerais
            f.write(f"Accuracy: {result['accuracy']:.4f}\n")
            f.write(f"F1-score (macro): {result['f1_macro']:.4f}\n\n")

            # Stats
            stats = result['stats']
            f.write(f"Latência média: {stats['avg_latency']:.3f}s\n")
            f.write(f"Total de chamadas: {stats['total_calls']}\n")
            f.write(f"Input tokens: {stats['total_input_tokens']:,}\n")
            f.write(f"Output tokens: {stats['total_output_tokens']:,}\n")
            f.write(f"Custo total: ${stats['total_cost']:.4f}\n")
            f.write(f"Erros: {len(stats.get('errors', []))}\n\n")

            # Classification report sklearn
            try:
                unique_labels = sorted(set(result['ground_truth'] + result['predictions']))
                report = classification_report(
                    result['ground_truth'],
                    result['predictions'],
                    labels=unique_labels,
                    zero_division=0
                )
                f.write("Classification Report (sklearn):\n")
                f.write(report)
                f.write("\n")
            except Exception as e:
                f.write(f"⚠️ Erro ao gerar classification report: {e}\n\n")

    print(f"✅ Classification report salvo em: {report_path}")


def main():
    """Pipeline principal de avaliação."""
    print("="*80)
    print("🚀 AVALIAÇÃO DE MODELOS LLM - FORMATO JSON")
    print("="*80)

    # Paths
    config_path = BASE_DIR / 'config' / 'models_config.yaml'
    test_path = BASE_DIR / 'data' / 'classification' / 'news_classification_test_annotated.csv'
    taxonomy_path = BASE_DIR / 'data' / 'classification' / 'arvore.yaml'
    output_dir = BASE_DIR / 'results'

    # Carregar configuração
    print("\n📋 Carregando configuração...")
    config = load_config(config_path)
    models = config['models']
    eval_config = config['evaluation']

    print(f"   ✓ {len(models)} modelos configurados")
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

        # Top 3 modelos
        print("\n" + "="*80)
        print("🏆 TOP 3 MODELOS (por Accuracy)")
        print("="*80)
        sorted_results = sorted(results.items(), key=lambda x: x[1]['accuracy'], reverse=True)
        for rank, (model_name, result) in enumerate(sorted_results[:3], 1):
            stats = result['stats']
            print(f"\n{rank}. {model_name}")
            print(f"   Accuracy: {result['accuracy']:.2%}")
            print(f"   F1-score: {result['f1_macro']:.4f}")
            print(f"   Latência: {stats['avg_latency']:.3f}s")
            print(f"   Custo: ${stats['total_cost']:.4f}")

        print("\n" + "="*80)
        print("✅ AVALIAÇÃO CONCLUÍDA!")
        print("="*80)
    else:
        print("\n❌ Nenhum resultado foi gerado. Verifique os erros acima.")


if __name__ == '__main__':
    main()
