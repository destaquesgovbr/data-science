#!/usr/bin/env python3
"""
Fine-tuning LEVE para CPU - versão otimizada.

Mudanças para rodar em CPU:
- Batch size menor (8 vs 16)
- Precision reduzida (float16 quando possível)
- Menos evaluation steps
- Dataset menor (100-200 triplas para teste)

Usage:
    python finetune_model_light.py --dataset fewshot --max-samples 200
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, InputExample, losses
from sentence_transformers.evaluation import InformationRetrievalEvaluator
from torch.utils.data import DataLoader

# Configuração
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "finetuning"
MODELS_DIR = BASE_DIR / "models"


def load_triplets(dataset_type='fewshot', max_samples=None):
    """Carrega triplas (com limite opcional para CPU)."""
    print(f"📂 Carregando dataset: {dataset_type}")

    # Train
    if dataset_type == 'fewshot':
        train_file = DATA_DIR / "train_fewshot.csv"
    else:
        train_file = DATA_DIR / "train.csv"

    train_df = pd.read_csv(train_file)

    # Limitar samples para CPU
    if max_samples and len(train_df) > max_samples:
        train_df = train_df.sample(n=max_samples, random_state=42)
        print(f"  ⚠️  Limitado a {max_samples} amostras para treino em CPU")

    # Validation (sempre usar menos para economizar)
    val_file = DATA_DIR / "val.csv"
    val_df = pd.read_csv(val_file)
    if len(val_df) > 100:
        val_df = val_df.sample(n=100, random_state=42)

    print(f"  ✅ Train: {len(train_df)} triplas")
    print(f"  ✅ Val: {len(val_df)} triplas")

    # Converter para InputExample
    train_examples = []
    for _, row in train_df.iterrows():
        train_examples.append(
            InputExample(texts=[row['query'], row['positive'], row['negative']])
        )

    # Validation data
    val_queries = {}
    val_corpus = {}
    val_relevant_docs = {}

    doc_id = 0
    for idx, row in val_df.iterrows():
        query_id = f"q{idx}"
        pos_id = f"pos_{doc_id}"
        neg_id = f"neg_{doc_id}"
        doc_id += 1

        val_queries[query_id] = row['query']
        val_corpus[pos_id] = row['positive']
        val_corpus[neg_id] = row['negative']
        val_relevant_docs[query_id] = {pos_id}

    return train_examples, (val_queries, val_corpus, val_relevant_docs)


def create_evaluator(val_queries, val_corpus, val_relevant_docs, name='val'):
    """Cria evaluator otimizado."""
    return InformationRetrievalEvaluator(
        queries=val_queries,
        corpus=val_corpus,
        relevant_docs=val_relevant_docs,
        name=name,
        show_progress_bar=False,  # Desabilitar para economizar
        batch_size=32
    )


def finetune_light(
    base_model='BAAI/bge-m3',
    dataset_type='fewshot',
    max_samples=200,
    epochs=1,  # Apenas 1 época para CPU
    batch_size=8,  # Menor para CPU
    learning_rate=2e-5,
    warmup_steps=20,
    output_path=None,
    evaluation_steps=100  # Avaliar menos frequentemente
):
    """Fine-tuning otimizado para CPU."""

    print("=" * 80)
    print("FINE-TUNING LEVE (CPU-OPTIMIZED)")
    print("=" * 80)
    print()

    # Device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"🖥️  Device: {device}")
    if device == 'cpu':
        print("  ⚠️  Modo CPU: treino será lento (~2-4h para 200 samples)")
    print()

    # Load model
    print(f"📥 Carregando modelo base: {base_model}")
    model = SentenceTransformer(base_model, device=device)
    print(f"  ✅ Modelo carregado")
    print()

    # Load dataset
    train_examples, val_data = load_triplets(dataset_type, max_samples=max_samples)
    val_queries, val_corpus, val_relevant_docs = val_data
    print()

    # DataLoader
    train_dataloader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=batch_size
    )

    print(f"🔧 Configuração de treino (otimizada para CPU):")
    print(f"  Épocas: {epochs}")
    print(f"  Batch size: {batch_size}")
    print(f"  Learning rate: {learning_rate}")
    print(f"  Samples: {len(train_examples)}")
    print(f"  Steps por época: {len(train_dataloader)}")
    print(f"  Total steps: {len(train_dataloader) * epochs}")
    print()

    # Loss
    train_loss = losses.MultipleNegativesRankingLoss(model)
    print(f"📉 Loss: MultipleNegativesRankingLoss")
    print()

    # Evaluator
    evaluator = create_evaluator(val_queries, val_corpus, val_relevant_docs)

    # Output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = MODELS_DIR / f"bge-m3-light-{timestamp}"
    else:
        output_path = Path(output_path)

    output_path.mkdir(parents=True, exist_ok=True)

    print(f"💾 Modelo será salvo em: {output_path}")
    print()

    # Training
    print("🚀 Iniciando treinamento (modo leve)...")
    print("=" * 80)

    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=epochs,
        warmup_steps=warmup_steps,
        evaluator=evaluator,
        evaluation_steps=evaluation_steps,
        output_path=str(output_path),
        save_best_model=True,
        show_progress_bar=True,
        optimizer_params={'lr': learning_rate}
    )

    print()
    print("=" * 80)
    print("✅ TREINAMENTO CONCLUÍDO!")
    print("=" * 80)
    print()

    # Save config
    config = {
        'base_model': base_model,
        'dataset_type': dataset_type,
        'max_samples': max_samples,
        'epochs': epochs,
        'batch_size': batch_size,
        'learning_rate': learning_rate,
        'device': device,
        'timestamp': datetime.now().isoformat(),
        'note': 'CPU-optimized version'
    }

    with open(output_path / 'training_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print(f"📁 Modelo salvo em: {output_path}")
    print()
    print("⚠️  NOTA: Este é um modelo de teste (poucas amostras/épocas)")
    print("   Não espere ganhos significativos. Use para validar pipeline.")
    print()

    return output_path


def main():
    parser = argparse.ArgumentParser(description='Fine-tuning leve (CPU)')

    parser.add_argument('--base-model', type=str, default='BAAI/bge-m3')
    parser.add_argument('--dataset', type=str, choices=['fewshot', 'full'], default='fewshot')
    parser.add_argument('--max-samples', type=int, default=200, help='Limite de samples (CPU)')
    parser.add_argument('--epochs', type=int, default=1, help='Épocas (default: 1 para CPU)')
    parser.add_argument('--batch-size', type=int, default=8, help='Batch size menor para CPU')
    parser.add_argument('--output', type=str, default=None)

    args = parser.parse_args()

    finetune_light(
        base_model=args.base_model,
        dataset_type=args.dataset,
        max_samples=args.max_samples,
        epochs=args.epochs,
        batch_size=args.batch_size,
        output_path=args.output
    )


if __name__ == "__main__":
    main()
