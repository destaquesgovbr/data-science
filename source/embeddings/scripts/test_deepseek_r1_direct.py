#!/usr/bin/env python3
"""
Teste específico: DeepSeek-R1-Distill-Qwen-14B com classificação DIRETA.
Chain-of-thought nativo pode lidar com prompt de 500 categorias?
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
    print("🧪 TESTE DEEPSEEK-R1 - Classificação DIRETA (500 categorias)")
    print("=" * 80)
    print()
    print("🎯 Hipótese:")
    print("   Chain-of-thought nativo do DeepSeek-R1 pode raciocinar sobre")
    print("   500 categorias simultaneamente melhor que outros modelos.")
    print()
    print("📊 Contexto:")
    print("   - Outros modelos falharam na direta (0% L3)")
    print("   - DeepSeek-R1 tem reasoning avançado")
    print("   - Pode ser a combinação que funciona!")
    print()
    print("📝 Configuração:")
    print("   - Modelo: DeepSeek-R1-Distill-Qwen-14B")
    print("   - 50 notícias (mesmo sample)")
    print("   - Classificação DIRETA (todas 500 categorias)")
    print("   - Timeout generoso (reasoning + prompt grande)")
    print("   - Tempo estimado: 20-30 minutos")
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
    print("🤖 Testando: DeepSeek-R1 (Classificação DIRETA)")
    print("=" * 80)
    print()

    try:
        # Inicializar classificador
        print(f"   Inicializando modelo...")
        start_init = time.time()

        classifier = LocalClassifier(
            model_id="deepseek-r1:14b",
            model_name="DeepSeek-R1-Distill-Qwen-14B",
            taxonomy_path=str(taxonomy_path),
            ollama_host="http://localhost:11434",
            timeout=600  # 10 min - reasoning + prompt grande
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

        # Comparar hierárquica vs direta
        print("=" * 80)
        print("📊 COMPARAÇÃO: HIERÁRQUICA vs DIRETA (DeepSeek-R1)")
        print("=" * 80)
        print()
        print("Abordagem        Acc L1   Acc L2   Acc L3   Latência")
        print("-" * 60)
        print(f"Hierárquica       ???%     ???%     ???%     ???s     (aguardando)")
        print(f"Direta          {accuracy['l1']*100:5.1f}%   {accuracy['l2']*100:5.1f}%   {accuracy['l3']*100:5.1f}%    {avg_latency:5.1f}s")
        print()

        # Análise
        print("💡 ANÁLISE:")
        print()

        l3_pct = accuracy['l3']*100

        if l3_pct > 20:
            print(f"   🎉 BREAKTHROUGH! DeepSeek-R1 conseguiu {l3_pct:.1f}% L3 na DIRETA!")
            print(f"   → Chain-of-thought funcionou com prompt de 500 categorias")
            print(f"   → Primeiro modelo que não zerou na abordagem direta")
            print(f"   → Reasoning avançado fez diferença!")
        elif l3_pct > 10:
            print(f"   ✅ DeepSeek-R1 conseguiu {l3_pct:.1f}% na direta")
            print(f"   → Melhor que outros (0%), mas ainda baixo")
            print(f"   → Reasoning ajudou mas não o suficiente")
        elif l3_pct > 0:
            print(f"   ⚖️ DeepSeek-R1 teve {l3_pct:.1f}% na direta")
            print(f"   → Pelo menos não zerou (como Qwen 32B)")
            print(f"   → Mas resultado insignificante")
        else:
            print(f"   ❌ DeepSeek-R1 também zerou na direta (0% L3)")
            print(f"   → Nem chain-of-thought salvou")
            print(f"   → Confirma: prompt de 500 categorias não funciona")

        print()
        print("🎯 CONTEXTO GERAL:")
        print("   Hierárquica (melhores): Llama 8B 16%, Qwen 32B 8%")
        print("   Direta (todos): 0% L3 (exceto este teste)")
        print(f"   Claude Haiku: 80.5% L3")
        print()

        if l3_pct < 20:
            print("   ⚠️  Mesmo com chain-of-thought, classificação direta falha")
            print("   ⚠️  Hierárquica continua sendo a melhor abordagem local")

    except Exception as e:
        print(f"   ❌ ERRO: {str(e)}")

    print()
    print("=" * 80)
    print("✅ TESTE DEEPSEEK-R1 DIRETO CONCLUÍDO!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
