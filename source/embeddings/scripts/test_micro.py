#!/usr/bin/env python3
"""
Micro-teste: Valida pipeline com 2 modelos pequenos em 5 notícias
Objetivo: Verificar que tudo funciona antes da avaliação completa
"""

import sys
import os
import time
import pandas as pd
import yaml
from pathlib import Path

# Adicionar path do projeto
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from source.embeddings.classifiers.local_classifier import LocalClassifier

def load_sample_data(n_samples=5):
    """Carrega amostra pequena do dataset"""
    data_path = Path(__file__).parent.parent / "data" / "classification" / "news_classification_test_annotated.csv"
    df = pd.read_csv(data_path)

    # Pegar 5 notícias aleatórias (seed fixo para reproduzibilidade)
    sample = df.sample(n=n_samples, random_state=42)

    texts = sample['content'].tolist()
    ground_truth = sample['level_3_code'].tolist()

    return texts, ground_truth, sample

def calculate_accuracy(predictions, ground_truth):
    """Calcula accuracy simples"""
    correct = sum(1 for pred, gt in zip(predictions, ground_truth) if pred == gt)
    return correct / len(ground_truth) if ground_truth else 0.0

def main():
    print("=" * 80)
    print("🧪 MICRO-TESTE - Validação Rápida do Pipeline")
    print("=" * 80)
    print()

    # Configuração
    models = [
        {
            "name": "Gemma 2 2B",
            "model_id": "gemma2:2b-instruct-q4_K_M",
            "tier": "C (Small)"
        },
        {
            "name": "Llama 3.2 3B",
            "model_id": "llama3.2:3b-instruct-q4_K_M",
            "tier": "C (Small)"
        }
    ]

    # Carregar dados
    print("📊 Carregando 5 notícias de teste...")
    texts, ground_truth, sample_df = load_sample_data(n_samples=5)
    print(f"   ✅ {len(texts)} notícias carregadas")
    print()

    # Mostrar amostra
    print("📰 Amostra de notícias:")
    for i, row in sample_df.iterrows():
        title = row['title'][:60] + "..." if len(row['title']) > 60 else row['title']
        print(f"   {i+1}. {title}")
        print(f"      Ground truth: {row['level_3_code']} - {row['level_3_label']}")
    print()

    results = []

    # Testar cada modelo
    for model_config in models:
        print("=" * 80)
        print(f"🤖 Testando: {model_config['name']} ({model_config['tier']})")
        print("=" * 80)

        try:
            # Inicializar classificador
            print(f"   Inicializando {model_config['model_id']}...")
            classifier = LocalClassifier(
                model_id=model_config['model_id'],
                model_name=model_config['name'],
                ollama_host="http://localhost:11434",
                timeout=60
            )
            print(f"   ✅ Modelo inicializado")

            # Classificar
            predictions = []
            latencies = []
            errors = 0

            start_time = time.time()

            for i, text in enumerate(texts, 1):
                print(f"   [{i}/{len(texts)}] Classificando...", end=" ", flush=True)

                result = classifier.classify(text[:2000])  # Limite de 2000 chars

                if result.get('success'):
                    pred_code = result.get('category', '').split(' - ')[0] if ' - ' in result.get('category', '') else ''
                    predictions.append(pred_code)
                    latencies.append(result.get('latency', 0))
                    print(f"✅ {result.get('latency', 0):.2f}s - {result.get('category', 'N/A')[:50]}")
                else:
                    predictions.append('')
                    errors += 1
                    print(f"❌ Erro")

            total_time = time.time() - start_time

            # Calcular métricas
            accuracy = calculate_accuracy(predictions, ground_truth)
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            # Resultados
            print()
            print(f"   📊 Resultados:")
            print(f"      Accuracy: {accuracy*100:.1f}% ({sum(1 for p,g in zip(predictions, ground_truth) if p==g)}/{len(ground_truth)})")
            print(f"      Latência média: {avg_latency:.2f}s")
            print(f"      Tempo total: {total_time:.1f}s")
            print(f"      Throughput: {len(texts)/total_time:.2f} classificações/seg")
            print(f"      Erros: {errors}")

            # Estimativa para 200 notícias
            estimated_time_200 = (total_time / len(texts)) * 200
            print()
            print(f"   ⏱️  Estimativa para 200 notícias: {estimated_time_200/60:.1f} minutos")

            results.append({
                'model': model_config['name'],
                'accuracy': accuracy * 100,
                'avg_latency': avg_latency,
                'total_time': total_time,
                'errors': errors,
                'estimated_200': estimated_time_200
            })

        except Exception as e:
            print(f"   ❌ ERRO: {str(e)}")
            results.append({
                'model': model_config['name'],
                'accuracy': 0,
                'avg_latency': 0,
                'total_time': 0,
                'errors': len(texts),
                'estimated_200': 0
            })

        print()

    # Resumo final
    print("=" * 80)
    print("📊 RESUMO COMPARATIVO")
    print("=" * 80)
    print()

    print(f"{'Modelo':<20} {'Accuracy':<12} {'Lat.Média':<12} {'Est. 200 news':<15}")
    print("-" * 80)
    for r in results:
        print(f"{r['model']:<20} {r['accuracy']:>6.1f}%      {r['avg_latency']:>6.2f}s       {r['estimated_200']/60:>6.1f} min")

    print()
    print("=" * 80)
    print("✅ MICRO-TESTE CONCLUÍDO!")
    print("=" * 80)
    print()
    print("💡 Próximo passo: Aguardar downloads e executar avaliação completa (8 modelos × 200 notícias)")
    print()

if __name__ == "__main__":
    main()
