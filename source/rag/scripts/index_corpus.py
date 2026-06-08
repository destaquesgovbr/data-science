#!/usr/bin/env python3
"""
Index corpus into PostgreSQL + pgvector.

Loads documents from JSON/CSV and indexes them using the IndexingPipeline.

Usage:
    # Index from JSON
    python scripts/index_corpus.py --input data/corpus_sample.json --format json

    # Index from CSV with semantic chunking
    python scripts/index_corpus.py --input data/corpus.csv --format csv --chunker semantic

    # Enable contextual enrichment
    python scripts/index_corpus.py --input data/corpus.json --format json --enrich

    # Dry run (don't actually index)
    python scripts/index_corpus.py --input data/corpus.json --dry-run
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from datetime import datetime
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from dotenv import load_dotenv
import os

# Import RAG components
from src.indexing import (
    IndexingPipeline,
    load_documents_from_json,
    load_documents_from_csv
)
from src.chunking import create_chunker

# Import sentence transformers for embeddings
from sentence_transformers import SentenceTransformer

console = Console()


def load_config(config_dir: str = "config"):
    """Load all configuration files."""
    load_dotenv()

    configs = {}

    # Load database config
    with open(f"{config_dir}/database.yaml") as f:
        configs['database'] = yaml.safe_load(f)

    # Load embeddings config
    with open(f"{config_dir}/embeddings.yaml") as f:
        configs['embeddings'] = yaml.safe_load(f)

    # Load LLM config (for enrichment)
    with open(f"{config_dir}/llm.yaml") as f:
        configs['llm'] = yaml.safe_load(f)

    # Replace environment variables
    def replace_env_vars(obj):
        if isinstance(obj, dict):
            return {k: replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_env_vars(v) for v in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var_expr = obj[2:-1]
            if ":" in var_expr:
                var_name, default = var_expr.split(":", 1)
                return os.getenv(var_name, default)
            else:
                return os.getenv(var_expr, obj)
        else:
            return obj

    return {k: replace_env_vars(v) for k, v in configs.items()}


def get_connection_string(config: dict) -> str:
    """Build PostgreSQL connection string."""
    db_config = config['database']['database']

    return (
        f"host={db_config['host']} "
        f"port={db_config['port']} "
        f"dbname={db_config['name']} "
        f"user={db_config['user']} "
        f"password={db_config['password']}"
    )


def load_embedder(config: dict) -> SentenceTransformer:
    """Load embedding model (BGE-M3)."""
    console.print("\n[bold blue]Loading embedding model...[/bold blue]")

    emb_config = config['embeddings']
    model_name = emb_config['model']['name']
    device = emb_config['model']['device']

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Loading {model_name}...", total=None)

        model = SentenceTransformer(
            model_name,
            device=device,
            trust_remote_code=True
        )

        progress.update(task, completed=True)

    console.print(f"   ✓ Loaded {model_name} on {device}", style="green")
    console.print(f"   Dimension: {emb_config['specifications']['dimension']}")
    console.print(f"   Max tokens: {emb_config['specifications']['max_tokens']}")

    return model


def load_enrichment_llm(config: dict, enable_enrichment: bool):
    """Load LLM for contextual enrichment (optional)."""
    if not enable_enrichment:
        return None

    console.print("\n[bold blue]Loading LLM for enrichment...[/bold blue]")

    llm_config = config['llm']
    provider = llm_config['default_provider']

    console.print(f"   Provider: {provider}")

    # Placeholder - implement based on provider
    # For now, return None (enrichment will be skipped)
    console.print("   ⚠️  LLM enrichment not yet implemented", style="yellow")
    return None


def load_documents(input_path: str, format: str):
    """Load documents from file."""
    console.print(f"\n[bold blue]Loading documents from {input_path}...[/bold blue]")

    if format == 'json':
        documents = load_documents_from_json(input_path)
    elif format == 'csv':
        documents = load_documents_from_csv(input_path)
    else:
        raise ValueError(f"Unknown format: {format}")

    console.print(f"   ✓ Loaded {len(documents)} documents", style="green")

    # Show sample
    if documents:
        sample = documents[0]
        console.print(f"\n   Sample document:")
        console.print(f"   - Title: {sample.title[:80]}...")
        console.print(f"   - Content length: {len(sample.content)} chars")
        if sample.category:
            console.print(f"   - Category: {sample.category}")
        if sample.source_agency:
            console.print(f"   - Agency: {sample.source_agency}")

    return documents


def create_indexing_pipeline(
    config: dict,
    embedder,
    chunker_strategy: str,
    chunker_kwargs: dict,
    enable_enrichment: bool,
    enrichment_llm,
    batch_size: int
):
    """Create indexing pipeline."""
    console.print(f"\n[bold blue]Creating indexing pipeline...[/bold blue]")

    conn_string = get_connection_string(config)

    pipeline = IndexingPipeline(
        conn_string=conn_string,
        embedder=embedder,
        chunker_strategy=chunker_strategy,
        chunker_kwargs=chunker_kwargs,
        enable_enrichment=enable_enrichment,
        enrichment_llm=enrichment_llm,
        batch_size=batch_size
    )

    console.print(f"   ✓ Pipeline created", style="green")
    console.print(f"   - Chunker: {chunker_strategy}")
    console.print(f"   - Enrichment: {'enabled' if enable_enrichment else 'disabled'}")
    console.print(f"   - Batch size: {batch_size}")

    return pipeline


def index_corpus(
    pipeline,
    documents,
    skip_existing: bool,
    dry_run: bool
):
    """Index corpus using pipeline."""
    if dry_run:
        console.print(
            Panel.fit(
                "[bold yellow]DRY RUN MODE[/bold yellow]\n\n"
                "No documents will be indexed.\n"
                "This is a test run to validate configuration.",
                border_style="yellow"
            )
        )
        return {'total': len(documents), 'indexed': 0, 'skipped': 0, 'failed': 0, 'chunks_created': 0}

    console.print(
        Panel.fit(
            f"[bold cyan]Indexing {len(documents)} documents[/bold cyan]\n\n"
            f"Skip existing: {skip_existing}",
            border_style="cyan"
        )
    )

    start_time = datetime.now()

    # Index documents
    stats = pipeline.index_documents(
        documents,
        skip_existing=skip_existing,
        show_progress=True
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    # Display results
    console.print(
        Panel.fit(
            f"[bold green]✅ Indexing complete![/bold green]\n\n"
            f"Time: {elapsed:.1f}s\n"
            f"Indexed: {stats['indexed']} documents\n"
            f"Skipped: {stats['skipped']} documents\n"
            f"Failed: {stats['failed']} documents\n"
            f"Chunks created: {stats['chunks_created']}",
            border_style="green"
        )
    )

    return stats


def display_index_stats(pipeline):
    """Display index statistics."""
    console.print("\n[bold blue]Index Statistics:[/bold blue]")

    stats = pipeline.get_index_stats()

    # Create table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Documents", str(stats['total_documents']))
    table.add_row("Total Chunks", str(stats['total_chunks']))
    table.add_row("Avg Chunks/Document", f"{stats['avg_chunks_per_doc']:.1f}")

    if stats['latest_indexed']:
        table.add_row("Latest Indexed", stats['latest_indexed'].strftime("%Y-%m-%d %H:%M:%S"))

    console.print(table)

    # Documents by category
    if stats['documents_by_category']:
        console.print("\n[bold blue]Documents by Category:[/bold blue]")

        cat_table = Table(show_header=True, header_style="bold cyan")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Count", style="green")

        for row in stats['documents_by_category'][:10]:  # Top 10
            cat_table.add_row(row['category'] or 'Unknown', str(row['count']))

        console.print(cat_table)


def main():
    parser = argparse.ArgumentParser(
        description="Index corpus into PostgreSQL + pgvector",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input file path (JSON or CSV)"
    )

    parser.add_argument(
        "--format",
        choices=['json', 'csv'],
        default='json',
        help="Input file format"
    )

    parser.add_argument(
        "--chunker",
        choices=['fixed', 'semantic', 'paragraph', 'recursive'],
        default='semantic',
        help="Chunking strategy"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size in characters (for fixed/recursive)"
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap in characters (for fixed/recursive)"
    )

    parser.add_argument(
        "--semantic-threshold",
        type=float,
        default=0.8,
        help="Similarity threshold for semantic chunking"
    )

    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enable contextual enrichment (Anthropic pattern)"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embeddings"
    )

    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip documents that already exist (by URL)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run (don't actually index)"
    )

    parser.add_argument(
        "--config-dir",
        default="config",
        help="Configuration directory"
    )

    args = parser.parse_args()

    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]RAG Indexing Pipeline[/bold cyan]\n"
            "[dim]Issue #5: Q&A sobre Notícias Governamentais[/dim]",
            border_style="cyan"
        )
    )

    try:
        # Load configurations
        console.print(f"\n📋 Loading configurations from {args.config_dir}/")
        config = load_config(args.config_dir)

        # Load embedder (BGE-M3)
        embedder = load_embedder(config)

        # Load enrichment LLM (optional)
        enrichment_llm = load_enrichment_llm(config, args.enrich)

        # Load documents
        documents = load_documents(args.input, args.format)

        # Prepare chunker kwargs
        chunker_kwargs = {}
        if args.chunker == 'semantic':
            chunker_kwargs = {
                'embedder': embedder,
                'threshold': args.semantic_threshold
            }
        elif args.chunker in ['fixed', 'recursive']:
            chunker_kwargs = {
                'chunk_size': args.chunk_size,
                'chunk_overlap': args.chunk_overlap
            }

        # Create pipeline
        pipeline = create_indexing_pipeline(
            config=config,
            embedder=embedder,
            chunker_strategy=args.chunker,
            chunker_kwargs=chunker_kwargs,
            enable_enrichment=args.enrich,
            enrichment_llm=enrichment_llm,
            batch_size=args.batch_size
        )

        # Index corpus
        stats = index_corpus(
            pipeline=pipeline,
            documents=documents,
            skip_existing=args.skip_existing,
            dry_run=args.dry_run
        )

        # Display statistics
        if not args.dry_run:
            display_index_stats(pipeline)

        console.print(
            Panel.fit(
                "[bold green]✅ Success![/bold green]\n\n"
                "Next steps:\n"
                "1. Test retrieval: python scripts/test_retrieval.py\n"
                "2. Test generation: python scripts/test_generation.py",
                border_style="green"
            )
        )

    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
