#!/usr/bin/env python3
"""
Setup and validation of embedding models.

Downloads and tests all 8 models defined in ROTEIRO_TESTES_EMBEDDINGS.md:
- Group A: Multilingual (3 models)
- Group B: PT-BR Specific (3 models)
- Group C: Smaller/Fast (2 models)

Usage:
    python setup_models.py [--test-only] [--device cuda|cpu]
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import time

import torch
from sentence_transformers import SentenceTransformer


# Model definitions from ROTEIRO
MODELS = {
    # Group A: Multilingual (Distilled)
    "bge-m3": {
        "name": "BAAI/bge-m3",
        "dims": 1024,
        "max_tokens": 8192,
        "params": "568M",
        "group": "multilingual"
    },
    "multilingual-e5-large": {
        "name": "intfloat/multilingual-e5-large",
        "dims": 1024,
        "max_tokens": 512,
        "params": "560M",
        "group": "multilingual"
    },
    "multilingual-e5-base": {
        "name": "intfloat/multilingual-e5-base",
        "dims": 768,
        "max_tokens": 512,
        "params": "278M",
        "group": "multilingual"
    },
    "labse": {
        "name": "sentence-transformers/LaBSE",
        "dims": 768,
        "max_tokens": 512,
        "params": "471M",
        "group": "multilingual"
    },

    # Group B: PT-BR Specific
    "serafim": {
        "name": "PORTULAN/serafim-900m-portuguese-pt-sentence-encoder",
        "dims": 1536,
        "max_tokens": 512,
        "params": "900M",
        "group": "pt-specific"
    },
    "bertimbau": {
        "name": "neuralmind/bert-base-portuguese-cased",
        "dims": 768,
        "max_tokens": 512,
        "params": "110M",
        "group": "pt-specific"
    },
    "legal-bertimbau": {
        "name": "rufimelo/Legal-BERTimbau-sts-base",
        "dims": 768,
        "max_tokens": 512,
        "params": "110M",
        "group": "pt-specific"
    },

    # Group C: Smaller (Fast)
    "paraphrase-miniml": {
        "name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dims": 384,
        "max_tokens": 512,
        "params": "118M",
        "group": "small"
    },
    "paraphrase-mpnet": {
        "name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "dims": 768,
        "max_tokens": 512,
        "params": "278M",
        "group": "multilingual"
    },
    "multilingual-e5-small": {
        "name": "intfloat/multilingual-e5-small",
        "dims": 384,
        "max_tokens": 512,
        "params": "118M",
        "group": "small"
    },
}


def check_gpu():
    """Check GPU availability."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"✅ GPU disponível: {gpu_name}")
        return True
    else:
        print("⚠️  GPU não disponível, usando CPU")
        return False


def load_model(model_id: str, model_info: Dict, device: str = "cuda") -> SentenceTransformer:
    """Load a single model."""
    print(f"\n📦 Carregando: {model_id}")
    print(f"   Modelo: {model_info['name']}")
    print(f"   Grupo: {model_info['group']}")
    print(f"   Dimensões: {model_info['dims']}")

    try:
        start_time = time.time()
        model = SentenceTransformer(model_info['name'], device=device)
        load_time = time.time() - start_time

        print(f"   ✅ Carregado em {load_time:.2f}s")
        return model

    except Exception as e:
        print(f"   ❌ Erro ao carregar: {e}")
        return None


def test_model(model_id: str, model: SentenceTransformer, model_info: Dict):
    """Test model with sample texts."""
    print(f"\n🧪 Testando: {model_id}")

    # Test sentences
    test_sentences = [
        "MEC anuncia distribuição do PNLD",
        "Ministério da Educação divulga calendário",
        "SUS amplia vacinação contra COVID-19",
        "Ministério da Saúde inicia campanha",
    ]

    try:
        # Generate embeddings
        start_time = time.time()
        embeddings = model.encode(test_sentences, show_progress_bar=False)
        encode_time = time.time() - start_time

        # Validate dimensions
        expected_dims = model_info['dims']
        actual_dims = embeddings.shape[1]

        if actual_dims != expected_dims:
            print(f"   ⚠️  Dimensões: esperado {expected_dims}, obtido {actual_dims}")
        else:
            print(f"   ✅ Dimensões corretas: {actual_dims}")

        # Calculate similarity between related sentences
        from sklearn.metrics.pairwise import cosine_similarity
        sim_mec = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        sim_sus = cosine_similarity([embeddings[2]], [embeddings[3]])[0][0]

        print(f"   Similaridade 'MEC' vs 'Ministério da Educação': {sim_mec:.3f}")
        print(f"   Similaridade 'SUS' vs 'Ministério da Saúde': {sim_sus:.3f}")
        print(f"   Tempo de encoding (4 sentenças): {encode_time*1000:.1f}ms")

        # Check if model understands Portuguese semantics
        if sim_mec > 0.5 and sim_sus > 0.5:
            print(f"   ✅ Modelo entende semântica PT-BR")
            return True
        else:
            print(f"   ⚠️  Similaridades baixas, verificar modelo")
            return False

    except Exception as e:
        print(f"   ❌ Erro no teste: {e}")
        return False


def save_model_info(results: Dict):
    """Save model setup results."""
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "models_setup.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Resultados salvos em: {output_file}")


def main():
    """Main setup routine."""
    import argparse

    parser = argparse.ArgumentParser(description="Setup embedding models")
    parser.add_argument("--test-only", action="store_true",
                        help="Only test models, don't download")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu",
                        choices=["cuda", "cpu"],
                        help="Device to use (cuda or cpu)")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Specific models to setup (default: all)")

    args = parser.parse_args()

    print("="*70)
    print("🚀 SETUP DE MODELOS DE EMBEDDING")
    print("="*70)

    # Check GPU
    has_gpu = check_gpu()
    device = args.device

    if device == "cuda" and not has_gpu:
        print("⚠️  CUDA solicitado mas GPU não disponível, usando CPU")
        device = "cpu"

    print(f"\n📊 Modelos a configurar: {len(MODELS)}")
    print(f"🖥️  Device: {device.upper()}")

    # Select models to setup
    models_to_setup = args.models if args.models else list(MODELS.keys())

    results = {
        "device": device,
        "has_gpu": has_gpu,
        "models": {}
    }

    # Setup each model
    success_count = 0
    failed_models = []

    for model_id in models_to_setup:
        if model_id not in MODELS:
            print(f"\n⚠️  Modelo '{model_id}' não encontrado, pulando...")
            continue

        model_info = MODELS[model_id]

        print(f"\n{'='*70}")
        print(f"🔧 {model_id.upper()}")
        print(f"{'='*70}")

        # Load model
        model = load_model(model_id, model_info, device=device)

        if model is None:
            failed_models.append(model_id)
            results["models"][model_id] = {
                "status": "failed",
                "error": "Failed to load model"
            }
            continue

        # Test model
        test_passed = test_model(model_id, model, model_info)

        if test_passed:
            success_count += 1
            results["models"][model_id] = {
                "status": "success",
                "name": model_info['name'],
                "group": model_info['group'],
                "dims": model_info['dims'],
                "max_tokens": model_info['max_tokens'],
            }
        else:
            failed_models.append(model_id)
            results["models"][model_id] = {
                "status": "warning",
                "error": "Tests failed or low similarity"
            }

        # Free memory
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Summary
    print(f"\n{'='*70}")
    print("📊 RESUMO DO SETUP")
    print(f"{'='*70}")
    print(f"\n✅ Modelos configurados com sucesso: {success_count}/{len(models_to_setup)}")

    if failed_models:
        print(f"❌ Modelos com problemas: {', '.join(failed_models)}")
    else:
        print("🎉 Todos os modelos configurados com sucesso!")

    # Save results
    save_model_info(results)

    # Exit code
    sys.exit(0 if len(failed_models) == 0 else 1)


if __name__ == "__main__":
    main()
