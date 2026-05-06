#!/usr/bin/env python3
"""
Teste de classificação hierárquica em 3 etapas.
Permite que modelos pequenos processem sem timeout.
"""

import sys
from pathlib import Path

# Adicionar path do projeto
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from source.embeddings.classifiers.local_classifier import LocalClassifier
from source.embeddings.prompts.classification_prompts_hierarchical import classify_hierarchical
from source.embeddings.utils.taxonomy_parser import TaxonomyParser
import time

def main():
    print("=" * 80)
    print("🧪 TESTE DE CLASSIFICAÇÃO HIERÁRQUICA (3 ETAPAS)")
    print("=" * 80)
    print()

    # Configuração
    model_id = "gemma2:2b-instruct-q4_K_M"
    model_name = "Gemma 2 2B"

    # Carregar taxonomia
    taxonomy_path = Path(__file__).parent.parent / "data" / "classification" / "arvore.yaml"
    print(f"📚 Carregando taxonomia de {taxonomy_path}...")
    taxonomy = TaxonomyParser(str(taxonomy_path))
    print(f"   ✅ {len(taxonomy.flat_categories)} categorias carregadas")
    print()

    # Inicializar classificador
    print(f"🤖 Inicializando {model_name}...")
    classifier = LocalClassifier(
        model_id=model_id,
        model_name=model_name,
        ollama_host="http://localhost:11434",
        timeout=120  # 2 minutos por etapa
    )
    print(f"   ✅ Modelo pronto")
    print()

    # Texto de teste
    text = """
    Ministério da Educação anuncia novo programa de bolsas para estudantes
    universitários de baixa renda. O programa Abdias Nascimento, gerido pela
    CAPES, prevê investimento de R$ 500 milhões em 2025 para apoiar estudantes
    de pós-graduação em todo o país.
    """

    print("📰 Notícia de teste:")
    print("   " + text.strip()[:200] + "...")
    print()

    # Classificar
    print("🔄 Classificando hierarquicamente...")
    print()

    result = classify_hierarchical(text, taxonomy, classifier)

    # Resultados
    print("=" * 80)
    print("📊 RESULTADOS")
    print("=" * 80)
    print()

    if result['success']:
        print(f"✅ Classificação bem-sucedida!")
        print()
        print(f"   Nível 1: {result['level1_code']} ({result['latency_l1']:.2f}s)")
        print(f"   Nível 2: {result['level2_code']} ({result['latency_l2']:.2f}s)")
        print(f"   Nível 3: {result['level3_code']} ({result['latency_l3']:.2f}s)")
        print()
        print(f"   ⏱️  Tempo total: {result['latency_total']:.2f}s")
        print()
        print(f"   Ground truth esperado: 02.04.03 - Bolsas e Incentivos")
        print(f"   Predição: {result['level3_code']}")

        if result['level3_code'] == "02.04.03":
            print(f"   🎯 CORRETO!")
        else:
            print(f"   ❌ Incorreto")

    else:
        print(f"❌ Erro: {result.get('error', 'Unknown')}")
        print()
        print(f"   Níveis parciais:")
        print(f"   L1: {result['level1_code']}")
        print(f"   L2: {result['level2_code']}")
        print(f"   L3: {result['level3_code']}")

    print()
    print("=" * 80)
    print("💡 Vantagens da abordagem hierárquica:")
    print("=" * 80)
    print("  1. Prompts muito menores (10-30 categorias por etapa vs 500 todas)")
    print("  2. Modelos pequenos (2B-3B) conseguem processar")
    print("  3. Timeout razoável (120s por etapa vs 180s+ com prompt grande)")
    print("  4. Pode ser mais preciso (decisões focadas por etapa)")
    print()

if __name__ == "__main__":
    main()
