"""
Script para otimização de prompts dos modelos LLM.

Testa diferentes estratégias de prompt em uma amostra de notícias
para identificar melhorias no desempenho de modelos específicos.

Foco: Claude Sonnet e Mistral Large 3
"""

import sys
from pathlib import Path
import pandas as pd
import time
from typing import Dict, List
import random

# Add parent directory to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.bedrock_classifier_json import BedrockClassifierJSON
from embeddings.prompts.classification_prompts_json import get_prompt_json, get_prompt_json_explicit, get_prompt_json_fewshot
from embeddings.utils.taxonomy_parser import TaxonomyParser


class BedrockClassifierWithPromptStrategy(BedrockClassifierJSON):
    """
    Classificador Bedrock que aceita diferentes estratégias de prompt.
    """

    def __init__(self, *args, prompt_strategy='default', **kwargs):
        super().__init__(*args, **kwargs)
        self.prompt_strategy = prompt_strategy

    def classify(self, text: str, prompt_strategy: str = None) -> dict:
        """
        Classifica usando estratégia de prompt específica.

        Args:
            text: Texto a classificar
            prompt_strategy: 'default', 'explicit', ou 'fewshot'
        """
        strategy = prompt_strategy or self.prompt_strategy

        # Construir prompt baseado na estratégia
        if strategy == 'explicit':
            prompt = get_prompt_json_explicit(text, self.taxonomy)
        elif strategy == 'fewshot':
            prompt = get_prompt_json_fewshot(text, self.taxonomy, num_examples=3)
        else:  # default
            prompt = get_prompt_json(text, self.taxonomy)

        # Construir body da request
        request_body = self._build_request_body(prompt)

        # Chamar Bedrock (resto é igual ao método pai)
        import time
        start_time = time.time()
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=request_body
            )

            # Parse response
            import json
            response_body = json.loads(response['body'].read())

            # Extrair texto e tokens
            response_text, input_tokens, output_tokens = self._extract_response_text(response_body)

            # Parse JSON
            json_result = self._parse_json_response(response_text)

            if json_result is None:
                raise ValueError("Falha ao parsear JSON da resposta")

            # Extrair código e label mais específicos (nível 3)
            most_specific_code = json_result.get('most_specific_theme_code', '')
            most_specific_label = json_result.get('most_specific_theme_label', '')

            # Formato: "XX.XX.XX - Label"
            category_full = f"{most_specific_code} - {most_specific_label}"

            # Validar categoria usando método da base
            category = self._validate_category(category_full)

            latency = time.time() - start_time

            # Atualizar stats
            self.call_count += 1
            self.total_latency += latency
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            return {
                'category': category,
                'confidence': None,
                'latency': latency,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'raw_response': response_text,
                'json_parsed': json_result,
                'success': True,
            }

        except Exception as e:
            latency = time.time() - start_time
            error_msg = str(e)
            self.errors.append({
                'text_preview': text[:100],
                'error': error_msg,
                'latency': latency
            })

            return {
                'category': '20.01.01 - Controle Interno',  # Fallback
                'confidence': None,
                'latency': latency,
                'input_tokens': 0,
                'output_tokens': 0,
                'raw_response': f"ERROR: {error_msg}",
                'json_parsed': None,
                'success': False,
            }


def calculate_hierarchical_agreement(predictions: List[Dict], ground_truth: List[str]) -> Dict:
    """
    Calcula concordância hierárquica em 3 níveis.

    Args:
        predictions: Lista de dicts com 'category'
        ground_truth: Lista de categorias ground truth

    Returns:
        Dict com concordâncias L1, L2, L3
    """
    l1_matches = 0
    l2_matches = 0
    l3_matches = 0
    total = len(predictions)

    for pred, gt in zip(predictions, ground_truth):
        pred_cat = pred['category']

        # Extrair códigos
        pred_l1 = pred_cat.split('.')[0] if '.' in pred_cat else ''
        pred_l2 = '.'.join(pred_cat.split('.')[:2]) if '.' in pred_cat else ''
        pred_l3 = pred_cat.split(' - ')[0] if ' - ' in pred_cat else pred_cat

        gt_l1 = gt.split('.')[0] if '.' in gt else ''
        gt_l2 = '.'.join(gt.split('.')[:2]) if '.' in gt else ''
        gt_l3 = gt.split(' - ')[0] if ' - ' in gt else gt

        # Contar matches
        if pred_l1 == gt_l1:
            l1_matches += 1
        if pred_l2 == gt_l2:
            l2_matches += 1
        if pred_l3 == gt_l3:
            l3_matches += 1

    return {
        'L1': (l1_matches / total * 100) if total > 0 else 0,
        'L2': (l2_matches / total * 100) if total > 0 else 0,
        'L3': (l3_matches / total * 100) if total > 0 else 0,
        'total': total
    }


def test_temperature_variation(classifier: BedrockClassifierJSON,
                                sample_texts: List[str],
                                ground_truth: List[str],
                                temperatures: List[float]) -> Dict:
    """
    Testa variações de temperature.

    Args:
        classifier: Instância do classificador
        sample_texts: Lista de textos para classificar
        ground_truth: Categorias corretas
        temperatures: Lista de temperatures para testar

    Returns:
        Dict com resultados por temperature
    """
    results = {}

    for temp in temperatures:
        print(f"\n  🔥 Testing temperature={temp}...")

        # Modificar temperature temporariamente
        original_temp = None
        predictions = []

        for text in sample_texts:
            # Override temperature no body da request
            # (isso requer modificação no classificador)
            result = classifier.classify(text)
            predictions.append(result)

        # Calcular concordância
        agreement = calculate_hierarchical_agreement(predictions, ground_truth)

        results[f"temp_{temp}"] = {
            'temperature': temp,
            'agreement': agreement,
            'avg_latency': sum(p['latency'] for p in predictions) / len(predictions),
            'errors': sum(1 for p in predictions if not p['success'])
        }

        print(f"     L1: {agreement['L1']:.1f}% | L2: {agreement['L2']:.1f}% | L3: {agreement['L3']:.1f}%")

    return results


def test_explicit_prompt(classifier: BedrockClassifierWithPromptStrategy,
                         sample_texts: List[str],
                         ground_truth: List[str]) -> Dict:
    """
    Testa prompt com instruções explícitas de formatação JSON.

    Args:
        classifier: Instância do classificador
        sample_texts: Lista de textos
        ground_truth: Categorias corretas

    Returns:
        Dict com resultados
    """
    print(f"\n  📝 Testing explicit JSON prompt...")

    predictions = []

    for text in sample_texts:
        result = classifier.classify(text, prompt_strategy='explicit')
        predictions.append(result)

    agreement = calculate_hierarchical_agreement(predictions, ground_truth)

    results = {
        'agreement': agreement,
        'avg_latency': sum(p['latency'] for p in predictions) / len(predictions),
        'errors': sum(1 for p in predictions if not p['success'])
    }

    print(f"     L1: {agreement['L1']:.1f}% | L2: {agreement['L2']:.1f}% | L3: {agreement['L3']:.1f}%")
    print(f"     Errors: {results['errors']}/{len(sample_texts)}")

    return results


def test_fewshot_prompt(classifier: BedrockClassifierWithPromptStrategy,
                        sample_texts: List[str],
                        ground_truth: List[str],
                        num_examples: int = 3) -> Dict:
    """
    Testa prompt com few-shot examples.

    Args:
        classifier: Instância do classificador
        sample_texts: Lista de textos
        ground_truth: Categorias corretas
        num_examples: Número de exemplos para incluir

    Returns:
        Dict com resultados
    """
    print(f"\n  🎯 Testing few-shot prompt ({num_examples} examples)...")

    predictions = []

    for text in sample_texts:
        result = classifier.classify(text, prompt_strategy='fewshot')
        predictions.append(result)

    agreement = calculate_hierarchical_agreement(predictions, ground_truth)

    results = {
        'agreement': agreement,
        'avg_latency': sum(p['latency'] for p in predictions) / len(predictions),
        'errors': sum(1 for p in predictions if not p['success'])
    }

    print(f"     L1: {agreement['L1']:.1f}% | L2: {agreement['L2']:.1f}% | L3: {agreement['L3']:.1f}%")
    print(f"     Errors: {results['errors']}/{len(sample_texts)}")

    return results


def run_optimization_experiment(sample_size: int = 20):
    """
    Executa experimento de otimização de prompts.

    Args:
        sample_size: Número de notícias para testar
    """
    print("=" * 80)
    print("🔬 EXPERIMENTO DE OTIMIZAÇÃO DE PROMPTS")
    print("=" * 80)
    print(f"\nAmostra: {sample_size} notícias")
    print("Modelos: Claude Sonnet, Mistral Large 3")
    print("Estratégias: Temperature, Explicit JSON, Few-shot")
    print()

    # Carregar dataset
    data_path = BASE_DIR / "data" / "classification" / "news_classification_test_annotated.csv"
    df = pd.read_csv(data_path)

    # Selecionar amostra aleatória
    random.seed(42)  # Reproducibilidade
    sample_indices = random.sample(range(len(df)), sample_size)
    sample_df = df.iloc[sample_indices].copy()

    sample_texts = sample_df['content'].tolist()  # Coluna 'content' contém o texto

    # Ground truth deve ser level_3_code + level_3_label (formato: "XX.XX.XX - Nome")
    ground_truth = [
        f"{row['level_3_code']} - {row['level_3_label']}"
        for _, row in sample_df.iterrows()
    ]

    print(f"✅ Dataset carregado: {len(sample_df)} notícias")
    print()

    # Configuração dos modelos (usando IDs válidos do config)
    models_config = [
        {
            'name': 'Claude Sonnet',
            'model_id': 'anthropic.claude-3-sonnet-20240229-v1:0',
            'provider': 'anthropic',
            'baseline_temp': 0.3
        },
        {
            'name': 'Mistral Large 3',
            'model_id': 'mistral.mistral-large-3-675b-instruct',
            'provider': 'mistral',
            'baseline_temp': 0.3
        }
    ]

    all_results = {}

    # Testar cada modelo
    for model_config in models_config:
        print("=" * 80)
        print(f"🤖 MODELO: {model_config['name']}")
        print("=" * 80)

        # Inicializar classificador com suporte a estratégias
        classifier = BedrockClassifierWithPromptStrategy(
            model_id=model_config['model_id'],
            model_name=model_config['name'],
            provider=model_config['provider'],
            region='us-east-1',
            prompt_strategy='default'
        )

        model_results = {}

        # 1. Baseline (settings atuais)
        print("\n📊 BASELINE (default prompt, temperature=0.3)")
        baseline_predictions = []
        for i, text in enumerate(sample_texts):
            print(f"     Classifying {i+1}/{sample_size}...", end='\r')
            result = classifier.classify(text, prompt_strategy='default')
            baseline_predictions.append(result)

        baseline_agreement = calculate_hierarchical_agreement(baseline_predictions, ground_truth)
        model_results['baseline'] = {
            'agreement': baseline_agreement,
            'avg_latency': sum(p['latency'] for p in baseline_predictions) / len(baseline_predictions),
            'errors': sum(1 for p in baseline_predictions if not p['success'])
        }

        print(f"   L1: {baseline_agreement['L1']:.1f}% | L2: {baseline_agreement['L2']:.1f}% | L3: {baseline_agreement['L3']:.1f}%")
        print(f"   Errors: {model_results['baseline']['errors']}/{sample_size}")

        # Reset para próximos testes
        classifier.reset_stats()

        # 2. Explicit prompt (bom para Mistral que tem problemas de JSON parsing)
        model_results['explicit'] = test_explicit_prompt(
            classifier, sample_texts, ground_truth
        )
        classifier.reset_stats()

        # 3. Few-shot (bom para modelos que precisam de exemplos)
        model_results['fewshot'] = test_fewshot_prompt(
            classifier, sample_texts, ground_truth, num_examples=3
        )
        classifier.reset_stats()

        all_results[model_config['name']] = model_results

        # Estatísticas do classificador
        stats = classifier.get_stats()
        print(f"\n📈 Estatísticas:")
        print(f"   Total calls: {stats['total_calls']}")
        print(f"   Avg latency: {stats['avg_latency']:.2f}s")
        print(f"   Total cost: ${stats['total_cost']:.4f}")
        print()

        time.sleep(2)  # Pausa entre modelos

    # Resumo final
    print("=" * 80)
    print("📊 RESUMO DO EXPERIMENTO")
    print("=" * 80)
    print()

    for model_name, results in all_results.items():
        print(f"\n🤖 {model_name}")
        print("-" * 40)

        baseline = results['baseline']
        print(f"Baseline (default prompt):")
        print(f"  L1: {baseline['agreement']['L1']:.1f}%")
        print(f"  L2: {baseline['agreement']['L2']:.1f}%")
        print(f"  L3: {baseline['agreement']['L3']:.1f}%")
        print(f"  Errors: {baseline['errors']}/{sample_size} ({baseline['errors']/sample_size*100:.1f}%)")
        print(f"  Avg latency: {baseline['avg_latency']:.2f}s")

        # Comparar com estratégias alternativas
        if 'explicit' in results:
            explicit = results['explicit']
            l3_diff = explicit['agreement']['L3'] - baseline['agreement']['L3']
            errors_diff = explicit['errors'] - baseline['errors']
            print(f"\nExplicit JSON prompt:")
            print(f"  L1: {explicit['agreement']['L1']:.1f}% ({explicit['agreement']['L1'] - baseline['agreement']['L1']:+.1f}%)")
            print(f"  L2: {explicit['agreement']['L2']:.1f}% ({explicit['agreement']['L2'] - baseline['agreement']['L2']:+.1f}%)")
            print(f"  L3: {explicit['agreement']['L3']:.1f}% ({l3_diff:+.1f}%)")
            print(f"  Errors: {explicit['errors']}/{sample_size} ({errors_diff:+d})")
            if l3_diff > 5:
                print(f"  ✅ IMPROVEMENT >5% detected!")

        if 'fewshot' in results:
            fewshot = results['fewshot']
            l3_diff = fewshot['agreement']['L3'] - baseline['agreement']['L3']
            errors_diff = fewshot['errors'] - baseline['errors']
            print(f"\nFew-shot prompt (3 examples):")
            print(f"  L1: {fewshot['agreement']['L1']:.1f}% ({fewshot['agreement']['L1'] - baseline['agreement']['L1']:+.1f}%)")
            print(f"  L2: {fewshot['agreement']['L2']:.1f}% ({fewshot['agreement']['L2'] - baseline['agreement']['L2']:+.1f}%)")
            print(f"  L3: {fewshot['agreement']['L3']:.1f}% ({l3_diff:+.1f}%)")
            print(f"  Errors: {fewshot['errors']}/{sample_size} ({errors_diff:+d})")
            if l3_diff > 5:
                print(f"  ✅ IMPROVEMENT >5% detected!")

        # Identificar melhor estratégia
        best_strategy = 'baseline'
        best_l3 = baseline['agreement']['L3']

        if 'explicit' in results and results['explicit']['agreement']['L3'] > best_l3:
            best_strategy = 'explicit'
            best_l3 = results['explicit']['agreement']['L3']

        if 'fewshot' in results and results['fewshot']['agreement']['L3'] > best_l3:
            best_strategy = 'fewshot'
            best_l3 = results['fewshot']['agreement']['L3']

        if best_strategy != 'baseline':
            improvement = best_l3 - baseline['agreement']['L3']
            print(f"\n🏆 BEST STRATEGY: {best_strategy} (L3: {best_l3:.1f}%, +{improvement:.1f}%)")

    print()
    print("=" * 80)
    print("✅ EXPERIMENTO CONCLUÍDO")
    print("=" * 80)
    print()
    print("📝 Próximos passos:")
    print("   1. Analisar resultados acima")
    print("   2. Implementar variações de prompt mais promissoras")
    print("   3. Re-testar com estratégias otimizadas")
    print("   4. Se >5% melhoria, aplicar ao dataset completo")
    print()

    return all_results


if __name__ == '__main__':
    # Executar experimento com amostra de 20 notícias
    results = run_optimization_experiment(sample_size=20)
