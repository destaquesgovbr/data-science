"""
Teste rápido de modelos locais.

Testa 3 modelos em 10 notícias para validação técnica antes da avaliação completa.
Útil para:
- Verificar se Ollama está funcionando
- Confirmar que modelos foram baixados
- Validar parsing JSON
- Estimar tempo total da avaliação completa
"""

import sys
from pathlib import Path
import pandas as pd
import time

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.local_classifier import LocalClassifier


def test_quick():
    """Executa teste rápido."""
    print("=" * 80)
    print("🧪 TESTE RÁPIDO - MODELOS LOCAIS")
    print("=" * 80)
    print()
    print("Configuração:")
    print("  - 3 modelos (1 por tier)")
    print("  - 10 notícias")
    print("  - Validação técnica")
    print()

    # Modelos para teste rápido
    test_models = [
        {
            'name': 'Llama 3.1 8B',
            'model_id': 'llama3.1:8b-instruct-q4_K_M',
            'tier': 'B'
        },
        {
            'name': 'Mistral 7B',
            'model_id': 'mistral:7b-instruct-v0.3-q4_K_M',
            'tier': 'B'
        },
        {
            'name': 'Gemma 2 2B',
            'model_id': 'gemma2:2b-instruct-q4_K_M',
            'tier': 'C'
        }
    ]

    # Carregar dataset
    data_path = BASE_DIR / "data" / "classification" / "news_classification_test_annotated.csv"
    df = pd.read_csv(data_path)

    # Selecionar 10 notícias aleatórias
    sample_df = df.sample(n=10, random_state=42)

    texts = sample_df['content'].tolist()
    ground_truth = [
        f"{row['level_3_code']} - {row['level_3_label']}"
        for _, row in sample_df.iterrows()
    ]

    print(f"✅ Dataset carregado: {len(sample_df)} notícias (sample)")
    print()

    # Testar cada modelo
    results = []

    for i, model_config in enumerate(test_models):
        print(f"\n{'='*80}")
        print(f"[{i+1}/{len(test_models)}] TESTANDO: {model_config['name']}")
        print(f"{'='*80}")
        print()

        try:
            # Inicializar classificador
            classifier = LocalClassifier(
                model_id=model_config['model_id'],
                model_name=model_config['name'],
                ollama_host="http://localhost:11434"
            )

            # Classificar 10 notícias
            print("📊 Classificando 10 notícias...")
            predictions = []
            errors = 0
            start_time = time.time()

            for j, text in enumerate(texts):
                print(f"  {j+1}/10...", end='\r')
                result = classifier.classify(text)
                predictions.append(result['category'])
                if not result['success']:
                    errors += 1

            total_time = time.time() - start_time

            # Calcular accuracy L3 rápida
            correct = sum(1 for gt, pred in zip(ground_truth, predictions) if gt == pred)
            accuracy_l3 = (correct / len(predictions)) * 100

            # Stats
            stats = classifier.get_stats()

            print(f"\n✅ Concluído em {total_time:.1f}s")
            print()
            print("Resultados:")
            print(f"  Accuracy L3: {accuracy_l3:.1f}% ({correct}/10)")
            print(f"  Latência média: {stats['avg_latency']:.2f}s")
            print(f"  Erros: {errors}/10")
            print()

            results.append({
                'model': model_config['name'],
                'tier': model_config['tier'],
                'accuracy_l3': accuracy_l3,
                'avg_latency': stats['avg_latency'],
                'errors': errors,
                'status': 'ok'
            })

        except Exception as e:
            print(f"❌ ERRO: {e}")
            print()
            results.append({
                'model': model_config['name'],
                'tier': model_config['tier'],
                'status': 'failed',
                'error': str(e)
            })

        # Pausa entre modelos
        if i < len(test_models) - 1:
            time.sleep(2)

    # Resumo
    print("\n" + "=" * 80)
    print("📊 RESUMO DO TESTE RÁPIDO")
    print("=" * 80)
    print()

    for result in results:
        if result['status'] == 'ok':
            print(f"✅ {result['model']} ({result['tier']})")
            print(f"   Accuracy: {result['accuracy_l3']:.1f}% | Latência: {result['avg_latency']:.2f}s | Erros: {result['errors']}/10")
        else:
            print(f"❌ {result['model']} ({result['tier']}) - FALHOU")
            print(f"   Erro: {result['error']}")
        print()

    # Estimativa de tempo para avaliação completa
    successful = [r for r in results if r['status'] == 'ok']
    if successful:
        avg_latency = sum(r['avg_latency'] for r in successful) / len(successful)
        estimated_time_per_model = avg_latency * 200 / 60  # minutos
        estimated_total = estimated_time_per_model * 8  # 8 modelos

        print("=" * 80)
        print("⏱️  ESTIMATIVA PARA AVALIAÇÃO COMPLETA")
        print("=" * 80)
        print()
        print(f"Latência média: {avg_latency:.2f}s por classificação")
        print(f"Tempo por modelo (200 news): ~{estimated_time_per_model:.1f} min")
        print(f"Tempo total estimado (8 modelos): ~{estimated_total:.1f} min ({estimated_total/60:.1f}h)")
        print()

    print("=" * 80)
    print("✅ TESTE CONCLUÍDO!")
    print("=" * 80)
    print()
    print("Se tudo funcionou, rode a avaliação completa:")
    print("  python scripts/evaluate_local_models.py")
    print()


if __name__ == '__main__':
    # Verificar se Ollama está rodando
    import requests

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
    except Exception as e:
        print("❌ ERRO: Ollama não está rodando!")
        print(f"   {e}")
        print()
        print("Para iniciar o Ollama:")
        print("   ollama serve")
        print()
        sys.exit(1)

    test_quick()
