#!/usr/bin/env python3
"""
Complete evaluation pipeline for embedding models.

Orchestrates the full evaluation workflow:
1. Setup and validate models
2. Generate corpus embeddings
3. Run semantic search
4. Calculate metrics
5. Benchmark performance
6. Generate report

Usage:
    python run_evaluation.py [--models MODEL1 ...] [--skip-setup] [--skip-bench]
"""

import sys
import subprocess
from pathlib import Path
import time
import json


def run_command(cmd: list, description: str) -> bool:
    """Run a command and handle errors."""
    print(f"\n{'='*70}")
    print(f"▶️  {description}")
    print(f"{'='*70}")
    print(f"Comando: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent,
            check=True,
            text=True
        )
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erro ao executar: {description}")
        print(f"   Código de saída: {e.returncode}")
        return False


def check_prerequisites():
    """Check if prerequisites are met."""
    print("🔍 Verificando pré-requisitos...\n")

    checks = []

    # 1. Check corpus
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    num_docs = len(list(corpus_dir.glob("doc_*.json")))
    if num_docs == 250:
        print(f"   ✅ Corpus: {num_docs} documentos")
        checks.append(True)
    else:
        print(f"   ❌ Corpus: esperado 250 docs, encontrado {num_docs}")
        checks.append(False)

    # 2. Check queries
    query_file = Path(__file__).parent.parent / "data" / "query_template_85.json"
    if query_file.exists():
        with open(query_file) as f:
            queries = json.load(f)

        # Count filled queries
        filled = sum(1 for q in queries if q.get('query_text', '').strip() or q.get('recommended_query', '').strip())

        if filled >= 50:  # At least 50 queries
            print(f"   ✅ Queries: {filled}/85 preenchidas")
            checks.append(True)
        else:
            print(f"   ⚠️  Queries: {filled}/85 preenchidas (mínimo 50 recomendado)")
            checks.append(False)
    else:
        print(f"   ❌ Queries: arquivo não encontrado")
        checks.append(False)

    # 3. Check ground truth (not blocking, just warning)
    gt_file = Path(__file__).parent.parent / "data" / "annotations" / "ground_truth.json"
    if gt_file.exists():
        print(f"   ✅ Ground truth: encontrado")
    else:
        print(f"   ⚠️  Ground truth: NÃO encontrado")
        print(f"      (necessário para calcular métricas)")

    return all(checks)


def main():
    """Main evaluation pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run complete embedding evaluation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full evaluation for all models
  python run_evaluation.py

  # Evaluate specific models only
  python run_evaluation.py --models bge-m3 serafim bertimbau

  # Skip model setup (if already done)
  python run_evaluation.py --skip-setup

  # Skip benchmarks (focus on retrieval metrics)
  python run_evaluation.py --skip-bench

  # Run only search and metrics (embeddings already generated)
  python run_evaluation.py --skip-setup --skip-embeddings --skip-bench
        """
    )

    parser.add_argument("--models", nargs="+", default=None,
                        help="Specific models to evaluate (default: all)")
    parser.add_argument("--skip-setup", action="store_true",
                        help="Skip model setup (assume already done)")
    parser.add_argument("--skip-embeddings", action="store_true",
                        help="Skip embedding generation (assume already done)")
    parser.add_argument("--skip-search", action="store_true",
                        help="Skip semantic search (assume already done)")
    parser.add_argument("--skip-bench", action="store_true",
                        help="Skip performance benchmarks")
    parser.add_argument("--skip-metrics", action="store_true",
                        help="Skip metrics calculation (requires ground truth)")
    parser.add_argument("--device", default=None,
                        choices=["cuda", "cpu"],
                        help="Device to use (default: auto-detect)")

    args = parser.parse_args()

    # Header
    print("="*70)
    print("🚀 PIPELINE DE AVALIAÇÃO DE EMBEDDINGS")
    print("="*70)
    print(f"\nIniciado em: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Pré-requisitos não atendidos!")
        print("   Execute os scripts de preparação primeiro.")
        return 1

    # Build model argument
    models_arg = []
    if args.models:
        models_arg = ["--models"] + args.models

    # Build device argument
    device_arg = []
    if args.device:
        device_arg = ["--device", args.device]

    # Track which steps ran
    steps_run = []
    steps_failed = []

    start_time = time.time()

    # Step 1: Setup models
    if not args.skip_setup:
        success = run_command(
            ["python", "setup_models.py"] + models_arg + device_arg,
            "PASSO 1: Setup e Validação de Modelos"
        )
        steps_run.append("Setup")
        if not success:
            steps_failed.append("Setup")
            print("\n⚠️  Setup falhou, mas continuando...")

    # Step 2: Generate embeddings
    if not args.skip_embeddings:
        success = run_command(
            ["python", "generate_embeddings.py"] + models_arg + device_arg,
            "PASSO 2: Geração de Embeddings do Corpus"
        )
        steps_run.append("Embeddings")
        if not success:
            steps_failed.append("Embeddings")
            print("\n❌ Geração de embeddings falhou!")
            print("   Não é possível continuar sem embeddings.")
            return 1

    # Step 3: Semantic search
    if not args.skip_search:
        success = run_command(
            ["python", "semantic_search.py"] + models_arg + device_arg,
            "PASSO 3: Busca Semântica"
        )
        steps_run.append("Search")
        if not success:
            steps_failed.append("Search")
            print("\n❌ Busca semântica falhou!")
            return 1

    # Step 4: Calculate metrics (only if ground truth exists)
    if not args.skip_metrics:
        gt_file = Path(__file__).parent.parent / "data" / "annotations" / "ground_truth.json"

        if gt_file.exists():
            success = run_command(
                ["python", "evaluate_metrics.py"] + models_arg,
                "PASSO 4: Cálculo de Métricas (NDCG, MAP, MRR)"
            )
            steps_run.append("Metrics")
            if not success:
                steps_failed.append("Metrics")
                print("\n⚠️  Cálculo de métricas falhou")
        else:
            print(f"\n{'='*70}")
            print("⚠️  PASSO 4: Métricas - PULADO")
            print(f"{'='*70}")
            print("\nGround truth não encontrado!")
            print("Execute o script de anotação primeiro para calcular métricas.")

    # Step 5: Performance benchmarks
    if not args.skip_bench:
        success = run_command(
            ["python", "benchmark_performance.py"] + models_arg + device_arg,
            "PASSO 5: Benchmark de Performance"
        )
        steps_run.append("Benchmark")
        if not success:
            steps_failed.append("Benchmark")
            print("\n⚠️  Benchmark falhou")

    # Summary
    elapsed = time.time() - start_time
    elapsed_min = elapsed / 60

    print(f"\n{'='*70}")
    print("🏁 PIPELINE COMPLETO!")
    print(f"{'='*70}")
    print(f"\nTempo total: {elapsed_min:.1f} minutos")
    print(f"\nPassos executados: {', '.join(steps_run)}")

    if steps_failed:
        print(f"⚠️  Passos com falha: {', '.join(steps_failed)}")

    # Next steps
    print(f"\n{'='*70}")
    print("📊 PRÓXIMOS PASSOS")
    print(f"{'='*70}\n")

    results_dir = Path(__file__).parent.parent / "results"

    # Check what's available
    has_embeddings = (results_dir / "embeddings").exists()
    has_search = (results_dir / "search_results").exists()
    has_metrics = (results_dir / "metrics").exists()
    has_bench = (results_dir / "benchmarks").exists()

    if has_search and not has_metrics:
        print("⚠️  Você tem resultados de busca mas não tem métricas calculadas!")
        print("   Execute:")
        print("   1. Crie o ground truth (anotação de relevância)")
        print("   2. python evaluate_metrics.py")

    if has_metrics:
        metrics_file = results_dir / "metrics" / "metrics_summary.csv"
        if metrics_file.exists():
            print("✅ Métricas disponíveis em:")
            print(f"   {metrics_file}")

    if has_bench:
        bench_file = results_dir / "benchmarks" / "benchmark_results.json"
        if bench_file.exists():
            print("✅ Benchmarks disponíveis em:")
            print(f"   {bench_file}")

    if has_metrics and has_bench:
        print("\n🎉 Avaliação completa!")
        print("   Próximo passo: Analisar resultados e escolher modelo vencedor")

    return 0 if not steps_failed else 1


if __name__ == "__main__":
    sys.exit(main())
