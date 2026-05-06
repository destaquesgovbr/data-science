#!/usr/bin/env python3
"""
Teste médio: 3 modelos × 50 notícias com classificação hierárquica.
Validação antes da avaliação completa.
"""

import sys
import time
import pandas as pd
from pathlib import Path
from datetime import datetime

# Adicionar path do projeto
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from source.embeddings.classifiers.local_classifier import LocalClassifier
from source.embeddings.prompts.classification_prompts_hierarchical import classify_hierarchical
from source.embeddings.utils.taxonomy_parser import TaxonomyParser


def calculate_hierarchical_accuracy(predictions, ground_truth):
    """
    Calcula accuracy em cada nível hierárquico.

    Args:
        predictions: Lista de códigos preditos (ex: ['01.02.03', '02.04.01', ...])
        ground_truth: Lista de códigos corretos (ex: ['01.02.03', '02.04.01', ...])

    Returns:
        Dict com l1_accuracy, l2_accuracy, l3_accuracy
    """
    if not predictions or not ground_truth or len(predictions) != len(ground_truth):
        return {'l1': 0.0, 'l2': 0.0, 'l3': 0.0}

    correct_l1 = 0
    correct_l2 = 0
    correct_l3 = 0

    for pred, gt in zip(predictions, ground_truth):
        if not pred or not gt:
            continue

        pred_parts = pred.split('.')
        gt_parts = gt.split('.')

        # Nível 1: comparar primeiro dígito
        if len(pred_parts) >= 1 and len(gt_parts) >= 1:
            if pred_parts[0] == gt_parts[0]:
                correct_l1 += 1

                # Nível 2: comparar primeiro e segundo
                if len(pred_parts) >= 2 and len(gt_parts) >= 2:
                    if pred_parts[1] == gt_parts[1]:
                        correct_l2 += 1

                        # Nível 3: comparar completo
                        if len(pred_parts) >= 3 and len(gt_parts) >= 3:
                            if pred_parts[2] == gt_parts[2]:
                                correct_l3 += 1

    total = len(predictions)
    return {
        'l1': correct_l1 / total if total > 0 else 0.0,
        'l2': correct_l2 / total if total > 0 else 0.0,
        'l3': correct_l3 / total if total > 0 else 0.0
    }


def main():
    print("=" * 80)
    print("🧪 TESTE MÉDIO - Avaliação Hierárquica v2 (Parsing Robusto)")
    print("=" * 80)
    print()
    print("📊 Configuração:")
    print("   - 5 modelos (2B, 8B Q4, 8B Q6, 14B, 32B)")
    print("   - 50 notícias (amostra representativa)")
    print("   - Classificação hierárquica (3 etapas)")
    print("   - Parsing robusto com regex (v2)")
    print("   - Testando impacto de quantização (Q4 vs Q6)")
    print("   - Tempo estimado: 12-18 minutos com GPU L4")
    print()

    # Modelos a testar
    models = [
        {
            "name": "Gemma 2 2B",
            "model_id": "gemma2:2b-instruct-q4_K_M",
            "tier": "C (Small)",
            "params": "2B",
            "quant": "Q4_K_M"
        },
        {
            "name": "Llama 3.1 8B Q4",
            "model_id": "llama3.1:8b-instruct-q4_K_M",
            "tier": "B (Medium)",
            "params": "8B",
            "quant": "Q4_K_M"
        },
        {
            "name": "Llama 3.1 8B Q6",
            "model_id": "llama3.1:8b-instruct-q6_k",
            "tier": "B (Medium)",
            "params": "8B",
            "quant": "Q6_K"
        },
        {
            "name": "Qwen 2.5 14B",
            "model_id": "qwen2.5:14b-instruct-q4_K_M",
            "tier": "B (Large)",
            "params": "14B",
            "quant": "Q4_K_M"
        },
        {
            "name": "Qwen 2.5 32B",
            "model_id": "qwen2.5:32b-instruct-q4_K_M",
            "tier": "A (XLarge)",
            "params": "32B",
            "quant": "Q4_K_M"
        }
    ]

    # Carregar taxonomia
    taxonomy_path = Path(__file__).parent.parent / "data" / "classification" / "arvore.yaml"
    print(f"📚 Carregando taxonomia...")
    taxonomy = TaxonomyParser(str(taxonomy_path))
    print(f"   ✅ {len(taxonomy.flat_categories)} categorias carregadas")
    print()

    # Carregar dataset
    data_path = Path(__file__).parent.parent / "data" / "classification" / "news_classification_test_annotated.csv"
    print(f"📊 Carregando dataset...")
    df = pd.read_csv(data_path)

    # Pegar 50 notícias (seed fixo para reproduzibilidade)
    sample_df = df.sample(n=50, random_state=42)
    texts = sample_df['content'].tolist()
    ground_truth = sample_df['level_3_code'].tolist()

    print(f"   ✅ {len(texts)} notícias carregadas")
    print()

    # Resultados
    all_results = []

    # Avaliar cada modelo
    for model_config in models:
        print("=" * 80)
        print(f"🤖 Testando: {model_config['name']} ({model_config['params']})")
        print("=" * 80)
        print()

        try:
            # Inicializar classificador
            print(f"   Inicializando {model_config['model_id']}...")
            start_init = time.time()

            classifier = LocalClassifier(
                model_id=model_config['model_id'],
                model_name=model_config['name'],
                ollama_host="http://localhost:11434",
                timeout=300  # 5 min por etapa (foco em capacidade, não performance)
            )

            init_time = time.time() - start_init
            print(f"   ✅ Modelo inicializado ({init_time:.1f}s)")
            print()

            # Classificar
            predictions = []
            latencies = []
            errors = 0

            total_start = time.time()

            for i, text in enumerate(texts, 1):
                print(f"   [{i:2}/{len(texts)}] Classificando...", end=" ", flush=True)

                result = classify_hierarchical(text, taxonomy, classifier)

                if result['success']:
                    predictions.append(result['level3_code'])
                    latencies.append(result['latency_total'])
                    print(f"✅ {result['latency_total']:5.1f}s - {result['level3_code']}")
                else:
                    predictions.append('')
                    errors += 1
                    print(f"❌ Erro: {result.get('error', 'Unknown')[:40]}")

                # Progress a cada 10
                if i % 10 == 0:
                    elapsed = time.time() - total_start
                    avg_per_item = elapsed / i
                    remaining = (len(texts) - i) * avg_per_item
                    print(f"      [Progresso: {i}/{len(texts)} | Tempo: {elapsed/60:.1f}min | Restante: ~{remaining/60:.1f}min]")

            total_time = time.time() - total_start

            # Calcular métricas
            accuracy = calculate_hierarchical_accuracy(predictions, ground_truth)
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            throughput = len(texts) / total_time if total_time > 0 else 0

            # Estimativa para 200 notícias
            estimated_200 = (total_time / len(texts)) * 200

            print()
            print(f"   📊 Resultados:")
            print(f"      Accuracy L1: {accuracy['l1']*100:5.1f}%")
            print(f"      Accuracy L2: {accuracy['l2']*100:5.1f}%")
            print(f"      Accuracy L3: {accuracy['l3']*100:5.1f}%")
            print(f"      Latência média: {avg_latency:6.2f}s")
            print(f"      Tempo total: {total_time/60:6.1f} min")
            print(f"      Throughput: {throughput:6.3f} classificações/seg")
            print(f"      Erros: {errors}/{len(texts)}")
            print()
            print(f"   ⏱️  Estimativa para 200 notícias: {estimated_200/60:.1f} minutos")
            print()

            all_results.append({
                'model': model_config['name'],
                'model_id': model_config['model_id'],
                'tier': model_config['tier'],
                'params': model_config['params'],
                'quant': model_config.get('quant', 'Q4_K_M'),
                'accuracy_l1': accuracy['l1'] * 100,
                'accuracy_l2': accuracy['l2'] * 100,
                'accuracy_l3': accuracy['l3'] * 100,
                'avg_latency': avg_latency,
                'total_time_min': total_time / 60,
                'throughput': throughput,
                'errors': errors,
                'estimated_200_min': estimated_200 / 60
            })

        except Exception as e:
            print(f"   ❌ ERRO FATAL: {str(e)}")
            all_results.append({
                'model': model_config['name'],
                'model_id': model_config['model_id'],
                'tier': model_config['tier'],
                'params': model_config['params'],
                'quant': model_config.get('quant', 'Q4_K_M'),
                'accuracy_l1': 0,
                'accuracy_l2': 0,
                'accuracy_l3': 0,
                'avg_latency': 0,
                'total_time_min': 0,
                'throughput': 0,
                'errors': len(texts),
                'estimated_200_min': 0
            })

        print()

    # Resumo comparativo
    print("=" * 80)
    print("📊 RESUMO COMPARATIVO - 50 Notícias")
    print("=" * 80)
    print()

    results_df = pd.DataFrame(all_results)

    print(f"{'Modelo':<20} {'Acc L1':<8} {'Acc L2':<8} {'Acc L3':<8} {'Lat.':<8} {'Est.200':<10}")
    print("-" * 80)
    for _, row in results_df.iterrows():
        print(f"{row['model']:<20} {row['accuracy_l1']:>6.1f}%  {row['accuracy_l2']:>6.1f}%  "
              f"{row['accuracy_l3']:>6.1f}%  {row['avg_latency']:>6.1f}s  {row['estimated_200_min']:>6.1f} min")

    print()
    print("=" * 80)
    print("💡 ANÁLISE")
    print("=" * 80)
    print()

    # Melhor modelo por métrica
    best_l3 = results_df.loc[results_df['accuracy_l3'].idxmax()]
    fastest = results_df.loc[results_df['avg_latency'].idxmin()]

    print(f"🏆 Melhor Accuracy L3: {best_l3['model']} ({best_l3['accuracy_l3']:.1f}%)")
    print(f"⚡ Mais Rápido: {fastest['model']} ({fastest['avg_latency']:.1f}s)")
    print()

    # Estimativa para avaliação completa
    total_estimated = results_df['estimated_200_min'].sum()
    print(f"⏱️  Tempo estimado para avaliação completa (7 modelos × 200 notícias):")
    print(f"   - Com estes 3 modelos: {results_df['estimated_200_min'].sum():.1f} min")
    print(f"   - Extrapolando para 7 modelos: ~{(total_estimated / 3) * 7:.0f} min (~{((total_estimated / 3) * 7)/60:.1f}h)")
    print()

    # Salvar resultados
    output_dir = Path(__file__).parent.parent / "results" / "hierarchical_medium"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"medium_test_{timestamp}.csv"
    results_df.to_csv(csv_path, index=False)

    print(f"💾 Resultados salvos em: {csv_path}")
    print()
    print("=" * 80)
    print("✅ TESTE MÉDIO CONCLUÍDO!")
    print("=" * 80)
    print()
    print("🎯 Próximo passo: Se os resultados forem satisfatórios (>50% L3),")
    print("   rodar avaliação completa com 7-8 modelos em 200 notícias.")
    print()


if __name__ == "__main__":
    main()
