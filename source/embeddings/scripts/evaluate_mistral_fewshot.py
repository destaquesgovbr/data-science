"""
Avaliação completa do Mistral Large 3 com few-shot prompt.

Roda nas 200 notícias do dataset para validar se a melhoria
observada no experimento se mantém em escala.
"""

import sys
from pathlib import Path
import pandas as pd
import time
from typing import Dict, List
from sklearn.metrics import classification_report, accuracy_score
import json

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.bedrock_classifier_json import BedrockClassifierJSON
from embeddings.prompts.classification_prompts_json import get_prompt_json_fewshot
from embeddings.utils.taxonomy_parser import TaxonomyParser


class BedrockClassifierFewShot(BedrockClassifierJSON):
    """Classificador Bedrock que usa few-shot prompt."""

    def classify(self, text: str, prompt_strategy: str = None) -> dict:
        """Classifica usando few-shot prompt."""
        # Construir prompt few-shot
        prompt = get_prompt_json_fewshot(text, self.taxonomy, num_examples=3)

        # Construir body da request
        request_body = self._build_request_body(prompt)

        # Chamar Bedrock
        start_time = time.time()
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=request_body
            )

            # Parse response
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
                'category': '20.01.01 - Controle Interno',
                'confidence': None,
                'latency': latency,
                'input_tokens': 0,
                'output_tokens': 0,
                'raw_response': f"ERROR: {error_msg}",
                'json_parsed': None,
                'success': False,
            }


def calculate_hierarchical_metrics(y_true: List[str], y_pred: List[str]) -> Dict:
    """
    Calcula métricas hierárquicas (L1, L2, L3).

    Args:
        y_true: Categorias ground truth (formato: "XX.XX.XX - Nome")
        y_pred: Categorias preditas (formato: "XX.XX.XX - Nome")

    Returns:
        Dict com accuracy por nível
    """
    l1_matches = 0
    l2_matches = 0
    l3_matches = 0
    total = len(y_true)

    for gt, pred in zip(y_true, y_pred):
        # Extrair códigos
        gt_code = gt.split(' - ')[0] if ' - ' in gt else gt
        pred_code = pred.split(' - ')[0] if ' - ' in pred else pred

        # Nível 1 (XX)
        gt_l1 = gt_code.split('.')[0] if '.' in gt_code else gt_code
        pred_l1 = pred_code.split('.')[0] if '.' in pred_code else pred_code

        # Nível 2 (XX.XX)
        gt_l2 = '.'.join(gt_code.split('.')[:2]) if '.' in gt_code else ''
        pred_l2 = '.'.join(pred_code.split('.')[:2]) if '.' in pred_code else ''

        # Nível 3 (XX.XX.XX)
        gt_l3 = gt_code
        pred_l3 = pred_code

        # Contar matches
        if gt_l1 == pred_l1:
            l1_matches += 1
        if gt_l2 == pred_l2 and gt_l2 != '':
            l2_matches += 1
        if gt_l3 == pred_l3:
            l3_matches += 1

    return {
        'L1_accuracy': (l1_matches / total * 100) if total > 0 else 0,
        'L2_accuracy': (l2_matches / total * 100) if total > 0 else 0,
        'L3_accuracy': (l3_matches / total * 100) if total > 0 else 0,
        'L1_correct': l1_matches,
        'L2_correct': l2_matches,
        'L3_correct': l3_matches,
        'total': total
    }


def run_evaluation():
    """Executa avaliação completa do Mistral Large 3 com few-shot."""
    print("=" * 80)
    print("🚀 AVALIAÇÃO: MISTRAL LARGE 3 COM FEW-SHOT PROMPT")
    print("=" * 80)
    print()
    print("Dataset: 200 notícias")
    print("Estratégia: Few-shot com 3 exemplos")
    print("Comparação: vs baseline (33.5% L3)")
    print()

    # Carregar dataset
    data_path = BASE_DIR / "data" / "classification" / "news_classification_test_annotated.csv"
    df = pd.read_csv(data_path)

    print(f"✅ Dataset carregado: {len(df)} notícias")
    print()

    # Preparar textos e ground truth
    texts = df['content'].tolist()
    ground_truth = [
        f"{row['level_3_code']} - {row['level_3_label']}"
        for _, row in df.iterrows()
    ]

    # Inicializar classificador
    print("🤖 Inicializando Mistral Large 3 (few-shot)...")
    classifier = BedrockClassifierFewShot(
        model_id='mistral.mistral-large-3-675b-instruct',
        model_name='Mistral Large 3 (Few-shot)',
        provider='mistral',
        region='us-east-1'
    )

    # Configurar pricing
    classifier.input_price_per_mtok = 2.0
    classifier.output_price_per_mtok = 6.0

    print()
    print("=" * 80)
    print("📊 CLASSIFICANDO...")
    print("=" * 80)
    print()

    # Classificar todas as notícias
    predictions = []
    start_time = time.time()

    for i, text in enumerate(texts):
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / (i + 1)
            remaining = avg_time * (len(texts) - i - 1)
            print(f"  Progress: {i+1}/{len(texts)} ({(i+1)/len(texts)*100:.1f}%) | "
                  f"Elapsed: {elapsed/60:.1f}min | "
                  f"ETA: {remaining/60:.1f}min")

        result = classifier.classify(text)
        predictions.append(result['category'])

    total_time = time.time() - start_time

    print()
    print(f"✅ Classificação concluída em {total_time/60:.1f} minutos")
    print()

    # Calcular métricas hierárquicas
    print("=" * 80)
    print("📈 RESULTADOS")
    print("=" * 80)
    print()

    hierarchical_metrics = calculate_hierarchical_metrics(ground_truth, predictions)

    print("Concordância Hierárquica:")
    print(f"  Level 1 (Grande Área):  {hierarchical_metrics['L1_accuracy']:.1f}% ({hierarchical_metrics['L1_correct']}/200)")
    print(f"  Level 2 (Subcategoria): {hierarchical_metrics['L2_accuracy']:.1f}% ({hierarchical_metrics['L2_correct']}/200)")
    print(f"  Level 3 (Tópico):       {hierarchical_metrics['L3_accuracy']:.1f}% ({hierarchical_metrics['L3_correct']}/200)")
    print()

    # Comparar com baseline
    baseline_l1 = 65.0  # Do resultado anterior
    baseline_l2 = 48.5
    baseline_l3 = 33.5

    print("Comparação com Baseline (prompt padrão):")
    print(f"  Level 1: {hierarchical_metrics['L1_accuracy']:.1f}% vs {baseline_l1:.1f}% ({hierarchical_metrics['L1_accuracy'] - baseline_l1:+.1f}%)")
    print(f"  Level 2: {hierarchical_metrics['L2_accuracy']:.1f}% vs {baseline_l2:.1f}% ({hierarchical_metrics['L2_accuracy'] - baseline_l2:+.1f}%)")
    print(f"  Level 3: {hierarchical_metrics['L3_accuracy']:.1f}% vs {baseline_l3:.1f}% ({hierarchical_metrics['L3_accuracy'] - baseline_l3:+.1f}%)")
    print()

    # Estatísticas do classificador
    stats = classifier.get_stats()

    print("Estatísticas de Uso:")
    print(f"  Total chamadas:     {stats['total_calls']}")
    print(f"  Latência média:     {stats['avg_latency']:.2f}s")
    print(f"  Input tokens:       {stats['total_input_tokens']:,}")
    print(f"  Output tokens:      {stats['total_output_tokens']:,}")
    print(f"  Custo total:        ${stats['total_cost']:.4f}")
    print(f"  Erros:              {len(classifier.errors)}/200 ({len(classifier.errors)/2:.1f}%)")
    print()

    # Verificar se houve melhoria significativa
    l3_improvement = hierarchical_metrics['L3_accuracy'] - baseline_l3

    print("=" * 80)
    print("🎯 CONCLUSÃO")
    print("=" * 80)
    print()

    if l3_improvement >= 5:
        print(f"✅ MELHORIA SIGNIFICATIVA detectada!")
        print(f"   Few-shot melhorou L3 em {l3_improvement:+.1f}%")
        print(f"   Recomendação: ADOTAR few-shot para Mistral Large 3")
    elif l3_improvement > 0:
        print(f"⚠️  Melhoria modesta: {l3_improvement:+.1f}% no L3")
        print(f"   Considerar trade-off entre melhoria e complexidade")
    else:
        print(f"❌ Few-shot NÃO melhorou o desempenho ({l3_improvement:+.1f}%)")
        print(f"   Recomendação: manter prompt padrão")
    print()

    # Salvar resultados
    results_path = BASE_DIR / "results" / "mistral_fewshot_evaluation.csv"
    results_df = pd.DataFrame({
        'strategy': ['Few-shot', 'Baseline'],
        'L1_accuracy': [hierarchical_metrics['L1_accuracy'], baseline_l1],
        'L2_accuracy': [hierarchical_metrics['L2_accuracy'], baseline_l2],
        'L3_accuracy': [hierarchical_metrics['L3_accuracy'], baseline_l3],
        'avg_latency': [stats['avg_latency'], 1.73],  # Do experimento
        'cost': [stats['total_cost'], stats['total_cost'] * 0.9],  # Estimativa
        'errors': [len(classifier.errors), 14]  # Do resultado anterior
    })

    results_df.to_csv(results_path, index=False)
    print(f"📁 Resultados salvos em: {results_path}")
    print()

    # Salvar predições detalhadas
    detailed_path = BASE_DIR / "results" / "mistral_fewshot_predictions.csv"
    detailed_df = pd.DataFrame({
        'id': df['id'],
        'ground_truth': ground_truth,
        'prediction': predictions,
        'match_l3': [gt == pred for gt, pred in zip(ground_truth, predictions)]
    })
    detailed_df.to_csv(detailed_path, index=False)
    print(f"📁 Predições detalhadas salvas em: {detailed_path}")
    print()

    return hierarchical_metrics, stats


if __name__ == '__main__':
    results = run_evaluation()
