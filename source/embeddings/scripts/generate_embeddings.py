#!/usr/bin/env python3
"""
Generate embeddings for corpus documents using all models.

Loads the 250 curated documents and generates embeddings with each model.
Saves embeddings as .npy files for fast loading during evaluation.

Usage:
    python generate_embeddings.py [--models MODEL1 MODEL2 ...] [--device cuda|cpu]
"""

import json
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


# Import model definitions
from setup_models import MODELS


def load_corpus():
    """Load all corpus documents."""
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"

    documents = []
    doc_ids = []

    print("📂 Carregando corpus...")

    for json_file in sorted(corpus_dir.glob("doc_*.json")):
        with open(json_file) as f:
            doc = json.load(f)
            documents.append(doc['content'])
            doc_ids.append(doc['id'])

    print(f"✅ {len(documents)} documentos carregados")

    return documents, doc_ids


def generate_embeddings_for_model(
    model_id: str,
    model_info: Dict,
    documents: List[str],
    device: str = "cuda",
    batch_size: int = 32
) -> np.ndarray:
    """Generate embeddings for all documents using one model."""

    print(f"\n{'='*70}")
    print(f"🔧 {model_id.upper()}")
    print(f"{'='*70}")
    print(f"Modelo: {model_info['name']}")
    print(f"Dimensões: {model_info['dims']}")
    print(f"Batch size: {batch_size}")

    # Load model
    print("\n📦 Carregando modelo...")
    start_load = time.time()
    model = SentenceTransformer(model_info['name'], device=device)
    load_time = time.time() - start_load
    print(f"✅ Modelo carregado em {load_time:.2f}s")

    # Generate embeddings
    print(f"\n🔄 Gerando embeddings para {len(documents)} documentos...")
    start_encode = time.time()

    embeddings = model.encode(
        documents,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True  # Normalize for cosine similarity
    )

    encode_time = time.time() - start_encode

    # Stats
    docs_per_sec = len(documents) / encode_time
    avg_time_ms = (encode_time / len(documents)) * 1000

    print(f"\n✅ Embeddings gerados!")
    print(f"   Tempo total: {encode_time:.2f}s")
    print(f"   Throughput: {docs_per_sec:.1f} docs/s")
    print(f"   Tempo médio: {avg_time_ms:.1f}ms por documento")
    print(f"   Shape: {embeddings.shape}")

    # Free memory
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return embeddings, {
        "load_time": load_time,
        "encode_time": encode_time,
        "throughput": docs_per_sec,
        "avg_latency_ms": avg_time_ms
    }


def save_embeddings(
    model_id: str,
    embeddings: np.ndarray,
    doc_ids: List[str],
    stats: Dict
):
    """Save embeddings and metadata."""
    output_dir = Path(__file__).parent.parent / "results" / "embeddings"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save embeddings
    emb_file = output_dir / f"{model_id}_corpus.npy"
    np.save(emb_file, embeddings)
    print(f"💾 Embeddings salvos: {emb_file}")

    # Save document IDs mapping
    ids_file = output_dir / f"{model_id}_doc_ids.json"
    with open(ids_file, 'w') as f:
        json.dump(doc_ids, f, indent=2)
    print(f"💾 IDs salvos: {ids_file}")

    # Save stats
    stats_file = output_dir / f"{model_id}_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"💾 Stats salvos: {stats_file}")


def main():
    """Main generation routine."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate corpus embeddings")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Specific models to use (default: all)")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu",
                        choices=["cuda", "cpu"],
                        help="Device to use")
    parser.add_argument("--batch-size", type=int, default=32,
                        help="Batch size for encoding (default: 32)")

    args = parser.parse_args()

    print("="*70)
    print("🚀 GERAÇÃO DE EMBEDDINGS DO CORPUS")
    print("="*70)

    # Check GPU
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("⚠️  Usando CPU")

    device = args.device

    # Load corpus
    documents, doc_ids = load_corpus()

    # Select models
    models_to_use = args.models if args.models else list(MODELS.keys())

    print(f"\n📊 Modelos a processar: {len(models_to_use)}")
    print(f"📄 Documentos no corpus: {len(documents)}")
    print(f"🖥️  Device: {device.upper()}")
    print(f"📦 Batch size: {args.batch_size}")

    # Generate embeddings for each model
    all_stats = {}

    for i, model_id in enumerate(models_to_use, 1):
        if model_id not in MODELS:
            print(f"\n⚠️  Modelo '{model_id}' não encontrado, pulando...")
            continue

        model_info = MODELS[model_id]

        print(f"\n{'='*70}")
        print(f"📊 Progresso: {i}/{len(models_to_use)}")
        print(f"{'='*70}")

        try:
            embeddings, stats = generate_embeddings_for_model(
                model_id,
                model_info,
                documents,
                device=device,
                batch_size=args.batch_size
            )

            # Save
            save_embeddings(model_id, embeddings, doc_ids, stats)

            # Store stats
            all_stats[model_id] = {
                **stats,
                "status": "success",
                "model_name": model_info['name'],
                "dims": model_info['dims']
            }

        except Exception as e:
            print(f"\n❌ Erro ao processar {model_id}: {e}")
            all_stats[model_id] = {
                "status": "failed",
                "error": str(e)
            }
            continue

    # Save summary
    summary_file = Path(__file__).parent.parent / "results" / "embeddings" / "generation_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(all_stats, f, indent=2)

    print(f"\n{'='*70}")
    print("📊 RESUMO DA GERAÇÃO")
    print(f"{'='*70}")

    successful = [m for m, s in all_stats.items() if s['status'] == 'success']
    failed = [m for m, s in all_stats.items() if s['status'] == 'failed']

    print(f"\n✅ Modelos processados: {len(successful)}/{len(models_to_use)}")

    if successful:
        print(f"\n📈 Throughput por modelo:")
        for model_id in successful:
            throughput = all_stats[model_id]['throughput']
            print(f"   {model_id:25} → {throughput:6.1f} docs/s")

    if failed:
        print(f"\n❌ Modelos com erro: {', '.join(failed)}")

    print(f"\n💾 Resumo salvo em: {summary_file}")


if __name__ == "__main__":
    main()
