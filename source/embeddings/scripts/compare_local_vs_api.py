"""
Comparação direta: Melhor modelo local vs Claude Haiku (API).

Gera análise comparativa completa incluindo:
- Accuracy (L1, L2, L3)
- Performance (latência, throughput)
- Custo (TCO local vs API)
- Break-even analysis
- Recomendação final
"""

import sys
from pathlib import Path
import pandas as pd
import json

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))


def load_results() -> tuple:
    """
    Carrega resultados da avaliação local e API.

    Returns:
        (local_results_df, api_haiku_baseline)
    """
    # Resultados locais
    local_path = BASE_DIR / "results" / "local_models" / "comparison_summary.csv"
    if not local_path.exists():
        raise FileNotFoundError(
            f"Resultados locais não encontrados em {local_path}. "
            "Execute primeiro: python scripts/evaluate_local_models.py"
        )

    local_df = pd.read_csv(local_path)

    # Baseline API (Claude Haiku - dos experimentos anteriores)
    api_baseline = {
        'model_name': 'Claude 3 Haiku',
        'provider': 'AWS Bedrock (API)',
        'L1_accuracy': 80.5,
        'L2_accuracy': 80.5,
        'L3_accuracy': 80.5,
        'avg_latency_sec': 2.70,
        'cost_per_200': 0.65,  # USD
        'errors': 0,
        'error_rate_pct': 0.0
    }

    return local_df, api_baseline


def calculate_tco(
    classifications_per_day: int,
    model_latency_sec: float,
    instance_type: str = 'g5.xlarge'
) -> dict:
    """
    Calcula Total Cost of Ownership para deployment local.

    Args:
        classifications_per_day: Volume diário
        model_latency_sec: Latência do modelo
        instance_type: Tipo de instância AWS

    Returns:
        Dict com breakdown de custos
    """
    # Pricing AWS (us-east-1)
    pricing = {
        'g5.xlarge': {
            'on_demand': 1.01,
            'reserved_1yr': 0.60,
            'spot': 0.30,
            'vram_gb': 24
        },
        'g5.2xlarge': {
            'on_demand': 1.21,
            'reserved_1yr': 0.73,
            'spot': 0.36,
            'vram_gb': 24
        }
    }

    instance = pricing.get(instance_type, pricing['g5.xlarge'])

    # Calcular custos mensais
    monthly_cost = {
        'compute_on_demand': instance['on_demand'] * 24 * 30,
        'compute_reserved': instance['reserved_1yr'] * 24 * 30,
        'compute_spot': instance['spot'] * 24 * 30,
        'storage': 15,  # EBS para modelos (~50GB)
        'monitoring': 20,  # CloudWatch
        'devops': 300,  # Manutenção (4-8h/mês)
    }

    monthly_cost['total_on_demand'] = (
        monthly_cost['compute_on_demand'] +
        monthly_cost['storage'] +
        monthly_cost['monitoring'] +
        monthly_cost['devops']
    )

    monthly_cost['total_reserved'] = (
        monthly_cost['compute_reserved'] +
        monthly_cost['storage'] +
        monthly_cost['monitoring'] +
        monthly_cost['devops']
    )

    monthly_cost['total_spot'] = (
        monthly_cost['compute_spot'] +
        monthly_cost['storage'] +
        monthly_cost['monitoring'] +
        monthly_cost['devops']
    )

    # Custo por classificação
    monthly_classifications = classifications_per_day * 30
    cost_per_classification = {
        'on_demand': monthly_cost['total_on_demand'] / monthly_classifications,
        'reserved': monthly_cost['total_reserved'] / monthly_classifications,
        'spot': monthly_cost['total_spot'] / monthly_classifications,
    }

    return {
        'instance_type': instance_type,
        'monthly_cost': monthly_cost,
        'cost_per_classification': cost_per_classification,
        'classifications_per_day': classifications_per_day,
        'monthly_classifications': monthly_classifications
    }


def calculate_api_cost(classifications_per_day: int) -> dict:
    """
    Calcula custo da API Claude Haiku.

    Args:
        classifications_per_day: Volume diário

    Returns:
        Dict com custos
    """
    # Baseado nos resultados: $0.65 para 200 classificações
    cost_per_classification = 0.65 / 200

    monthly_classifications = classifications_per_day * 30
    monthly_cost = cost_per_classification * monthly_classifications

    return {
        'cost_per_classification': cost_per_classification,
        'monthly_cost': monthly_cost,
        'classifications_per_day': classifications_per_day,
        'monthly_classifications': monthly_classifications
    }


def find_breakeven(
    local_monthly_cost: float,
    api_cost_per_classification: float
) -> int:
    """
    Encontra volume de break-even (local vs API).

    Args:
        local_monthly_cost: Custo mensal da infraestrutura local
        api_cost_per_classification: Custo por classificação da API

    Returns:
        Classificações/dia para break-even
    """
    # local_cost = api_cost_per_classification * classifications_per_day * 30
    classifications_per_day = local_monthly_cost / (api_cost_per_classification * 30)
    return int(classifications_per_day)


def generate_comparison_report():
    """Gera relatório comparativo completo."""
    print("=" * 80)
    print("📊 COMPARAÇÃO: MODELOS LOCAIS vs API (CLAUDE HAIKU)")
    print("=" * 80)
    print()

    # Carregar resultados
    try:
        local_df, api_baseline = load_results()
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return

    # Melhor modelo local
    best_local = local_df.iloc[0]

    print("=" * 80)
    print("🏆 CAMPEÕES")
    print("=" * 80)
    print()

    print(f"API (Claude Haiku):")
    print(f"  L1: {api_baseline['L1_accuracy']:.1f}% | L2: {api_baseline['L2_accuracy']:.1f}% | L3: {api_baseline['L3_accuracy']:.1f}%")
    print(f"  Latência: {api_baseline['avg_latency_sec']:.2f}s")
    print(f"  Erros: {api_baseline['errors']}/200")
    print()

    print(f"Local ({best_local['model_name']}):")
    print(f"  L1: {best_local['L1_accuracy']:.1f}% | L2: {best_local['L2_accuracy']:.1f}% | L3: {best_local['L3_accuracy']:.1f}%")
    print(f"  Latência: {best_local['avg_latency_sec']:.2f}s")
    print(f"  Erros: {best_local['errors']}/200")
    print()

    # Gap de accuracy
    print("=" * 80)
    print("📉 GAP DE PERFORMANCE")
    print("=" * 80)
    print()

    gap_l1 = api_baseline['L1_accuracy'] - best_local['L1_accuracy']
    gap_l2 = api_baseline['L2_accuracy'] - best_local['L2_accuracy']
    gap_l3 = api_baseline['L3_accuracy'] - best_local['L3_accuracy']

    print(f"Diferença (API - Local):")
    print(f"  L1: {gap_l1:+.1f} pontos percentuais")
    print(f"  L2: {gap_l2:+.1f} pontos percentuais")
    print(f"  L3: {gap_l3:+.1f} pontos percentuais")
    print()

    # Análise de custo
    print("=" * 80)
    print("💰 ANÁLISE DE CUSTO")
    print("=" * 80)
    print()

    # Cenários de volume
    volumes = [1000, 5000, 10000, 50000]

    print("Cenário atual: 1000 classificações/dia")
    print()
    print(f"{'Volume/dia':<12} | {'API (Haiku)':<15} | {'Local (Reserved)':<20} | {'Melhor':<15}")
    print("-" * 80)

    for volume in volumes:
        api_cost = calculate_api_cost(volume)
        local_tco = calculate_tco(volume, best_local['avg_latency_sec'])

        api_monthly = api_cost['monthly_cost']
        local_monthly = local_tco['monthly_cost']['total_reserved']

        cheaper = "API" if api_monthly < local_monthly else "Local"
        savings = abs(api_monthly - local_monthly)

        print(f"{volume:<12,} | ${api_monthly:>12,.2f} | ${local_monthly:>17,.2f} | {cheaper:<8} (-${savings:,.0f})")

    print()

    # Break-even
    api_cost_per = 0.65 / 200
    local_tco_example = calculate_tco(5000, best_local['avg_latency_sec'])
    breakeven_reserved = find_breakeven(
        local_tco_example['monthly_cost']['total_reserved'],
        api_cost_per
    )
    breakeven_spot = find_breakeven(
        local_tco_example['monthly_cost']['total_spot'],
        api_cost_per
    )

    print("Break-even points:")
    print(f"  Reserved instance (g5.xlarge): ~{breakeven_reserved:,} classificações/dia")
    print(f"  Spot instance (g5.xlarge): ~{breakeven_spot:,} classificações/dia")
    print()

    # Recomendação
    print("=" * 80)
    print("🎯 RECOMENDAÇÃO")
    print("=" * 80)
    print()

    # Critérios de decisão
    accuracy_acceptable = best_local['L3_accuracy'] >= 60.0
    cost_competitive = breakeven_reserved <= 5000

    if best_local['L3_accuracy'] >= 70.0 and breakeven_reserved <= 5000:
        recommendation = "LOCAL"
        reason = "Accuracy competitiva (>70%) e TCO favorável para volumes médios"
    elif best_local['L3_accuracy'] >= 60.0 and breakeven_reserved <= 3000:
        recommendation = "LOCAL (para alto volume)"
        reason = f"Accuracy aceitável ({best_local['L3_accuracy']:.1f}%) compensa apenas acima de {breakeven_reserved:,}/dia"
    elif best_local['L3_accuracy'] >= 70.0:
        recommendation = "HÍBRIDO"
        reason = "Accuracy boa mas TCO só compensa em volumes muito altos. Considerar híbrido."
    else:
        recommendation = "API (Claude Haiku)"
        reason = f"Gap de accuracy muito grande ({gap_l3:.1f}pp) não justifica economia"

    print(f"✅ Recomendação: **{recommendation}**")
    print()
    print(f"Justificativa:")
    print(f"  {reason}")
    print()

    # Cenários de uso
    print("Quando usar cada abordagem:")
    print()
    print("📡 API (Claude Haiku):")
    print("  ✅ Volume baixo (<5k/dia)")
    print("  ✅ Prioridade em accuracy (80.5% L3)")
    print("  ✅ Menor complexidade operacional")
    print("  ✅ Sem investment inicial")
    print()

    print("🖥️  Local (melhor modelo):")
    print(f"  ✅ Volume alto (>{breakeven_reserved:,}/dia)")
    print("  ✅ Restrições de compliance/privacidade")
    print("  ✅ Latência crítica (<1s)")
    print(f"  ⚠️  Accuracy menor ({best_local['L3_accuracy']:.1f}% vs 80.5%)")
    print("  ⚠️  Requer DevOps (manutenção, monitoring)")
    print()

    print("🔀 Híbrido:")
    print("  ✅ Melhor dos dois mundos")
    print("  ✅ Local para bulk (overnight batch)")
    print("  ✅ API para casos críticos (online)")
    print("  ✅ Fallback automático se local falhar")
    print()

    # Salvar relatório
    report_path = BASE_DIR / "results" / "local_models" / "comparison_report.json"
    report = {
        'api_baseline': api_baseline,
        'best_local_model': {
            'name': best_local['model_name'],
            'L1_accuracy': float(best_local['L1_accuracy']),
            'L2_accuracy': float(best_local['L2_accuracy']),
            'L3_accuracy': float(best_local['L3_accuracy']),
            'avg_latency_sec': float(best_local['avg_latency_sec']),
            'errors': int(best_local['errors'])
        },
        'gap': {
            'L1': float(gap_l1),
            'L2': float(gap_l2),
            'L3': float(gap_l3)
        },
        'breakeven': {
            'reserved_instance_per_day': breakeven_reserved,
            'spot_instance_per_day': breakeven_spot
        },
        'recommendation': recommendation,
        'reason': reason
    }

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"📁 Relatório salvo em: {report_path}")
    print()

    print("=" * 80)
    print("✅ ANÁLISE COMPLETA!")
    print("=" * 80)
    print()


if __name__ == '__main__':
    generate_comparison_report()
