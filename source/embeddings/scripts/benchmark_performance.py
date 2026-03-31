#!/usr/bin/env python3
"""
Benchmark embedding models performance.

Measures:
- Throughput (docs/second)
- Latency (P50, P95, P99)
- Memory usage (CPU and GPU)
- Batch size scaling

Usage:
    python benchmark_performance.py [--models MODEL1 ...] [--device cuda|cpu]
"""

import json
import time
from pathlib import Path
from typing import Dict, List
import gc
import os

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
import psutil

from setup_models import MODELS


def get_memory_usage():
    """Get current memory usage (MB)."""
    process = psutil.Process(os.getpid())

    # CPU memory
    mem_cpu = process.memory_info().rss / 1024**2  # MB

    # GPU memory
    mem_gpu = 0
    if torch.cuda.is_available():
        mem_gpu = torch.cuda.memory_allocated() / 1024**2  # MB

    return {
        'cpu_mb': mem_cpu,
        'gpu_mb': mem_gpu
    }


def benchmark_throughput(
    model: SentenceTransformer,
    documents: List[str],
    batch_size: int = 32,
    num_runs: int = 3
) -> Dict:
    """
    Measure encoding throughput.

    Args:
        model: Sentence transformer model
        documents: List of documents to encode
        batch_size: Batch size for encoding
        num_runs: Number of runs to average

    Returns:
        Dict with throughput statistics
    """

    times = []

    for run in range(num_runs):
        start = time.time()

        embeddings = model.encode(
            documents,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )

        elapsed = time.time() - start
        times.append(elapsed)

        # Free memory
        del embeddings
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Statistics
    avg_time = np.mean(times)
    throughput = len(documents) / avg_time

    return {
        'docs_per_second': throughput,
        'total_time_sec': avg_time,
        'time_per_doc_ms': (avg_time / len(documents)) * 1000,
        'num_docs': len(documents),
        'batch_size': batch_size,
        'num_runs': num_runs
    }


def benchmark_latency(
    model: SentenceTransformer,
    documents: List[str],
    num_samples: int = 100
) -> Dict:
    """
    Measure single-document encoding latency.

    Important for real-time / interactive applications.

    Args:
        model: Sentence transformer model
        documents: Documents to sample from
        num_samples: Number of documents to test

    Returns:
        Dict with latency statistics (P50, P95, P99)
    """

    # Sample documents
    sample_docs = np.random.choice(documents, size=min(num_samples, len(documents)), replace=False)

    latencies = []

    for doc in sample_docs:
        start = time.time()
        _ = model.encode(doc, convert_to_numpy=True)
        latency = time.time() - start
        latencies.append(latency * 1000)  # Convert to ms

    return {
        'mean_ms': np.mean(latencies),
        'median_ms': np.median(latencies),
        'p95_ms': np.percentile(latencies, 95),
        'p99_ms': np.percentile(latencies, 99),
        'min_ms': np.min(latencies),
        'max_ms': np.max(latencies),
        'num_samples': len(latencies)
    }


def benchmark_batch_scaling(
    model: SentenceTransformer,
    documents: List[str],
    batch_sizes: List[int] = [1, 4, 8, 16, 32, 64]
) -> Dict:
    """
    Test how throughput scales with batch size.

    Args:
        model: Sentence transformer model
        documents: Documents to encode
        batch_sizes: List of batch sizes to test

    Returns:
        Dict mapping batch_size -> throughput
    """

    # Use subset of documents (1000 docs)
    test_docs = documents[:min(1000, len(documents))]

    results = {}

    for bs in batch_sizes:
        try:
            start = time.time()

            _ = model.encode(
                test_docs,
                batch_size=bs,
                show_progress_bar=False,
                convert_to_numpy=True
            )

            elapsed = time.time() - start
            throughput = len(test_docs) / elapsed

            results[bs] = {
                'throughput': throughput,
                'time_sec': elapsed
            }

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except RuntimeError as e:
            # Likely OOM
            print(f"      ⚠️  Batch size {bs} falhou (OOM?)")
            results[bs] = {
                'throughput': None,
                'error': str(e)
            }
            break

    return results


def benchmark_model(
    model_id: str,
    model_info: Dict,
    documents: List[str],
    device: str = "cuda"
) -> Dict:
    """Run all benchmarks for one model."""

    print(f"\n{'='*70}")
    print(f"⚡ BENCHMARK - {model_id.upper()}")
    print(f"{'='*70}")
    print(f"Modelo: {model_info['name']}")

    # Measure memory before loading
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    mem_before = get_memory_usage()

    # Load model
    print("\n📦 Carregando modelo...")
    start_load = time.time()
    model = SentenceTransformer(model_info['name'], device=device)
    load_time = time.time() - start_load

    mem_after = get_memory_usage()
    mem_model = {
        'cpu_mb': mem_after['cpu_mb'] - mem_before['cpu_mb'],
        'gpu_mb': mem_after['gpu_mb'] - mem_before['gpu_mb']
    }

    print(f"✅ Modelo carregado em {load_time:.2f}s")
    print(f"   Memória CPU: {mem_model['cpu_mb']:.1f} MB")
    if device == 'cuda':
        print(f"   Memória GPU: {mem_model['gpu_mb']:.1f} MB")

    results = {
        'model_id': model_id,
        'model_name': model_info['name'],
        'device': device,
        'load_time_sec': load_time,
        'memory_usage': mem_model
    }

    # 1. Throughput
    print("\n⚡ Testando throughput...")
    throughput = benchmark_throughput(model, documents, batch_size=32, num_runs=3)
    results['throughput'] = throughput
    print(f"   {throughput['docs_per_second']:.1f} docs/s (batch_size=32)")

    # 2. Latency
    print("\n🕐 Testando latência...")
    latency = benchmark_latency(model, documents, num_samples=100)
    results['latency'] = latency
    print(f"   Média: {latency['mean_ms']:.1f}ms")
    print(f"   P95: {latency['p95_ms']:.1f}ms")
    print(f"   P99: {latency['p99_ms']:.1f}ms")

    # 3. Batch scaling
    print("\n📈 Testando escalabilidade de batch...")
    batch_scaling = benchmark_batch_scaling(model, documents)
    results['batch_scaling'] = batch_scaling

    print("   Batch Size → Throughput:")
    for bs, data in batch_scaling.items():
        if data['throughput']:
            print(f"      {bs:3d} → {data['throughput']:7.1f} docs/s")

    # Free memory
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()

    return results


def load_corpus_sample(num_docs: int = 250):
    """Load corpus documents for benchmarking."""
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"

    documents = []

    for json_file in sorted(corpus_dir.glob("doc_*.json"))[:num_docs]:
        with open(json_file) as f:
            doc = json.load(f)
            documents.append(doc['content'])

    print(f"✅ {len(documents)} documentos carregados para benchmark")

    return documents


def save_results(all_results: List[Dict]):
    """Save benchmark results."""
    output_dir = Path(__file__).parent.parent / "results" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save complete results
    results_file = output_dir / "benchmark_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n💾 Resultados salvos: {results_file}")

    # Create summary table
    print(f"\n{'='*70}")
    print("📊 RESUMO DE PERFORMANCE")
    print(f"{'='*70}\n")

    # Header
    print(f"{'Modelo':25} {'Throughput':>12} {'Latência P99':>12} {'Mem GPU':>10}")
    print(f"{'-'*25} {'-'*12} {'-'*12} {'-'*10}")

    # Rows
    for result in sorted(all_results, key=lambda x: x['throughput']['docs_per_second'], reverse=True):
        model = result['model_id']
        throughput = result['throughput']['docs_per_second']
        latency_p99 = result['latency']['p99_ms']
        mem_gpu = result['memory_usage']['gpu_mb']

        print(f"{model:25} {throughput:10.1f}/s {latency_p99:10.1f}ms {mem_gpu:9.1f}MB")


def main():
    """Main benchmark routine."""
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark model performance")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Models to benchmark (default: all)")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu",
                        choices=["cuda", "cpu"],
                        help="Device to use")
    parser.add_argument("--num-docs", type=int, default=250,
                        help="Number of documents for benchmark (default: 250)")

    args = parser.parse_args()

    print("="*70)
    print("⚡ BENCHMARK DE PERFORMANCE")
    print("="*70)

    # Check GPU
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("⚠️  Usando CPU")

    # Load documents
    documents = load_corpus_sample(num_docs=args.num_docs)

    # Select models
    models_to_bench = args.models if args.models else list(MODELS.keys())

    print(f"\n📊 Configuração:")
    print(f"   Modelos: {len(models_to_bench)}")
    print(f"   Documentos: {len(documents)}")
    print(f"   Device: {args.device.upper()}")

    # Benchmark each model
    all_results = []

    for i, model_id in enumerate(models_to_bench, 1):
        if model_id not in MODELS:
            print(f"\n⚠️  Modelo '{model_id}' não encontrado")
            continue

        model_info = MODELS[model_id]

        print(f"\n{'='*70}")
        print(f"📊 Progresso: {i}/{len(models_to_bench)}")
        print(f"{'='*70}")

        try:
            result = benchmark_model(
                model_id,
                model_info,
                documents,
                device=args.device
            )
            all_results.append(result)

        except Exception as e:
            print(f"\n❌ Erro ao fazer benchmark de {model_id}: {e}")
            continue

    if not all_results:
        print("\n❌ Nenhum modelo avaliado com sucesso")
        return

    # Save and display results
    save_results(all_results)

    print(f"\n{'='*70}")
    print("✅ BENCHMARK COMPLETO!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
