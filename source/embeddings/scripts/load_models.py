"""
Script para carregar e configurar modelos de embedding

Suporta:
- Modelos multilinguais (BGE-M3, E5, GTE)
- Modelos PT-BR específicos (Serafim, BERTimbau, Jina)
- Configuração unificada de parâmetros
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import torch
from sentence_transformers import SentenceTransformer


@dataclass
class ModelConfig:
    """Configuração de um modelo de embedding"""
    name: str
    model_id: str
    dimensions: int
    max_tokens: int
    parameters_millions: int
    category: str  # 'multilingual' ou 'pt-specific'
    notes: str = ""


# Definição de todos os modelos a serem testados
MODELS_TO_EVALUATE: List[ModelConfig] = [
    # Modelos Multilinguais
    ModelConfig(
        name="BGE-M3",
        model_id="BAAI/bge-m3",
        dimensions=1024,
        max_tokens=8192,
        parameters_millions=568,
        category="multilingual",
        notes="Multi-functionality: dense, sparse, colbert"
    ),
    ModelConfig(
        name="E5-Large-Multilingual",
        model_id="intfloat/multilingual-e5-large",
        dimensions=1024,
        max_tokens=512,
        parameters_millions=560,
        category="multilingual",
        notes="Weakly-supervised contrastive pre-training"
    ),
    ModelConfig(
        name="GTE-Multilingual-Base",
        model_id="Alibaba-NLP/gte-multilingual-base",
        dimensions=768,
        max_tokens=8192,
        parameters_millions=278,
        category="multilingual",
        notes="Long context support"
    ),
    ModelConfig(
        name="Paraphrase-Multilingual-MPNet",
        model_id="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        dimensions=768,
        max_tokens=128,
        parameters_millions=278,
        category="multilingual",
        notes="Classic sentence-transformers model"
    ),

    # Modelos PT-BR Específicos
    ModelConfig(
        name="BGE-Large-PT",
        model_id="BAAI/bge-large-pt",
        dimensions=1024,
        max_tokens=512,
        parameters_millions=560,
        category="pt-specific",
        notes="Portuguese-specific version of BGE"
    ),
    ModelConfig(
        name="BGE-Small-PT",
        model_id="BAAI/bge-small-pt",
        dimensions=384,
        max_tokens=512,
        parameters_millions=33,
        category="pt-specific",
        notes="Lightweight Portuguese model"
    ),
    ModelConfig(
        name="Serafim-900M",
        model_id="PORTULAN/serafim-900m-portuguese-pt",
        dimensions=1536,
        max_tokens=128,
        parameters_millions=900,
        category="pt-specific",
        notes="Large Portuguese encoder"
    ),
    ModelConfig(
        name="Serafim-335M",
        model_id="PORTULAN/serafim-335m-portuguese-pt",
        dimensions=1024,
        max_tokens=128,
        parameters_millions=335,
        category="pt-specific",
        notes="Medium Portuguese encoder"
    ),
    ModelConfig(
        name="Jina-V2-Base-PT",
        model_id="jinaai/jina-embeddings-v2-base-pt",
        dimensions=768,
        max_tokens=8192,
        parameters_millions=137,
        category="pt-specific",
        notes="Long context Portuguese model"
    ),
    ModelConfig(
        name="BERTimbau-Base",
        model_id="neuralmind/bert-base-portuguese-cased",
        dimensions=768,
        max_tokens=512,
        parameters_millions=110,
        category="pt-specific",
        notes="Classic BERT for Brazilian Portuguese"
    ),
]


def load_model(
    config: ModelConfig,
    device: Optional[str] = None,
    normalize_embeddings: bool = True
) -> SentenceTransformer:
    """
    Carrega um modelo de embedding

    Args:
        config: Configuração do modelo
        device: Device para carregar ('cuda', 'cpu', ou None para auto)
        normalize_embeddings: Se True, normaliza embeddings (recomendado para cosine similarity)

    Returns:
        Modelo carregado
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"Carregando {config.name} ({config.model_id})...")
    print(f"  Dimensões: {config.dimensions}")
    print(f"  Max tokens: {config.max_tokens}")
    print(f"  Categoria: {config.category}")
    print(f"  Device: {device}")

    try:
        model = SentenceTransformer(config.model_id, device=device)

        # Configurar normalização
        if normalize_embeddings:
            model.normalize_embeddings = True

        print(f"✓ {config.name} carregado com sucesso!")
        return model

    except Exception as e:
        print(f"✗ Erro ao carregar {config.name}: {e}")
        raise


def load_all_models(
    device: Optional[str] = None,
    categories: Optional[List[str]] = None
) -> Dict[str, Tuple[ModelConfig, SentenceTransformer]]:
    """
    Carrega todos os modelos (ou filtra por categoria)

    Args:
        device: Device para carregar modelos
        categories: Lista de categorias para filtrar (None = todas)

    Returns:
        Dict com {name: (config, model)}
    """
    models = {}

    configs_to_load = MODELS_TO_EVALUATE
    if categories:
        configs_to_load = [c for c in configs_to_load if c.category in categories]

    print(f"\n{'='*80}")
    print(f"CARREGANDO {len(configs_to_load)} MODELOS")
    print(f"{'='*80}\n")

    for config in configs_to_load:
        try:
            model = load_model(config, device=device)
            models[config.name] = (config, model)
            print()
        except Exception as e:
            print(f"⚠️  Pulando {config.name} devido a erro\n")
            continue

    print(f"{'='*80}")
    print(f"✓ {len(models)}/{len(configs_to_load)} modelos carregados com sucesso")
    print(f"{'='*80}\n")

    return models


def get_model_info() -> str:
    """Retorna informações sobre todos os modelos em formato de tabela"""

    lines = []
    lines.append("\n" + "="*100)
    lines.append("MODELOS DISPONÍVEIS PARA AVALIAÇÃO")
    lines.append("="*100)

    # Multilinguais
    lines.append("\n### MODELOS MULTILINGUAIS\n")
    lines.append(f"{'Nome':<35} {'Dims':<8} {'Tokens':<8} {'Params':<10} {'HuggingFace ID':<40}")
    lines.append("-"*100)

    for config in MODELS_TO_EVALUATE:
        if config.category == "multilingual":
            lines.append(
                f"{config.name:<35} "
                f"{config.dimensions:<8} "
                f"{config.max_tokens:<8} "
                f"{config.parameters_millions}M{'':<7} "
                f"{config.model_id:<40}"
            )

    # PT-específicos
    lines.append("\n### MODELOS PT-BR ESPECÍFICOS\n")
    lines.append(f"{'Nome':<35} {'Dims':<8} {'Tokens':<8} {'Params':<10} {'HuggingFace ID':<40}")
    lines.append("-"*100)

    for config in MODELS_TO_EVALUATE:
        if config.category == "pt-specific":
            lines.append(
                f"{config.name:<35} "
                f"{config.dimensions:<8} "
                f"{config.max_tokens:<8} "
                f"{config.parameters_millions}M{'':<7} "
                f"{config.model_id:<40}"
            )

    lines.append("\n" + "="*100 + "\n")

    return "\n".join(lines)


# CLI para testar
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Carregar modelos de embedding")
    parser.add_argument(
        "--category",
        choices=["multilingual", "pt-specific", "all"],
        default="all",
        help="Categoria de modelos para carregar"
    )
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="Device para carregar modelos"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Apenas mostrar informações dos modelos"
    )

    args = parser.parse_args()

    if args.info:
        print(get_model_info())
    else:
        device = None if args.device == "auto" else args.device
        categories = None if args.category == "all" else [args.category]

        models = load_all_models(device=device, categories=categories)

        # Teste rápido
        if models:
            print("\n🧪 TESTE RÁPIDO")
            print("="*80)

            test_sentence = "O governo anunciou novas medidas para educação."

            for name, (config, model) in list(models.items())[:3]:  # Testar apenas 3
                print(f"\n{name}:")
                embedding = model.encode(test_sentence, show_progress_bar=False)
                print(f"  Shape: {embedding.shape}")
                print(f"  Norm: {torch.linalg.norm(torch.tensor(embedding)):.4f}")
                print(f"  Sample: {embedding[:5]}")
