#!/usr/bin/env python3
"""
Teste específico: Qwen 32B com classificação DIRETA.
Hipótese: Modelo grande tem contexto para 500 categorias de uma vez.
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
from source.embeddings.utils.taxonomy_parser import TaxonomyParser


def calculate_hierarchical_accuracy(predictions, ground_truth):
    """Calcula accuracy em cada nível hierárquico."""
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

        if len(pred_parts) >= 1 and len(gt_parts) >= 1:
            if pred_parts[0] == gt_parts[0]:
                correct_l1 += 1

                if len(pred_parts) >= 2 and len(gt_parts) >= 2:
                    if pred_parts[1] == gt_parts[1]:
                        correct_l2 += 1

                        if len(pred_parts) >= 3 and len(gt_parts) >= 3:
                            if pred_parts[2] == gt_parts[2]:
                                correct_l3 += 1

    total = len(predictions)
    return {
        'l1': correct_l1 / total if total > 0 else 0.0,
        'l2': correct_l2 / total if total > 0 else 0.0,
        'l3': correct_l3 / total if total > 0 else 0.0
    }


def extract_code_from_category(category: str) -> str:
    """Extrai código da categoria retornada."""
    if not category:
        return ''
    parts = category.split(' - ')
    if len(parts) > 0:
        return parts[0].strip()
    return category.strip()


def main():
    print("=" * 80)
    print("🧪 TESTE QWEN 32B - Classificação DIRETA vs HIERÁRQUICA")
    print("=" * 80)
    print()
    print("📊 Hipótese:")
    print("   Qwen 32B teve excelente L1/L2 (64%/36%) mas apenas 8% L3 na hierárquica.")
    print("   Talvez perca contexto entre etapas. Testando classificação direta!")
    print()
    print("📝 Configuração:")
    print("   - Modelo: Qwen 2.5 32B Q4_K_M")
    print("   - 50 notícias (mesmo sample dos testes anteriores)")
    print("   - Classificação DIRETA (todas 500 categorias)")
    print("   - Tempo estimado: ~8 minutos")
    print()

    # Carregar taxonomia
    taxonomy_path = Path(__file__).parent.parent / "data" / "classification" / "arvore.yaml"
    print(f"📚 Carregando taxonomia...")
    print(f"   ✅ Taxonomia carregada")
    print()

    # Carregar dataset
    data_path = Path(__file__).parent.parent / "data" / "classification" / "news_classification_test_annotated.csv"
    print(f"📊 Carregando dataset...")
    df = pd.read_csv(data_path)

    # Pegar 50 notícias (seed fixo - mesmo sample)
    sample_df = df.sample(n=50, random_state=42)
    texts = sample_df['content'].tolist()
    ground_truth = sample_df['level_3_code'].tolist()

    print(f"   ✅ {len(texts)} notícias carregadas")
    print()

    print("=" * 80)
    print("🤖 Testando: Qwen 2.5 32B (Classificação DIRETA)")
    print("=" * 80)
    print()

    try:
        # Inicializar classificador
        print(f"   Inicializando modelo...")
        start_init = time.time()

        classifier = LocalClassifier(
            model_id="qwen2.5:32b-instruct-q4_K_M",
            model_name="Qwen 2.5 32B",
            taxonomy_path=str(taxonomy_path),
            ollama_host="http://localhost:11434",
            timeout=300  # 5 min
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

            result = classifier.classify(text, prompt_strategy='json')

            if result['success']:
                code = extract_code_from_category(result['category'])
                predictions.append(code)
                latencies.append(result['latency'])
                print(f"✅ {result['latency']:5.1f}s - {code}")
            else:
                predictions.append('')
                errors += 1
                print(f"❌ Erro")

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

        print()
        print(f"   📊 Resultados (DIRETA):")
        print(f"      Accuracy L1: {accuracy['l1']*100:5.1f}%")
        print(f"      Accuracy L2: {accuracy['l2']*100:5.1f}%")
        print(f"      Accuracy L3: {accuracy['l3']*100:5.1f}%")
        print(f"      Latência média: {avg_latency:6.2f}s")
        print(f"      Tempo total: {total_time/60:6.1f} min")
        print(f"      Throughput: {throughput:6.3f} classificações/seg")
        print(f"      Erros: {errors}/{len(texts)}")
        print()

        # Comparar com resultado hierárquico
        print("=" * 80)
        print("📊 COMPARAÇÃO: HIERÁRQUICA vs DIRETA (Qwen 32B)")
        print("=" * 80)
        print()
        print("Abordagem        Acc L1   Acc L2   Acc L3   Latência")
        print("-" * 60)
        print(f"Hierárquica      64.0%    36.0%     8.0%     8.3s")
        print(f"Direta          {accuracy['l1']*100:5.1f}%   {accuracy['l2']*100:5.1f}%   {accuracy['l3']*100:5.1f}%    {avg_latency:5.1f}s")
        print()

        # Análise
        delta_l1 = accuracy['l1']*100 - 64.0
        delta_l2 = accuracy['l2']*100 - 36.0
        delta_l3 = accuracy['l3']*100 - 8.0

        print("💡 ANÁLISE:")
        print()
        if delta_l3 > 5:
            print(f"   ✅ DIRETA VENCEU! +{delta_l3:.1f} pontos em L3")
            print(f"   → Modelo 32B consegue lidar com prompt de 500 categorias")
            print(f"   → Não perde contexto como na hierárquica")
            print(f"   → Recomendação: usar classificação DIRETA para modelos 32B+")
        elif delta_l3 > 0:
            print(f"   ⚖️ DIRETA ligeiramente melhor (+{delta_l3:.1f} pontos)")
            print(f"   → Ganho marginal, ambas abordagens viáveis")
        else:
            print(f"   ❌ HIERÁRQUICA ainda melhor")
            print(f"   → Mesmo com 32B, prompt grande não ajuda")
            print(f"   → Problema é capacidade fundamental do modelo")

        print()
        print("🎯 CONTEXTO CRÍTICO:")
        print(f"   Melhor resultado local: {max(accuracy['l3']*100, 16.0):.1f}% L3")
        print(f"   Claude Haiku (API): 80.5% L3")
        print(f"   Gap: {80.5 - max(accuracy['l3']*100, 16.0):.1f} pontos")
        print()

        if max(accuracy['l3']*100, 16.0) < 30:
            print("   ⚠️  Mesmo com melhor abordagem, modelos locais não competem com APIs")
            print("   ⚠️  Recomendação: usar Claude Haiku em produção")

    except Exception as e:
        print(f"   ❌ ERRO FATAL: {str(e)}")

    print()
    print("=" * 80)
    print("✅ TESTE QWEN 32B DIRETO CONCLUÍDO!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
