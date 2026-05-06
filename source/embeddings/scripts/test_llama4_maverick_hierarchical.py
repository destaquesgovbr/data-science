#!/usr/bin/env python3
"""
Teste específico: Llama 4 Maverick com classificação hierárquica.
Llama 3.1 8B foi o melhor (16% L3). Llama 4 pode superar?
"""

import sys
import time
import pandas as pd
from pathlib import Path

# Adicionar path do projeto
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from source.embeddings.classifiers.local_classifier import LocalClassifier
from source.embeddings.prompts.classification_prompts_hierarchical import classify_hierarchical
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


def main():
    print("=" * 80)
    print("🧪 TESTE LLAMA 4 MAVERICK - Hierárquica")
    print("=" * 80)
    print()
    print("🎯 Por que Llama 4 Maverick?")
    print("   - Llama 3.1 8B foi nosso MELHOR resultado (16% L3)")
    print("   - Llama 4 é a versão mais recente (2025)")
    print("   - Melhorias em reasoning e instruction following")
    print("   - Se algum modelo vai superar 16%, é este!")
    print()
    print("📊 Recorde a bater: Llama 3.1 8B - 16% L3")
    print()
    print("📝 Configuração:")
    print("   - Modelo: Llama 4 Maverick")
    print("   - 50 notícias (mesmo sample)")
    print("   - Classificação hierárquica v2 (parsing robusto)")
    print("   - Tempo estimado: 8-12 minutos")
    print()

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

    # Pegar 50 notícias (seed fixo)
    sample_df = df.sample(n=50, random_state=42)
    texts = sample_df['content'].tolist()
    ground_truth = sample_df['level_3_code'].tolist()

    print(f"   ✅ {len(texts)} notícias carregadas")
    print()

    print("=" * 80)
    print("🤖 Testando: Llama 4 Maverick")
    print("=" * 80)
    print()

    try:
        # Inicializar classificador
        print(f"   Inicializando modelo...")
        start_init = time.time()

        classifier = LocalClassifier(
            model_id="llama4:latest",
            model_name="Llama 4 Maverick",
            ollama_host="http://localhost:11434",
            timeout=300
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

        # Comparar com Llama 3.1
        print("=" * 80)
        print("📊 COMPARAÇÃO: Llama 3.1 vs Llama 4 Maverick")
        print("=" * 80)
        print()
        print("Modelo                   Acc L1   Acc L2   Acc L3   Latência")
        print("-" * 68)
        print(f"Llama 3.1 8B Q4          46.0%    34.0%    16.0%     2.6s  🥇 Anterior")
        print(f"Llama 4 Maverick        {accuracy['l1']*100:5.1f}%   {accuracy['l2']*100:5.1f}%   {accuracy['l3']*100:5.1f}%    {avg_latency:5.1f}s  ← NOVO")
        print()
        print(f"Claude Haiku (API)         -         -      80.5%     2-3s  👑 Baseline")
        print()

        # Análise
        print("💡 ANÁLISE:")
        print()

        l3_pct = accuracy['l3']*100
        delta = l3_pct - 16.0

        if l3_pct > 40:
            print(f"   🎉 BREAKTHROUGH HISTÓRICO!")
            print(f"   Llama 4 atingiu {l3_pct:.1f}% L3 (+{delta:.1f} pontos vs Llama 3.1)")
            print(f"   → Melhor modelo local de longe!")
            print(f"   → Gap vs Haiku: {80.5 - l3_pct:.1f} pontos")
            print(f"   → Modelos locais podem ser viáveis com Llama 4!")
        elif l3_pct > 25:
            print(f"   ✅ Llama 4 MELHOROU significativamente!")
            print(f"   {l3_pct:.1f}% L3 (+{delta:.1f} pontos vs Llama 3.1)")
            print(f"   → Progresso real, mas ainda longe de Haiku (80.5%)")
            print(f"   → Gap: {80.5 - l3_pct:.1f} pontos")
        elif delta > 5:
            print(f"   ✅ Llama 4 melhorou ({l3_pct:.1f}% vs 16.0%)")
            print(f"   +{delta:.1f} pontos - melhoria incremental")
            print(f"   → Evolução na direção certa mas insuficiente")
        elif delta > 0:
            print(f"   ⚖️ Llama 4 ligeiramente melhor ({l3_pct:.1f}% vs 16.0%)")
            print(f"   +{delta:.1f} pontos - melhoria marginal")
        elif delta == 0:
            print(f"   ⚖️ Llama 4 empatou com 3.1 ({l3_pct:.1f}%)")
            print(f"   Sem melhoria significativa entre versões")
        else:
            print(f"   ❌ Llama 4 PIOROU vs 3.1 ({l3_pct:.1f}% vs 16.0%)")
            print(f"   {delta:.1f} pontos - versão mais nova pior!")

        print()
        print(f"🎯 Recorde local: {max(l3_pct, 16.0):.1f}% L3")
        print(f"   Gap vs Haiku: {80.5 - max(l3_pct, 16.0):.1f} pontos")

    except Exception as e:
        print(f"   ❌ ERRO: {str(e)}")
        print()
        print("   Possível causa: Modelo não instalado")
        print("   Rode: ollama pull llama4")
        print("   Verifique: ollama list")

    print()
    print("=" * 80)
    print("✅ TESTE LLAMA 4 HIERÁRQUICO CONCLUÍDO!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
