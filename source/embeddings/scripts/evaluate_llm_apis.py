#!/usr/bin/env python3
"""
Avaliação comparativa de LLMs para classificação de notícias - Issue #3.

Testa 12 modelos via AWS Bedrock:
- Claude Sonnet 4.6, Claude Haiku 4.5
- DeepSeek V3.2, Mistral Large 3
- Amazon Nova Pro, Nova 2 Lite
- Qwen3 Next 80B, Llama 3 70B, Llama 3 8B
- Cohere Command R+, Ministral 3 8B, Gemma 3 27B

Métricas:
- Accuracy, F1-macro, F1-weighted
- Confusion matrix
- Latência (P50, P95, P99)
- Custo (input + output tokens)
"""

import pandas as pd
import numpy as np
import yaml
import json
import time
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

# Sklearn para métricas
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix
)

# Nossos classificadores
import sys
BASE_MODULE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_MODULE_DIR.parent))  # Adiciona 'source' ao path

from embeddings.classifiers.bedrock_classifier import BedrockClassifier


# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "models_config.yaml"

# Permitir override via argumento
import sys
if len(sys.argv) > 1:
    CONFIG_PATH = BASE_DIR / "config" / sys.argv[1]
TEST_DATA_PATH = BASE_DIR / "data" / "classification" / "news_classification_test.csv"
OUTPUT_DIR = BASE_DIR / "results" / "llm_evaluation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict:
    """Carrega configuração de modelos."""
    print("📋 Carregando configuração...")

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print(f"  ✅ {len(config['models'])} modelos configurados")
    print(f"  📂 Test file: {config['evaluation']['test_file']}")

    return config


def load_test_data() -> pd.DataFrame:
    """Carrega dataset de teste."""
    print(f"\n📂 Carregando test set...")

    df = pd.read_csv(TEST_DATA_PATH, encoding='utf-8')

    print(f"  ✅ {len(df)} notícias carregadas")
    print(f"  🏷️  {df['category'].nunique()} categorias")

    # Distribuição
    print(f"\n  📊 Distribuição:")
    for cat, count in df['category'].value_counts().items():
        print(f"    {cat}: {count}")

    return df


def evaluate_model(
    model_config: Dict,
    test_df: pd.DataFrame,
    prompt_strategy: str = 'chain-of-thought',
    batch_size: int = 10
) -> Dict:
    """
    Avalia um modelo no test set.

    Args:
        model_config: Configuração do modelo (do YAML)
        test_df: DataFrame com notícias de teste
        prompt_strategy: Estratégia de prompt
        batch_size: Tamanho do batch para feedback visual

    Returns:
        Dict com resultados completos
    """

    model_name = model_config['name']
    model_id = model_config['model_id']
    provider = model_config['provider']

    print(f"\n{'='*80}")
    print(f"🤖 Avaliando: {model_name}")
    print(f"   ID: {model_id}")
    print(f"   Provider: {provider}")
    print(f"   Estratégia: {prompt_strategy}")
    print(f"{'='*80}")

    # Criar classificador (taxonomia carregada automaticamente)
    classifier = BedrockClassifier(
        model_id=model_id,
        model_name=model_name,
        provider=provider,
        region='us-east-1'
    )

    # Pegar categorias da taxonomia
    categories = [cat['level3'] for cat in classifier.taxonomy.flat_categories]

    # Classificar todas as notícias
    predictions = []
    ground_truth = []
    latencies = []
    all_results = []

    total = len(test_df)

    for idx, row in test_df.iterrows():
        # Feedback visual a cada batch
        if (idx + 1) % batch_size == 0:
            print(f"  ⏳ Progresso: {idx + 1}/{total} ({(idx+1)/total*100:.1f}%)")

        text = row['content']
        true_category = row['category']

        # Classificar
        result = classifier.classify(text, prompt_strategy=prompt_strategy)

        predictions.append(result['category'])
        ground_truth.append(true_category)
        latencies.append(result['latency'])
        all_results.append({
            'id': row['id'],
            'true_category': true_category,
            'predicted_category': result['category'],
            'latency': result['latency'],
            'input_tokens': result['input_tokens'],
            'output_tokens': result['output_tokens'],
            'success': result['success'],
        })

    print(f"  ✅ Classificação completa: {total} notícias")

    # Calcular métricas (com tratamento de erro)
    try:
        accuracy = accuracy_score(ground_truth, predictions)

        # F1 scores - usar apenas labels que aparecem nos dados
        unique_labels = sorted(set(ground_truth + predictions))
        valid_categories = [c for c in categories if c in unique_labels]

        f1_macro = f1_score(ground_truth, predictions, average='macro', zero_division=0, labels=valid_categories)
        f1_weighted = f1_score(ground_truth, predictions, average='weighted', zero_division=0, labels=valid_categories)

        # Confusion matrix
        conf_matrix = confusion_matrix(
            ground_truth,
            predictions,
            labels=valid_categories
        )

        # Classification report (por categoria)
        class_report = classification_report(
            ground_truth,
            predictions,
            labels=valid_categories,
            output_dict=True,
            zero_division=0
        )
    except Exception as e:
        print(f"  ⚠️  Erro ao calcular métricas: {e}")
        print(f"  ℹ️  Usando métricas padrão com zero_division")
        accuracy = 0.0
        f1_macro = 0.0
        f1_weighted = 0.0
        conf_matrix = [[0]]
        class_report = {}

    # Latência (percentis)
    latencies_arr = np.array(latencies)
    latency_p50 = np.percentile(latencies_arr, 50)
    latency_p95 = np.percentile(latencies_arr, 95)
    latency_p99 = np.percentile(latencies_arr, 99)
    latency_mean = np.mean(latencies_arr)

    # Custos
    stats = classifier.get_stats()
    input_tokens = stats['total_input_tokens']
    output_tokens = stats['total_output_tokens']

    input_cost = (input_tokens / 1_000_000) * model_config['pricing']['input_per_mtok']
    output_cost = (output_tokens / 1_000_000) * model_config['pricing']['output_per_mtok']
    total_cost = input_cost + output_cost

    # Resumo
    print(f"\n  📊 Resultados:")
    print(f"    Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"    F1-macro: {f1_macro:.4f}")
    print(f"    F1-weighted: {f1_weighted:.4f}")
    print(f"\n  ⏱️  Latência:")
    print(f"    Média: {latency_mean:.3f}s")
    print(f"    P50: {latency_p50:.3f}s")
    print(f"    P95: {latency_p95:.3f}s")
    print(f"    P99: {latency_p99:.3f}s")
    print(f"\n  💰 Custo:")
    print(f"    Input: {input_tokens:,} tokens (${input_cost:.4f})")
    print(f"    Output: {output_tokens:,} tokens (${output_cost:.4f})")
    print(f"    Total: ${total_cost:.4f}")
    print(f"\n  ⚠️  Erros: {stats['total_errors']}")

    # Compilar resultado
    result = {
        'model_name': model_name,
        'model_id': model_id,
        'provider': provider,
        'tier': model_config['tier'],

        # Métricas
        'accuracy': accuracy,
        'f1_macro': f1_macro,
        'f1_weighted': f1_weighted,

        # Latência
        'latency_mean': latency_mean,
        'latency_p50': latency_p50,
        'latency_p95': latency_p95,
        'latency_p99': latency_p99,

        # Tokens e custo
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': input_tokens + output_tokens,
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,

        # Detalhes
        'total_predictions': len(predictions),
        'total_errors': stats['total_errors'],
        'confusion_matrix': conf_matrix.tolist(),
        'classification_report': class_report,
        'predictions': all_results,
    }

    return result


def generate_comparison_report(all_results: List[Dict]):
    """
    Gera relatório comparativo entre todos os modelos.

    Outputs:
    - comparison_summary.csv (tabela comparativa)
    - comparison_full.json (resultados completos)
    - best_models.txt (ranking por métrica)
    """

    print(f"\n{'='*80}")
    print("📊 GERANDO RELATÓRIO COMPARATIVO")
    print(f"{'='*80}")

    # 1. CSV com métricas principais
    summary_data = []

    for result in all_results:
        summary_data.append({
            'Model': result['model_name'],
            'Tier': result['tier'],
            'Accuracy': result['accuracy'],
            'F1-Macro': result['f1_macro'],
            'F1-Weighted': result['f1_weighted'],
            'Latency P50 (s)': result['latency_p50'],
            'Latency P95 (s)': result['latency_p95'],
            'Total Cost ($)': result['total_cost'],
            'Input Tokens': result['input_tokens'],
            'Output Tokens': result['output_tokens'],
            'Errors': result['total_errors'],
        })

    summary_df = pd.DataFrame(summary_data)

    # Ordenar por accuracy
    summary_df = summary_df.sort_values('Accuracy', ascending=False)

    csv_path = OUTPUT_DIR / "comparison_summary.csv"
    summary_df.to_csv(csv_path, index=False, encoding='utf-8')
    print(f"\n✅ CSV salvo: {csv_path}")

    # 2. JSON completo
    json_path = OUTPUT_DIR / "comparison_full.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'evaluation_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_models': len(all_results),
            'categories': categories,
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON salvo: {json_path}")

    # 3. Rankings
    rankings_path = OUTPUT_DIR / "model_rankings.txt"
    with open(rankings_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RANKINGS POR MÉTRICA - Issue #3\n")
        f.write("="*80 + "\n\n")

        # Ranking por accuracy
        f.write("🏆 TOP 5 - ACCURACY\n")
        f.write("-" * 80 + "\n")
        sorted_by_acc = sorted(all_results, key=lambda x: x['accuracy'], reverse=True)
        for i, r in enumerate(sorted_by_acc[:5], 1):
            f.write(f"{i}. {r['model_name']}: {r['accuracy']:.4f} ({r['accuracy']*100:.2f}%)\n")

        f.write("\n🏆 TOP 5 - F1-MACRO\n")
        f.write("-" * 80 + "\n")
        sorted_by_f1 = sorted(all_results, key=lambda x: x['f1_macro'], reverse=True)
        for i, r in enumerate(sorted_by_f1[:5], 1):
            f.write(f"{i}. {r['model_name']}: {r['f1_macro']:.4f}\n")

        f.write("\n⚡ TOP 5 - LATÊNCIA (P50)\n")
        f.write("-" * 80 + "\n")
        sorted_by_lat = sorted(all_results, key=lambda x: x['latency_p50'])
        for i, r in enumerate(sorted_by_lat[:5], 1):
            f.write(f"{i}. {r['model_name']}: {r['latency_p50']:.3f}s\n")

        f.write("\n💰 TOP 5 - CUSTO (menor)\n")
        f.write("-" * 80 + "\n")
        sorted_by_cost = sorted(all_results, key=lambda x: x['total_cost'])
        for i, r in enumerate(sorted_by_cost[:5], 1):
            f.write(f"{i}. {r['model_name']}: ${r['total_cost']:.4f}\n")

        f.write("\n💎 CUSTO-BENEFÍCIO (Accuracy / Cost)\n")
        f.write("-" * 80 + "\n")
        cost_benefit = [(r['model_name'], r['accuracy'] / r['total_cost'] if r['total_cost'] > 0 else 0)
                        for r in all_results]
        cost_benefit.sort(key=lambda x: x[1], reverse=True)
        for i, (name, cb) in enumerate(cost_benefit[:5], 1):
            f.write(f"{i}. {name}: {cb:.2f} (acc/dólar)\n")

    print(f"✅ Rankings salvos: {rankings_path}")

    # 4. Estatísticas gerais
    print(f"\n{'='*80}")
    print("📊 ESTATÍSTICAS GERAIS")
    print(f"{'='*80}")

    accuracies = [r['accuracy'] for r in all_results]
    costs = [r['total_cost'] for r in all_results]
    latencies = [r['latency_p50'] for r in all_results]

    print(f"\nAccuracy:")
    print(f"  Melhor: {max(accuracies):.4f} ({max(accuracies)*100:.2f}%)")
    print(f"  Pior: {min(accuracies):.4f} ({min(accuracies)*100:.2f}%)")
    print(f"  Média: {np.mean(accuracies):.4f} ({np.mean(accuracies)*100:.2f}%)")

    print(f"\nCusto (200 notícias):")
    print(f"  Mais caro: ${max(costs):.4f}")
    print(f"  Mais barato: ${min(costs):.4f}")
    print(f"  Média: ${np.mean(costs):.4f}")
    print(f"  Total (todos modelos): ${sum(costs):.2f}")

    print(f"\nLatência P50:")
    print(f"  Mais rápido: {min(latencies):.3f}s")
    print(f"  Mais lento: {max(latencies):.3f}s")
    print(f"  Média: {np.mean(latencies):.3f}s")

    # Melhor modelo geral (accuracy)
    best_model = sorted_by_acc[0]
    print(f"\n🏆 MELHOR MODELO (Accuracy):")
    print(f"  {best_model['model_name']}")
    print(f"  Accuracy: {best_model['accuracy']:.4f} ({best_model['accuracy']*100:.2f}%)")
    print(f"  F1-Macro: {best_model['f1_macro']:.4f}")
    print(f"  Custo: ${best_model['total_cost']:.4f}")
    print(f"  Latência P50: {best_model['latency_p50']:.3f}s")


def main():
    """Pipeline principal."""

    print("="*80)
    print("AVALIAÇÃO COMPARATIVA DE LLMs - ISSUE #3")
    print("="*80)

    start_time = time.time()

    # 1. Carregar configuração
    config = load_config()

    # 2. Carregar test data
    test_df = load_test_data()

    prompt_strategy = config['evaluation'].get('prompt_strategy', 'chain-of-thought')
    batch_size = config['evaluation'].get('batch_size', 10)

    # 3. Avaliar cada modelo
    all_results = []

    for i, model_config in enumerate(config['models'], 1):
        print(f"\n{'='*80}")
        print(f"MODELO {i}/{len(config['models'])}")
        print(f"{'='*80}")

        try:
            result = evaluate_model(
                model_config=model_config,
                test_df=test_df,
                prompt_strategy=prompt_strategy,
                batch_size=batch_size
            )
            all_results.append(result)

        except Exception as e:
            print(f"\n❌ ERRO ao avaliar {model_config['name']}: {e}")
            print("   Pulando este modelo...")

            # Salvar resultados parciais mesmo com erro
            if all_results and i == len(config['models']):
                print("\n💾 Salvando resultados dos modelos que funcionaram...")
                generate_comparison_report(all_results)

    # 4. Gerar relatório comparativo
    if all_results:
        generate_comparison_report(all_results)

    total_time = time.time() - start_time

    print(f"\n{'='*80}")
    print("✅ AVALIAÇÃO COMPLETA!")
    print(f"{'='*80}")
    print(f"\n⏱️  Tempo total: {total_time/60:.2f} minutos")
    print(f"📁 Resultados em: {OUTPUT_DIR}")
    print(f"\nArquivos gerados:")
    print(f"  - comparison_summary.csv (tabela comparativa)")
    print(f"  - comparison_full.json (resultados completos)")
    print(f"  - model_rankings.txt (rankings por métrica)")


if __name__ == "__main__":
    main()
