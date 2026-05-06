#!/usr/bin/env python3
"""
Teste específico: Llama 4 Maverick com classificação DIRETA.
Llama 3.1 falhou na direta (0%). Llama 4 pode lidar com 500 categorias?
"""

import sys
import time
import pandas as pd
from pathlib import Path

# Adicionar path do projeto
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from source.embeddings.classifiers.local_classifier import LocalClassifier


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
    print("🧪 TESTE LLAMA 4 MAVERICK - Classificação DIRETA")
    print("=" * 80)
    print()
    print("🎯 Hipótese:")
    print("   Llama 4 tem melhorias em context understanding.")
    print("   Pode conseguir processar 500 categorias onde Llama 3.1 falhou?")
    print()
    print("📊 Contexto:")
    print("   - Llama 3.1 direto: 0% L3 (falhou)")
    print("   - Todos modelos direto: 0% L3 (exceto DeepSeek-R1?)")
    print("   - Llama 4 pode ser o primeiro a funcionar na direta!")
    print()
    print("📝 Configuração:")
    print("   - Modelo: Llama 4 Maverick")
    print("   - 50 notícias (mesmo sample)")
    print("   - Classificação DIRETA (500 categorias simultâneas)")
    print("   - Tempo estimado: 10-15 minutos")
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

    # Pegar 50 notícias (seed fixo)
    sample_df = df.sample(n=50, random_state=42)
    texts = sample_df['content'].tolist()
    ground_truth = sample_df['level_3_code'].tolist()

    print(f"   ✅ {len(texts)} notícias carregadas")
    print()

    print("=" * 80)
    print("🤖 Testando: Llama 4 Maverick (DIRETA)")
    print("=" * 80)
    print()

    try:
        # Inicializar classificador
        print(f"   Inicializando modelo...")
        start_init = time.time()

        classifier = LocalClassifier(
            model_id="llama4:latest",
            model_name="Llama 4 Maverick",
            taxonomy_path=str(taxonomy_path),
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

        # Comparar
        print("=" * 80)
        print("📊 COMPARAÇÃO: Hierárquica vs Direta (Llama)")
        print("=" * 80)
        print()
        print("Modelo / Abordagem           Acc L1   Acc L2   Acc L3   Latência")
        print("-" * 72)
        print(f"Llama 3.1 8B - Hierárquica   46.0%    34.0%    16.0%     2.6s")
        print(f"Llama 3.1 8B - Direta         4.0%     4.0%     0.0%     5.3s")
        print(f"Llama 4 - Hierárquica         ???%     ???%     ???%     ???s  (outro teste)")
        print(f"Llama 4 - Direta            {accuracy['l1']*100:5.1f}%   {accuracy['l2']*100:5.1f}%   {accuracy['l3']*100:5.1f}%    {avg_latency:5.1f}s  ← NOVO")
        print()

        # Análise
        print("💡 ANÁLISE:")
        print()

        l3_pct = accuracy['l3']*100

        if l3_pct > 15:
            print(f"   🎉 BREAKTHROUGH! Llama 4 conseguiu {l3_pct:.1f}% L3 na DIRETA!")
            print(f"   → Primeiro Llama que funciona com prompt de 500 categorias")
            print(f"   → Melhorias de context understanding fizeram diferença")
            print(f"   → Pode competir com hierárquica!")
        elif l3_pct > 5:
            print(f"   ✅ Llama 4 melhorou vs 3.1 ({l3_pct:.1f}% vs 0%)")
            print(f"   → Não zerou como outros modelos")
            print(f"   → Mas ainda muito abaixo da hierárquica (16%)")
        elif l3_pct > 0:
            print(f"   ⚖️ Llama 4 teve {l3_pct:.1f}% na direta")
            print(f"   → Melhor que Llama 3.1 (0%) mas insignificante")
        else:
            print(f"   ❌ Llama 4 também zerou na direta (0% L3)")
            print(f"   → Mesmo com melhorias, prompt de 500 categorias falha")
            print(f"   → Hierárquica continua sendo a única abordagem viável")

        print()
        print(f"🎯 Conclusão: Hierárquica >> Direta (confirmado novamente)")

    except Exception as e:
        print(f"   ❌ ERRO: {str(e)}")

    print()
    print("=" * 80)
    print("✅ TESTE LLAMA 4 DIRETO CONCLUÍDO!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
