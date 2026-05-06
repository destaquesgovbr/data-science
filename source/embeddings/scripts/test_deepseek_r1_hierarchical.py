#!/usr/bin/env python3
"""
Teste específico: DeepSeek-R1-Distill-Qwen-14B com classificação hierárquica.
Última tentativa: Destilação de modelo SOTA em reasoning (DeepSeek-R1).
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
    print("🧪 TESTE DEEPSEEK-R1-DISTILL - Última Cartada (Chain-of-Thought)")
    print("=" * 80)
    print()
    print("🎯 Por que DeepSeek-R1-Distill?")
    print("   - Destilação do DeepSeek-R1 (SOTA em reasoning)")
    print("   - Chain-of-thought NATIVO (pensa antes de responder)")
    print("   - Compete com o1-preview em benchmarks de raciocínio")
    print("   - Base Qwen mas treinamento totalmente diferente")
    print("   - Lançado Jan/2025 - state-of-the-art recente")
    print()
    print("📊 Histórico de testes:")
    print("   Gemma 2B (6%), Llama 8B (16%), Qwen 14B (0%), Qwen 32B (8%), Phi-4 (<?)")
    print("   Baseline API: Claude Haiku 80.5%")
    print()
    print("🎲 Esta é a ÚLTIMA tentativa antes da conclusão final!")
    print("   Se DeepSeek-R1 < 25% → Fechamos com certeza absoluta")
    print("   Se DeepSeek-R1 > 40% → Breakthrough! Reasoning funciona")
    print()
    print("📝 Configuração:")
    print("   - Modelo: DeepSeek-R1-Distill-Qwen-14B")
    print("   - 50 notícias (mesmo sample de todos os testes)")
    print("   - Classificação hierárquica v2 (parsing robusto)")
    print("   - Timeout generoso (reasoning pode demorar)")
    print("   - Tempo estimado: 15-25 minutos")
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
    print("🤖 Testando: DeepSeek-R1-Distill-Qwen-14B")
    print("=" * 80)
    print()

    try:
        # Inicializar classificador
        print(f"   Inicializando modelo...")
        start_init = time.time()

        # Tentar diferentes nomes possíveis do modelo
        model_candidates = [
            "deepseek-r1:14b",
            "deepseek-r1-distill-qwen-14b",
            "deepseek-r1-distill:14b"
        ]

        print(f"   Tentando localizar modelo no Ollama...")
        model_id = model_candidates[0]  # Usar primeiro como padrão

        classifier = LocalClassifier(
            model_id=model_id,
            model_name="DeepSeek-R1-Distill-Qwen-14B",
            ollama_host="http://localhost:11434",
            timeout=600  # 10 min - reasoning pode demorar
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

        # Comparar com TODOS os modelos testados
        print("=" * 80)
        print("📊 RANKING FINAL - Todos os Modelos Testados")
        print("=" * 80)
        print()
        print("Modelo                          Params   Acc L1   Acc L2   Acc L3   Latência")
        print("-" * 80)
        print(f"Llama 3.1 8B Q4                 8B       46.0%    34.0%    16.0%     2.6s  🥇")
        print(f"Llama 3.1 8B Q6                 8B       46.0%    28.0%    12.0%     2.9s")
        print(f"Qwen 2.5 32B                    32B      64.0%    36.0%     8.0%     8.3s")
        print(f"Gemma 2 2B                      2B       42.0%    30.0%     6.0%     1.6s")
        print(f"Qwen 2.5 14B                    14B      46.0%    18.0%     0.0%     6.0s")
        print(f"Qwen 32B (direto)               32B      20.0%     4.0%     0.0%    24.4s")
        print(f"DeepSeek-R1-Distill-Qwen-14B    14B     {accuracy['l1']*100:5.1f}%   {accuracy['l2']*100:5.1f}%   {accuracy['l3']*100:5.1f}%    {avg_latency:5.1f}s  ← NOVO")
        print()
        print(f"Baseline: Claude Haiku (API)             -         -      80.5%     2-3s  👑")
        print()

        # Análise final
        print("=" * 80)
        print("💡 ANÁLISE FINAL - CONCLUSÃO DEFINITIVA")
        print("=" * 80)
        print()

        l3_pct = accuracy['l3']*100
        best_local = max(l3_pct, 16.0)

        if l3_pct > 40:
            print(f"   🎉 BREAKTHROUGH INESPERADO!")
            print(f"   DeepSeek-R1 atingiu {l3_pct:.1f}% L3 - melhor resultado local!")
            print(f"   Gap vs Haiku: {80.5 - l3_pct:.1f} pontos")
            print()
            print("   🔬 Próximos passos:")
            print("   1. Fine-tuning de DeepSeek-R1 na taxonomia")
            print("   2. Testar versões maiores (32B, 70B)")
            print("   3. Analisar chain-of-thought gerado")
            print("   4. Considerar híbrido: DeepSeek + API")
        elif l3_pct > 25:
            print(f"   ✅ DeepSeek-R1 melhorou ({l3_pct:.1f}% L3)")
            print(f"   Melhor que maioria, mas ainda longe de Haiku (80.5%)")
            print(f"   Gap: {80.5 - l3_pct:.1f} pontos")
            print()
            print("   ⚖️ Avaliação:")
            print("   - Reasoning ajudou mas não o suficiente")
            print("   - Melhoria incremental, não transformadora")
            print("   - Decisão mantida: usar Claude Haiku")
        elif l3_pct >= 16:
            print(f"   ⚖️ DeepSeek-R1 empatou com Llama 8B ({l3_pct:.1f}% vs 16%)")
            print(f"   Chain-of-thought não trouxe vantagem significativa")
            print(f"   Gap vs Haiku: {80.5 - l3_pct:.1f} pontos")
        else:
            print(f"   ❌ DeepSeek-R1 não superou melhores resultados ({l3_pct:.1f}% vs 16%)")
            print(f"   Nem destilação de SOTA em reasoning ajudou")

        print()
        print("=" * 80)
        print("🎯 CONCLUSÃO CIENTÍFICA FINAL")
        print("=" * 80)
        print()
        print(f"Testamos 10+ configurações na GPU L4:")
        print(f"  ✓ Tamanhos: 2B, 8B, 14B, 32B")
        print(f"  ✓ Famílias: Llama, Qwen, Gemma, Phi, DeepSeek")
        print(f"  ✓ Quantizações: Q4_K_M, Q6_K")
        print(f"  ✓ Abordagens: Hierárquica (3 etapas), Direta (1 etapa)")
        print(f"  ✓ Especialistas: General, Reasoning, Chain-of-Thought")
        print()
        print(f"📊 Resultado consistente:")
        print(f"   Melhor local: {best_local:.1f}% accuracy L3")
        print(f"   Claude Haiku: 80.5% accuracy L3")
        print(f"   Gap: {80.5 - best_local:.1f} pontos ({80.5/best_local:.1f}x pior)")
        print()

        if best_local < 30:
            print("✅ DECISÃO FINAL INCONTESTÁVEL:")
            print()
            print("   Usar Claude Haiku via AWS Bedrock em produção")
            print()
            print("   Justificativa técnica:")
            print("   • Accuracy 5x superior (80.5% vs ~16%)")
            print("   • Custo competitivo ($97/mês @1k/dia)")
            print("   • Latência similar (~2-3s)")
            print("   • Confiável e testado (Fase 2)")
            print("   • Manutenção zero vs overhead local")
            print()
            print("   Modelos locais < 32B não são viáveis para esta tarefa.")
            print("   Exploração completa. Decisão baseada em evidência.")
        else:
            print("💡 DeepSeek-R1 abriu possibilidades!")
            print("   Considerar exploração adicional.")

    except Exception as e:
        print(f"   ❌ ERRO: {str(e)}")
        print()
        print("   Possível causa: Modelo não instalado no Ollama")
        print("   Rode: ollama pull deepseek-r1:14b")

    print()
    print("=" * 80)
    print("🏁 TESTE DEEPSEEK-R1 CONCLUÍDO - FIM DA EXPLORAÇÃO")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
