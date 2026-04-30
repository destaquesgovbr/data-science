"""
Avaliação de modelos open source locais via Ollama.

Avalia 8 modelos (Tier B: médios, Tier C: pequenos) nas 200 notícias do dataset.
Compara com resultados das APIs (Claude Haiku baseline).
"""

import sys
from pathlib import Path
import pandas as pd
import yaml
import time
from typing import Dict, List
import json

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.local_classifier import LocalClassifier
from embeddings.utils.taxonomy_parser import TaxonomyParser


def load_config() -> Dict:
    """Carrega configuração dos modelos."""
    config_path = BASE_DIR / "config" / "local_models_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def calculate_hierarchical_metrics(y_true: List[str], y_pred: List[str]) -> Dict:
    """
    Calcula métricas hierárquicas (L1, L2, L3).

    Args:
        y_true: Categorias ground truth (formato: "XX.XX.XX - Nome")
        y_pred: Categorias preditas (formato: "XX.XX.XX - Nome")

    Returns:
        Dict com accuracy por nível
    """
    l1_matches = 0
    l2_matches = 0
    l3_matches = 0
    total = len(y_true)

    for gt, pred in zip(y_true, y_pred):
        # Extrair códigos
        gt_code = gt.split(' - ')[0] if ' - ' in gt else gt
        pred_code = pred.split(' - ')[0] if ' - ' in pred else pred

        # Nível 1 (XX)
        gt_l1 = gt_code.split('.')[0] if '.' in gt_code else gt_code
        pred_l1 = pred_code.split('.')[0] if '.' in pred_code else pred_code

        # Nível 2 (XX.XX)
        gt_l2 = '.'.join(gt_code.split('.')[:2]) if '.' in gt_code else ''
        pred_l2 = '.'.join(pred_code.split('.')[:2]) if '.' in pred_code else ''

        # Nível 3 (XX.XX.XX)
        gt_l3 = gt_code
        pred_l3 = pred_code

        # Contar matches
        if gt_l1 == pred_l1:
            l1_matches += 1
        if gt_l2 == pred_l2 and gt_l2 != '':
            l2_matches += 1
        if gt_l3 == pred_l3:
            l3_matches += 1

    return {
        'L1_accuracy': (l1_matches / total * 100) if total > 0 else 0,
        'L2_accuracy': (l2_matches / total * 100) if total > 0 else 0,
        'L3_accuracy': (l3_matches / total * 100) if total > 0 else 0,
        'L1_correct': l1_matches,
        'L2_correct': l2_matches,
        'L3_correct': l3_matches,
        'total': total
    }


def evaluate_model(model_config: Dict, texts: List[str], ground_truth: List[str]) -> Dict:
    """
    Avalia um modelo no dataset completo.

    Args:
        model_config: Configuração do modelo (do YAML)
        texts: Lista de textos a classificar
        ground_truth: Categorias corretas

    Returns:
        Dict com métricas completas
    """
    model_name = model_config['name']
    model_id = model_config['model_id']

    print(f"\n{'='*80}")
    print(f"🤖 MODELO: {model_name}")
    print(f"{'='*80}")
    print(f"ID: {model_id}")
    print(f"Parâmetros: {model_config['parameters']:,}")
    print(f"Quantização: {model_config['quantization']}")
    print(f"VRAM esperada: {model_config['expected_vram_gb']}GB")
    print()

    # Inicializar classificador
    try:
        classifier = LocalClassifier(
            model_id=model_id,
            model_name=model_name,
            ollama_host="http://localhost:11434"
        )
    except Exception as e:
        print(f"❌ Erro ao inicializar modelo: {e}")
        return {
            'model_name': model_name,
            'status': 'failed_init',
            'error': str(e)
        }

    # Classificar todas as notícias
    print("📊 Classificando 200 notícias...")
    print()

    predictions = []
    start_time = time.time()

    for i, text in enumerate(texts):
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / (i + 1)
            remaining = avg_time * (len(texts) - i - 1)
            print(f"  Progress: {i+1}/{len(texts)} ({(i+1)/len(texts)*100:.1f}%) | "
                  f"Avg: {avg_time:.2f}s | "
                  f"ETA: {remaining/60:.1f}min")

        result = classifier.classify(text)
        predictions.append(result['category'])

    total_time = time.time() - start_time

    print()
    print(f"✅ Classificação concluída em {total_time/60:.1f} minutos")
    print()

    # Calcular métricas
    hierarchical_metrics = calculate_hierarchical_metrics(ground_truth, predictions)
    stats = classifier.get_stats()

    # Compilar resultados
    results = {
        'model_name': model_name,
        'model_id': model_id,
        'tier': model_config['tier'],
        'parameters': model_config['parameters'],
        'quantization': model_config['quantization'],

        # Accuracy hierárquica
        'L1_accuracy': hierarchical_metrics['L1_accuracy'],
        'L2_accuracy': hierarchical_metrics['L2_accuracy'],
        'L3_accuracy': hierarchical_metrics['L3_accuracy'],

        # Performance
        'avg_latency_sec': stats['avg_latency'],
        'total_time_sec': total_time,
        'throughput_per_sec': len(texts) / total_time,

        # Tokens (para estimar custo de API equivalente)
        'total_input_tokens': stats['total_input_tokens'],
        'total_output_tokens': stats['total_output_tokens'],
        'avg_input_tokens': stats['total_input_tokens'] / len(texts),
        'avg_output_tokens': stats['total_output_tokens'] / len(texts),

        # Erros
        'errors': len(classifier.errors),
        'error_rate_pct': len(classifier.errors) / len(texts) * 100,

        # Estimativas de custo (local vs API)
        'expected_vram_gb': model_config['expected_vram_gb'],

        'status': 'completed'
    }

    # Mostrar resumo
    print("=" * 80)
    print("📈 RESULTADOS")
    print("=" * 80)
    print()
    print("Concordância Hierárquica:")
    print(f"  Level 1: {results['L1_accuracy']:.1f}%")
    print(f"  Level 2: {results['L2_accuracy']:.1f}%")
    print(f"  Level 3: {results['L3_accuracy']:.1f}%")
    print()
    print("Performance:")
    print(f"  Latência média: {results['avg_latency_sec']:.2f}s")
    print(f"  Throughput: {results['throughput_per_sec']:.2f} classificações/seg")
    print(f"  Tempo total: {results['total_time_sec']/60:.1f} min")
    print()
    print("Recursos:")
    print(f"  Tokens médios (input): {results['avg_input_tokens']:.0f}")
    print(f"  Tokens médios (output): {results['avg_output_tokens']:.0f}")
    print(f"  Erros: {results['errors']}/200 ({results['error_rate_pct']:.1f}%)")
    print()

    return results


def run_evaluation():
    """Executa avaliação completa de todos os modelos locais."""
    print("=" * 80)
    print("🚀 AVALIAÇÃO DE MODELOS OPEN SOURCE LOCAIS")
    print("=" * 80)
    print()

    # Carregar configuração
    config = load_config()
    models = config['models']

    print(f"📋 {len(models)} modelos configurados:")
    for model in models:
        print(f"   - {model['name']} ({model['tier']}) - {model['parameters']:,} params")
    print()

    # Carregar dataset
    data_path = BASE_DIR / "data" / "classification" / "news_classification_test_annotated.csv"
    df = pd.read_csv(data_path)

    print(f"✅ Dataset carregado: {len(df)} notícias")
    print()

    # Preparar textos e ground truth
    texts = df['content'].tolist()
    ground_truth = [
        f"{row['level_3_code']} - {row['level_3_label']}"
        for _, row in df.iterrows()
    ]

    # Avaliar cada modelo
    all_results = []

    for i, model_config in enumerate(models):
        print(f"\n[{i+1}/{len(models)}] Avaliando {model_config['name']}...")

        result = evaluate_model(model_config, texts, ground_truth)
        all_results.append(result)

        # Pausa entre modelos (para descarregar GPU se necessário)
        if i < len(models) - 1:
            print("\n⏸️  Pausa de 5 segundos antes do próximo modelo...")
            time.sleep(5)

    # Salvar resultados
    print("\n" + "=" * 80)
    print("💾 SALVANDO RESULTADOS")
    print("=" * 80)
    print()

    results_dir = BASE_DIR / "results" / "local_models"
    results_dir.mkdir(parents=True, exist_ok=True)

    # CSV com resumo
    results_df = pd.DataFrame(all_results)
    results_df = results_df.sort_values('L3_accuracy', ascending=False)

    summary_path = results_dir / "comparison_summary.csv"
    results_df.to_csv(summary_path, index=False)
    print(f"✅ Resumo salvo: {summary_path}")

    # JSON com detalhes completos
    json_path = results_dir / "detailed_results.json"
    with open(json_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"✅ Detalhes salvos: {json_path}")

    # Mostrar ranking
    print("\n" + "=" * 80)
    print("🏆 RANKING FINAL")
    print("=" * 80)
    print()

    for i, row in results_df.iterrows():
        if row['status'] != 'completed':
            print(f"{i+1}. ❌ {row['model_name']} - FALHOU")
            continue

        print(f"{i+1}. {row['model_name']} ({row['tier']})")
        print(f"   L1: {row['L1_accuracy']:.1f}% | L2: {row['L2_accuracy']:.1f}% | L3: {row['L3_accuracy']:.1f}%")
        print(f"   Latência: {row['avg_latency_sec']:.2f}s | Erros: {row['errors']}/200")
        print()

    # Comparar com baseline API (Claude Haiku)
    print("=" * 80)
    print("📊 COMPARAÇÃO COM BASELINE API")
    print("=" * 80)
    print()
    print("Claude 3 Haiku (AWS Bedrock):")
    print("   L1: 80.5% | L2: 80.5% | L3: 80.5%")
    print("   Latência: 2.70s | Custo: $0.65/200 = $97/mês")
    print()

    best_local = results_df.iloc[0]
    if best_local['status'] == 'completed':
        print(f"Melhor modelo local: {best_local['model_name']}")
        print(f"   L1: {best_local['L1_accuracy']:.1f}% | L2: {best_local['L2_accuracy']:.1f}% | L3: {best_local['L3_accuracy']:.1f}%")
        print(f"   Latência: {best_local['avg_latency_sec']:.2f}s")
        print()
        print(f"Gap vs Haiku:")
        print(f"   L3: {80.5 - best_local['L3_accuracy']:.1f} pontos percentuais")
        print()

    print("=" * 80)
    print("✅ AVALIAÇÃO COMPLETA!")
    print("=" * 80)
    print()

    return all_results


if __name__ == '__main__':
    import sys

    # Check if Ollama is running
    import requests
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
    except Exception as e:
        print("❌ ERRO: Ollama não está rodando!")
        print(f"   {e}")
        print()
        print("Para iniciar o Ollama:")
        print("   1. Instalar: curl -fsSL https://ollama.com/install.sh | sh")
        print("   2. Iniciar: ollama serve")
        print()
        sys.exit(1)

    results = run_evaluation()
