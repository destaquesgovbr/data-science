#!/usr/bin/env python3
"""
Teste específico: Phi-4 14B com classificação hierárquica.
Hipótese: Modelo focado em reasoning pode ter melhor performance desproporcional.
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
    print("🧪 TESTE PHI-4 14B - Última Tentativa com Reasoning Specialist")
    print("=" * 80)
    print()
    print("🎯 Por que Phi-4?")
    print("   - Microsoft, focado em REASONING")
    print("   - Arquitetura diferente (não Llama/Qwen/Gemma)")
    print("   - Família Phi conhecida por 'punch above its weight'")
    print("   - Classificação hierárquica = tarefa de raciocínio")
    print()
    print("📊 Contexto:")
    print("   Testamos: Gemma 2B (6%), Llama 8B (16%), Qwen 14B (0%), Qwen 32B (8%)")
    print("   Baseline API: Claude Haiku 80.5%")
    print("   Phi-4 precisa: >20% L3 para ser promissor, >40% para competir")
    print()
    print("📝 Configuração:")
    print("   - Modelo: Phi-4 14B (phi3:14b)")
    print("   - 50 notícias (mesmo sample dos testes)")
    print("   - Classificação hierárquica v2 (parsing robusto)")
    print("   - Tempo estimado: 10-15 minutos")
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
    print("🤖 Testando: Phi-4 14B (Microsoft Reasoning Specialist)")
    print("=" * 80)
    print()

    try:
        # Inicializar classificador
        print(f"   Inicializando modelo...")
        start_init = time.time()

        classifier = LocalClassifier(
            model_id="phi3:14b",
            model_name="Phi-4 14B",
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

        # Comparar com outros modelos
        print("=" * 80)
        print("📊 COMPARAÇÃO: Phi-4 vs Outros Modelos (Hierárquica)")
        print("=" * 80)
        print()
        print("Modelo               Params   Acc L1   Acc L2   Acc L3   Latência")
        print("-" * 72)
        print(f"Gemma 2 2B           2B       42.0%    30.0%     6.0%     1.6s")
        print(f"Llama 3.1 8B Q4      8B       46.0%    34.0%    16.0%     2.6s  ← Melhor")
        print(f"Qwen 2.5 14B         14B      46.0%    18.0%     0.0%     6.0s")
        print(f"Qwen 2.5 32B         32B      64.0%    36.0%     8.0%     8.3s")
        print(f"Phi-4 14B            14B     {accuracy['l1']*100:5.1f}%   {accuracy['l2']*100:5.1f}%   {accuracy['l3']*100:5.1f}%    {avg_latency:5.1f}s  ← NOVO")
        print()

        # Análise
        print("💡 ANÁLISE:")
        print()

        l3_pct = accuracy['l3']*100

        if l3_pct > 40:
            print(f"   🎉 BREAKTHROUGH! Phi-4 atingiu {l3_pct:.1f}% L3!")
            print(f"   → Reasoning specialist fez diferença")
            print(f"   → Gap vs Haiku reduziu para {80.5 - l3_pct:.1f} pontos")
            print(f"   → Vale explorar fine-tuning ou modelos maiores desta família")
        elif l3_pct > 20:
            print(f"   ✅ Phi-4 melhorou vs Qwen 14B (0%) mas ainda longe do ideal")
            print(f"   → {l3_pct:.1f}% L3 é melhor que Qwen mas pior que Llama 8B (16%)")
            print(f"   → Gap vs Haiku: {80.5 - l3_pct:.1f} pontos")
            print(f"   → Reasoning ajudou mas não o suficiente")
        elif l3_pct >= 16:
            print(f"   ⚖️ Phi-4 empatou com Llama 8B (~{l3_pct:.1f}% L3)")
            print(f"   → Mesmo 14B, não superou 8B")
            print(f"   → Tamanho/arquitetura não são o gargalo")
        else:
            print(f"   ❌ Phi-4 não superou melhores resultados ({l3_pct:.1f}% vs 16%)")
            print(f"   → Reasoning specialist não ajudou nesta tarefa")
            print(f"   → Confirma padrão: modelos locais < 32B não competem")

        print()
        print("🎯 CONTEXTO FINAL:")
        print(f"   Melhor local: {max(l3_pct, 16.0):.1f}% L3")
        print(f"   Claude Haiku: 80.5% L3")
        print(f"   Gap: {80.5 - max(l3_pct, 16.0):.1f} pontos")
        print()

        if max(l3_pct, 16.0) < 30:
            print("=" * 80)
            print("⚠️  CONCLUSÃO DEFINITIVA")
            print("=" * 80)
            print()
            print("Testamos TODAS as opções viáveis na GPU L4:")
            print("  • Tamanhos: 2B → 8B → 14B → 32B")
            print("  • Quantizações: Q4 → Q6")
            print("  • Arquiteturas: Llama, Qwen, Gemma, Phi")
            print("  • Abordagens: Hierárquica, Direta")
            print("  • Especialistas: General purpose vs Reasoning")
            print()
            print("Resultado consistente: ~16% accuracy máxima (5x pior que API)")
            print()
            print("✅ Decisão final mantida: Usar Claude Haiku em produção")
            print("   - 80.5% accuracy L3")
            print("   - $97/mês (@1k classificações/dia)")
            print("   - Confiável, testado, em produção")
        else:
            print("💡 Phi-4 abriu possibilidades! Considerar:")
            print("   - Fine-tuning de Phi-4 na taxonomia")
            print("   - Explorar modelos reasoning maiores")
            print("   - Híbrido: Phi-4 + API para casos difíceis")

    except Exception as e:
        print(f"   ❌ ERRO FATAL: {str(e)}")

    print()
    print("=" * 80)
    print("✅ TESTE PHI-4 CONCLUÍDO!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
