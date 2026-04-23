#!/usr/bin/env python3
"""
Fine-tuning de modelos de embedding com sentence-transformers.

Treina modelo base (ex: BGE-M3) com triplas (query, positive, negative)
usando Multiple Negatives Ranking Loss.

Usage:
    # Few-shot (500 triplas)
    python finetune_model.py --dataset fewshot --epochs 2 --output models/bge-m3-fewshot

    # Full dataset (1668 triplas)
    python finetune_model.py --dataset full --epochs 3 --output models/bge-m3-full
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


def load_triplets(dataset_type='fewshot'):
    """
    Carrega triplas de treino.

    Args:
        dataset_type: 'fewshot' (500) ou 'full' (1668)

    Returns:
        train_examples, val_data (para evaluation)
    """
    print(f"📂 Carregando dataset: {dataset_type}")

    # Train
    if dataset_type == 'fewshot':
        train_file = DATA_DIR / "train_fewshot.csv"
    else:
        train_file = DATA_DIR / "train.csv"

    train_df = pd.read_csv(train_file)

    # Validation
    val_file = DATA_DIR / "val.csv"
    val_df = pd.read_csv(val_file)

    print(f"  ✅ Train: {len(train_df)} triplas")
    print(f"  ✅ Val: {len(val_df)} triplas")

    # Converter para InputExample (formato sentence-transformers)
    train_examples = []
    for _, row in train_df.iterrows():
        train_examples.append(
            InputExample(
                texts=[row['query'], row['positive'], row['negative']]
            )
        )

    # Validation data para InformationRetrievalEvaluator
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
        val_relevant_docs[query_id] = {pos_id}  # Apenas positive é relevante

    return train_examples, (val_queries, val_corpus, val_relevant_docs)


def create_evaluator(val_queries, val_corpus, val_relevant_docs, name='val'):
    """
    Cria evaluator para validation durante treino.

    Calcula NDCG@10, MAP, MRR, Recall@10 no validation set.
    """
    return InformationRetrievalEvaluator(
        queries=val_queries,
        corpus=val_corpus,
        relevant_docs=val_relevant_docs,
        name=name,
        show_progress_bar=True
    )


def finetune(
    base_model='BAAI/bge-m3',
    dataset_type='fewshot',
    epochs=2,
    batch_size=16,
    learning_rate=2e-5,
    warmup_steps=100,
    output_path=None,
    evaluation_steps=50
):
    """
    Fine-tuning do modelo de embedding.

    Args:
        base_model: Modelo base do HuggingFace
        dataset_type: 'fewshot' ou 'full'
        epochs: Número de épocas
        batch_size: Batch size para treino
        learning_rate: Learning rate
        warmup_steps: Steps de warmup
        output_path: Onde salvar modelo treinado
        evaluation_steps: Avaliar a cada N steps
    """

    print("=" * 80)
    print("FINE-TUNING DE MODELO DE EMBEDDING")
    print("=" * 80)
    print()

    # Device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"🖥️  Device: {device}")
    if device == 'cuda':
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print()

    # Load base model
    print(f"📥 Carregando modelo base: {base_model}")
    model = SentenceTransformer(base_model, device=device)
    print(f"  ✅ Modelo carregado")
    print(f"  📊 Dimensão: {model.get_sentence_embedding_dimension()}")
    print(f"  📏 Max sequence length: {model.max_seq_length}")
    print()

    # Load dataset
    train_examples, val_data = load_triplets(dataset_type)
    val_queries, val_corpus, val_relevant_docs = val_data
    print()

    # DataLoader
    train_dataloader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=batch_size
    )

    print(f"🔧 Configuração de treino:")
    print(f"  Épocas: {epochs}")
    print(f"  Batch size: {batch_size}")
    print(f"  Learning rate: {learning_rate}")
    print(f"  Warmup steps: {warmup_steps}")
    print(f"  Steps por época: {len(train_dataloader)}")
    print(f"  Total steps: {len(train_dataloader) * epochs}")
    print()

    # Loss function
    train_loss = losses.MultipleNegativesRankingLoss(model)

    print(f"📉 Loss function: MultipleNegativesRankingLoss")
    print(f"   (Aproxima query de positive, afasta de negative)")
    print()

    # Evaluator
    evaluator = create_evaluator(val_queries, val_corpus, val_relevant_docs)

    # Output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = MODELS_DIR / f"bge-m3-{dataset_type}-{timestamp}"
    else:
        output_path = Path(output_path)

    output_path.mkdir(parents=True, exist_ok=True)

    print(f"💾 Modelo será salvo em: {output_path}")
    print()

    # Training
    print("🚀 Iniciando treinamento...")
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
    print(f"📁 Modelo salvo em: {output_path}")
    print()

    # Save training config
    config = {
        'base_model': base_model,
        'dataset_type': dataset_type,
        'epochs': epochs,
        'batch_size': batch_size,
        'learning_rate': learning_rate,
        'warmup_steps': warmup_steps,
        'train_samples': len(train_examples),
        'val_samples': len(val_queries),
        'device': device,
        'timestamp': datetime.now().isoformat()
    }

    with open(output_path / 'training_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print("📝 Configuração salva em: training_config.json")
    print()
    print("Próximos passos:")
    print("  1. Avaliar modelo no test set: python evaluate_finetuned.py")
    print("  2. Comparar com zero-shot baseline (Issue #1)")
    print("  3. Análise qualitativa de casos de sucesso/falha")
    print()

    return output_path


def main():
    parser = argparse.ArgumentParser(description='Fine-tuning de modelo de embedding')

    parser.add_argument(
        '--base-model',
        type=str,
        default='BAAI/bge-m3',
        help='Modelo base do HuggingFace (default: BAAI/bge-m3)'
    )

    parser.add_argument(
        '--dataset',
        type=str,
        choices=['fewshot', 'full'],
        default='fewshot',
        help='Dataset: fewshot (500) ou full (1668) triplas'
    )

    parser.add_argument(
        '--epochs',
        type=int,
        default=2,
        help='Número de épocas (default: 2)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=16,
        help='Batch size (default: 16)'
    )

    parser.add_argument(
        '--learning-rate',
        type=float,
        default=2e-5,
        help='Learning rate (default: 2e-5)'
    )

    parser.add_argument(
        '--warmup-steps',
        type=int,
        default=100,
        help='Warmup steps (default: 100)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Caminho para salvar modelo (default: auto-gerado)'
    )

    parser.add_argument(
        '--evaluation-steps',
        type=int,
        default=50,
        help='Avaliar a cada N steps (default: 50)'
    )

    args = parser.parse_args()

    # Run fine-tuning
    finetune(
        base_model=args.base_model,
        dataset_type=args.dataset,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        warmup_steps=args.warmup_steps,
        output_path=args.output,
        evaluation_steps=args.evaluation_steps
    )


if __name__ == "__main__":
    main()
