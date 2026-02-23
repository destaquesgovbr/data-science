"""
Script de Treino: BERT Fine-tuned para Classificação de Notícias

Este script treina um classificador BERT usando notícias JÁ CLASSIFICADAS
pelo Claude como dados de treino.

Workflow:
1. Carrega notícias classificadas (ex: do dataset enriquecido)
2. Prepara dados de treino/validação/teste
3. Fine-tune BERT português nas 410 categorias
4. Avalia performance
5. Salva modelo treinado

Requer:
- Notícias já classificadas (pode ser output do Claude)
- GPU recomendada (treino leva horas)
- ~16GB RAM
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração de paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Imports condicionais
try:
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer,
        DataCollatorWithPadding
    )
    from datasets import Dataset
    from sklearn.metrics import classification_report, accuracy_score
    TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    TRANSFORMERS_AVAILABLE = False
    print(f"⚠️  Dependências de ML não instaladas: {e}")
    print("Instale com: poetry install --extras ml")
    exit(1)


def load_classified_news(
    data_path: str,
    min_samples_per_category: int = 10
) -> Tuple[pl.DataFrame, Dict]:
    """
    Carrega notícias já classificadas.

    Args:
        data_path: Caminho para arquivo com notícias classificadas
        min_samples_per_category: Mínimo de exemplos por categoria

    Returns:
        DataFrame com notícias e dicionário de estatísticas
    """
    print("\n" + "="*80)
    print("CARREGANDO DADOS DE TREINO")
    print("="*80 + "\n")

    # Tentar carregar de diferentes fontes
    if Path(data_path).suffix == '.parquet':
        df = pl.read_parquet(data_path)
    elif Path(data_path).suffix == '.csv':
        df = pl.read_csv(data_path)
    else:
        raise ValueError(f"Formato não suportado: {Path(data_path).suffix}")

    print(f"✓ {len(df)} notícias carregadas")

    # Verificar colunas necessárias
    required_cols = ['title', 'content', 'most_specific_theme_label']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas faltando: {missing}")

    # Filtrar notícias com classificação válida
    df = df.filter(
        (pl.col('most_specific_theme_label').is_not_null()) &
        (pl.col('most_specific_theme_label') != '') &
        (pl.col('title').is_not_null()) &
        (pl.col('content').is_not_null())
    )

    print(f"✓ {len(df)} notícias com classificação válida")

    # Contar distribuição de categorias
    category_counts = (
        df.group_by('most_specific_theme_label')
        .count()
        .sort('count', descending=True)
    )

    print(f"\nDistribuição de categorias:")
    print(f"  Total de categorias únicas: {len(category_counts)}")
    print(f"  Mínimo por categoria: {category_counts['count'].min()}")
    print(f"  Máximo por categoria: {category_counts['count'].max()}")
    print(f"  Média por categoria: {category_counts['count'].mean():.1f}")

    # Filtrar categorias com poucos exemplos
    categories_to_keep = (
        category_counts
        .filter(pl.col('count') >= min_samples_per_category)
        ['most_specific_theme_label']
        .to_list()
    )

    df_filtered = df.filter(
        pl.col('most_specific_theme_label').is_in(categories_to_keep)
    )

    n_removed = len(df) - len(df_filtered)
    if n_removed > 0:
        print(f"\n⚠️  Removidas {n_removed} notícias de categorias com < {min_samples_per_category} exemplos")

    stats = {
        'total_news': len(df_filtered),
        'n_categories': len(categories_to_keep),
        'min_per_category': category_counts.filter(
            pl.col('most_specific_theme_label').is_in(categories_to_keep)
        )['count'].min(),
        'max_per_category': category_counts.filter(
            pl.col('most_specific_theme_label').is_in(categories_to_keep)
        )['count'].max(),
        'avg_per_category': len(df_filtered) / len(categories_to_keep)
    }

    print(f"\n✓ Dataset final:")
    print(f"  {stats['total_news']} notícias")
    print(f"  {stats['n_categories']} categorias")
    print(f"  {stats['avg_per_category']:.1f} exemplos/categoria (média)")

    return df_filtered, stats


def prepare_datasets(
    df: pl.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42
) -> Tuple[Dataset, Dataset, Dataset, Dict]:
    """
    Prepara datasets de treino/validação/teste.

    Args:
        df: DataFrame com notícias
        train_ratio: Proporção de treino
        val_ratio: Proporção de validação
        test_ratio: Proporção de teste
        seed: Seed para reprodutibilidade

    Returns:
        train_dataset, val_dataset, test_dataset, label_mapping
    """
    print("\n" + "="*80)
    print("PREPARANDO DATASETS")
    print("="*80 + "\n")

    # Criar label mapping
    unique_labels = df['most_specific_theme_label'].unique().sort().to_list()
    label2id = {label: idx for idx, label in enumerate(unique_labels)}
    id2label = {idx: label for label, idx in label2id.items()}

    print(f"✓ {len(label2id)} categorias mapeadas")

    # Adicionar coluna de texto completo e label_id
    df = df.with_columns([
        (pl.col('title') + ' ' + pl.col('content')).alias('text'),
        pl.col('most_specific_theme_label').map_dict(label2id).alias('label')
    ])

    # Shuffle
    df = df.sample(fraction=1.0, seed=seed, shuffle=True)

    # Split
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train_df = df[:train_end]
    val_df = df[train_end:val_end]
    test_df = df[val_end:]

    print(f"Split:")
    print(f"  Treino: {len(train_df)} ({len(train_df)/n*100:.1f}%)")
    print(f"  Validação: {len(val_df)} ({len(val_df)/n*100:.1f}%)")
    print(f"  Teste: {len(test_df)} ({len(test_df)/n*100:.1f}%)")

    # Converter para Hugging Face Dataset
    def to_hf_dataset(polars_df):
        return Dataset.from_dict({
            'text': polars_df['text'].to_list(),
            'label': polars_df['label'].to_list()
        })

    train_dataset = to_hf_dataset(train_df)
    val_dataset = to_hf_dataset(val_df)
    test_dataset = to_hf_dataset(test_df)

    label_mapping = {
        'label2id': label2id,
        'id2label': id2label,
        'n_labels': len(label2id)
    }

    print(f"\n✓ Datasets preparados")

    return train_dataset, val_dataset, test_dataset, label_mapping


def train_model(
    train_dataset: Dataset,
    val_dataset: Dataset,
    label_mapping: Dict,
    model_name: str = "neuralmind/bert-base-portuguese-cased",
    output_dir: str = None,
    num_epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5
):
    """
    Treina o modelo BERT.

    Args:
        train_dataset: Dataset de treino
        val_dataset: Dataset de validação
        label_mapping: Mapeamento de labels
        model_name: Nome do modelo base
        output_dir: Diretório de output
        num_epochs: Número de épocas
        batch_size: Tamanho do batch
        learning_rate: Taxa de aprendizado
    """
    print("\n" + "="*80)
    print("TREINANDO MODELO BERT")
    print("="*80 + "\n")

    if output_dir is None:
        output_dir = MODELS_DIR / "bert_news_classifier"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Carregar tokenizer e modelo
    print(f"Carregando modelo base: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=label_mapping['n_labels'],
        id2label=label_mapping['id2label'],
        label2id=label_mapping['label2id']
    )

    # Tokenizar datasets
    def tokenize_function(examples):
        return tokenizer(
            examples['text'],
            padding='max_length',
            truncation=True,
            max_length=512
        )

    print("Tokenizando datasets...")
    train_dataset = train_dataset.map(tokenize_function, batched=True)
    val_dataset = val_dataset.map(tokenize_function, batched=True)

    # Data collator
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        logging_dir=str(output_dir / "logs"),
        logging_steps=100,
        save_total_limit=2,
        fp16=torch.cuda.is_available(),  # Mixed precision se GPU
    )

    # Métricas
    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        return {
            'accuracy': accuracy_score(labels, predictions)
        }

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    # Treinar
    print(f"\nIniciando treino ({num_epochs} épocas)...")
    print("⏰ Isso pode levar várias horas dependendo do hardware\n")

    trainer.train()

    # Salvar modelo final
    print(f"\n✓ Treino concluído!")
    print(f"Salvando modelo em: {output_dir}")

    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Salvar label mapping
    with open(output_dir / "label_mapping.json", 'w', encoding='utf-8') as f:
        json.dump(label_mapping, f, ensure_ascii=False, indent=2)

    print(f"✓ Modelo salvo com sucesso!")

    return trainer


def evaluate_model(
    trainer: Trainer,
    test_dataset: Dataset,
    label_mapping: Dict
):
    """Avalia modelo no conjunto de teste."""
    print("\n" + "="*80)
    print("AVALIANDO MODELO")
    print("="*80 + "\n")

    # Predições
    predictions = trainer.predict(test_dataset)
    pred_labels = np.argmax(predictions.predictions, axis=1)
    true_labels = predictions.label_ids

    # Acurácia
    accuracy = accuracy_score(true_labels, pred_labels)
    print(f"Acurácia no teste: {accuracy*100:.2f}%")

    # Relatório por categoria (top-20)
    print(f"\nRelatório detalhado (primeiras 20 categorias):")
    print("-" * 80)

    id2label = label_mapping['id2label']
    target_names = [id2label[i] for i in range(min(20, len(id2label)))]

    # Filtrar apenas labels que aparecem no teste
    mask = (true_labels < 20) & (pred_labels < 20)
    if mask.sum() > 0:
        report = classification_report(
            true_labels[mask],
            pred_labels[mask],
            target_names=target_names,
            zero_division=0
        )
        print(report)

    return {
        'accuracy': accuracy,
        'n_test_samples': len(true_labels)
    }


def main():
    """Função principal."""
    print("\n" + "="*80)
    print("TREINO BERT: Classificador de Notícias")
    print("="*80)
    print()
    print("Este script treina um classificador BERT usando notícias")
    print("já classificadas como dados de treino.")
    print()

    # Configuração
    DATA_FILE = DATA_DIR / "govbrnews_enriched.parquet"  # Ajustar conforme necessário
    MIN_SAMPLES = 10  # Mínimo de exemplos por categoria
    NUM_EPOCHS = 3
    BATCH_SIZE = 16

    print("Configuração:")
    print(f"  Arquivo de dados: {DATA_FILE}")
    print(f"  Mínimo de exemplos/categoria: {MIN_SAMPLES}")
    print(f"  Épocas: {NUM_EPOCHS}")
    print(f"  Batch size: {BATCH_SIZE}")
    print()

    # Verificar se arquivo existe
    if not DATA_FILE.exists():
        print(f"⚠️  Arquivo não encontrado: {DATA_FILE}")
        print()
        print("Para treinar o modelo, você precisa de notícias classificadas.")
        print("Opções:")
        print("  1. Use o Claude para classificar um dataset")
        print("  2. Ou especifique outro arquivo com --data-file")
        print()
        print("Exemplo:")
        print("  python train_bert_classifier.py --data-file data/meu_dataset.parquet")
        return

    # 1. Carregar dados
    df, stats = load_classified_news(str(DATA_FILE), MIN_SAMPLES)

    if stats['total_news'] < 1000:
        print(f"\n⚠️  AVISO: Apenas {stats['total_news']} exemplos de treino")
        print("Para bons resultados, recomenda-se > 10.000 exemplos")
        print()
        resp = input("Continuar mesmo assim? (s/n): ")
        if resp.lower() != 's':
            print("Treino cancelado")
            return

    # 2. Preparar datasets
    train_ds, val_ds, test_ds, label_map = prepare_datasets(df)

    # 3. Treinar
    trainer = train_model(
        train_ds,
        val_ds,
        label_map,
        num_epochs=NUM_EPOCHS,
        batch_size=BATCH_SIZE
    )

    # 4. Avaliar
    eval_results = evaluate_model(trainer, test_ds, label_map)

    print("\n" + "="*80)
    print("TREINO CONCLUÍDO!")
    print("="*80)
    print()
    print(f"Acurácia final: {eval_results['accuracy']*100:.2f}%")
    print(f"Modelo salvo em: {MODELS_DIR / 'bert_news_classifier'}")
    print()
    print("Para usar o modelo:")
    print("  from news_enrichment.classifier_bert import NewsClassifierBERT")
    print("  classifier = NewsClassifierBERT(model_path='models/bert_news_classifier')")
    print()


if __name__ == "__main__":
    main()
