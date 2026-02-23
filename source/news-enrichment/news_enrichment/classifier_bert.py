"""
NewsClassifierBERT - Classificador baseado em BERT Fine-tuned

Este módulo implementa um classificador usando BERT português fine-tuned
para as 410 categorias da taxonomia.

Workflow:
1. Treino: Fine-tune BERT em notícias já classificadas
2. Inferência: BERT classifica diretamente (sem LLM)

Características:
+ Inferência rápida (~50-100ms por notícia)
+ Roda 100% local (sem API)
+ Custo zero por notícia
- Precisa de dados de treino
- Menos flexível que LLM
- Precisa re-treinar se taxonomia mudar

Nota: Este é um classificador supervisionado tradicional.
Requer dados rotulados para treino.
"""

import json
import logging
import pickle
from typing import Dict, List, Optional, Union
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        pipeline
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "transformers/torch não disponível. "
        "Instale com: poetry install --extras ml"
    )


class NewsClassifierBERT:
    """
    Classificador de notícias baseado em BERT fine-tuned.

    Usa BERT português (neuralmind) fine-tuned nas 410 categorias.

    Exemplo de uso:
        # Carregar modelo treinado
        classifier = NewsClassifierBERT(
            model_path="models/bert_news_classifier"
        )

        # Classificar
        result = classifier.classify_single({
            'title': 'Governo anuncia reforma tributária',
            'content': 'Medida visa simplificar...'
        })
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = "neuralmind/bert-base-portuguese-cased",
        device: str = "auto",
        batch_size: int = 32,
        max_length: int = 512,
        verbose: bool = False
    ):
        """
        Inicializa o classificador BERT.

        Args:
            model_path: Caminho para modelo fine-tuned (se já treinado)
            model_name: Nome do modelo base (se não tem modelo treinado)
            device: Device para inferência ('cpu', 'cuda', ou 'auto')
            batch_size: Tamanho do batch para processamento
            max_length: Comprimento máximo de tokens
            verbose: Habilitar logs detalhados
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers e torch são necessários. "
                "Instale com: poetry install --extras ml"
            )

        self.verbose = verbose
        self.batch_size = batch_size
        self.max_length = max_length

        # Determinar device
        if device == "auto":
            self.device = 0 if torch.cuda.is_available() else -1
        elif device == "cuda":
            self.device = 0
        else:
            self.device = -1

        if verbose:
            device_name = "GPU" if self.device == 0 else "CPU"
            logger.info(f"Usando device: {device_name}")

        # Carregar modelo e tokenizer
        if model_path and Path(model_path).exists():
            if verbose:
                logger.info(f"Carregando modelo fine-tuned: {model_path}")
            self._load_finetuned_model(model_path)
        else:
            if verbose:
                logger.info(f"Carregando modelo base: {model_name}")
                logger.info("⚠️  Modelo não está fine-tuned ainda")
            self._load_base_model(model_name)

    def _load_finetuned_model(self, model_path: str):
        """Carrega modelo já fine-tuned."""
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)

        # Carregar label mapping
        label_map_path = Path(model_path) / "label_mapping.json"
        if label_map_path.exists():
            with open(label_map_path, 'r', encoding='utf-8') as f:
                self.label_mapping = json.load(f)
            self.id2label = {int(k): v for k, v in self.label_mapping['id2label'].items()}
            self.label2id = self.label_mapping['label2id']
        else:
            logger.warning("label_mapping.json não encontrado")
            self.id2label = {}
            self.label2id = {}

        # Criar pipeline
        self.pipeline = pipeline(
            "text-classification",
            model=self.model,
            tokenizer=self.tokenizer,
            device=self.device,
            return_all_scores=True
        )

        if self.verbose:
            logger.info(f"✓ Modelo carregado: {len(self.id2label)} categorias")

    def _load_base_model(self, model_name: str):
        """Carrega modelo base (não treinado)."""
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = None  # Precisa fine-tunar primeiro
        self.pipeline = None
        self.id2label = {}
        self.label2id = {}

        logger.warning(
            "Modelo base carregado mas NÃO está fine-tuned. "
            "Use train_bert_classifier.py para treinar."
        )

    def classify_single(
        self,
        news: Dict,
        return_format: str = "json",
        top_k: int = 3
    ) -> Union[Dict, str]:
        """
        Classifica uma única notícia.

        Args:
            news: Dicionário com 'title' e 'content'
            return_format: 'json' ou 'dict'
            top_k: Retornar top-k categorias mais prováveis

        Returns:
            Dict ou JSON string com classificação
        """
        if self.pipeline is None:
            raise RuntimeError(
                "Modelo não está fine-tuned. "
                "Treine o modelo primeiro com train_bert_classifier.py"
            )

        # Preparar texto
        text = f"{news.get('title', '')} {news.get('content', '')}"
        text = text[:self.max_length * 4]  # Limitar tamanho

        # Classificar
        predictions = self.pipeline(text, top_k=top_k)

        # Processar resultado
        result = {
            'unique_id': news.get('unique_id', ''),
            'title': news.get('title', ''),
            'approach': 'bert_finetuned',
            'predictions': []
        }

        for pred in predictions[0]:
            label_id = int(pred['label'].split('_')[-1])  # LABEL_123 -> 123
            category = self.id2label.get(label_id, 'unknown')

            result['predictions'].append({
                'category': category,
                'confidence': pred['score']
            })

        # Adicionar categoria principal
        if result['predictions']:
            top_pred = result['predictions'][0]
            result['most_specific_theme_label'] = top_pred['category']
            result['confidence'] = top_pred['confidence']

            # Parse hierarquia (se formato for "Nivel1 > Nivel2 > Nivel3")
            if ' > ' in top_pred['category']:
                parts = top_pred['category'].split(' > ')
                result['theme_1_level_1_label'] = parts[0] if len(parts) > 0 else ''
                result['theme_1_level_2_label'] = parts[1] if len(parts) > 1 else ''
                result['theme_1_level_3_label'] = parts[2] if len(parts) > 2 else ''

        if return_format == "json":
            return json.dumps(result, ensure_ascii=False, indent=2)
        return result

    def classify_batch(
        self,
        news_list: List[Dict],
        return_format: str = "list"
    ) -> Union[List[Dict], str]:
        """
        Classifica múltiplas notícias.

        Args:
            news_list: Lista de dicionários com notícias
            return_format: 'list' ou 'json'

        Returns:
            Lista de resultados ou JSON string
        """
        results = []

        # Processar em batches
        for i in range(0, len(news_list), self.batch_size):
            batch = news_list[i:i + self.batch_size]

            for news in batch:
                try:
                    result = self.classify_single(news, return_format="dict")
                    results.append(result)
                except Exception as e:
                    logger.error(f"Erro ao classificar: {e}")
                    results.append({
                        'unique_id': news.get('unique_id', ''),
                        'error': str(e)
                    })

        if return_format == "json":
            return json.dumps(results, ensure_ascii=False, indent=2)
        return results

    def get_stats(self) -> Dict:
        """Retorna estatísticas do classificador."""
        return {
            'approach': 'BERT Fine-tuned',
            'model_loaded': self.pipeline is not None,
            'n_categories': len(self.id2label),
            'device': 'GPU' if self.device == 0 else 'CPU',
            'batch_size': self.batch_size,
            'max_length': self.max_length
        }


def demo():
    """Demonstração de uso do classificador BERT."""
    print("=" * 80)
    print("DEMO: Classificador BERT Fine-tuned")
    print("=" * 80)
    print()

    print("⚠️  Este classificador precisa ser treinado primeiro!")
    print()
    print("Para treinar:")
    print("  1. Classifique notícias com Claude (gera dados de treino)")
    print("  2. Execute: python train_bert_classifier.py")
    print("  3. Use este classificador com modelo treinado")
    print()
    print("Vantagens após treino:")
    print("  ✓ Inferência rápida (~50-100ms)")
    print("  ✓ Roda local (sem API)")
    print("  ✓ Custo zero por notícia")
    print()
    print("Ver: train_bert_classifier.py para detalhes de treino")


if __name__ == "__main__":
    demo()
