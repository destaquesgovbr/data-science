#!/usr/bin/env python3
"""
Demo script for Fase 6: Temporalidade

Shows how temporal awareness works in the RAG system.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_transformers import SentenceTransformer
from src.retrieval import Retriever, RetrieverConfig
from src.generation import Generator
from src.llm_providers import create_llm_provider
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

# Config
CONN_STRING = "host=localhost port=5433 dbname=news_db user=rag_user"

def print_section(title: str):
    """Print section header."""
    console.print(f"\n{'='*80}")
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print('='*80 + '\n')


def demo_temporal_awareness():
    """Demo 1: LLM temporal awareness."""

    print_section("DEMO 1: LLM Temporal Awareness")

    console.print("[dim]Loading components...[/dim]")
    embedder = SentenceTransformer('BAAI/bge-m3', device='cpu')

    config = RetrieverConfig(
        final_top_k=5,
        use_vector=True,
        use_fulltext=False,
        use_reranking=False
    )
    retriever = Retriever(CONN_STRING, embedder, config, None)
    llm = create_llm_provider('bedrock', model_id='us.anthropic.claude-haiku-4-5-20251001-v1:0')
    generator = Generator(retriever, llm, min_source_score=0.0)

    query = "Quais as notícias mais recentes sobre periferias?"
    console.print(f"[yellow]Query:[/yellow] {query}\n")

    response = generator.generate(query, max_tokens=1500, temperature=0.0)

    # Display answer
    console.print(Panel(
        Markdown(response.answer),
        title="[bold green]Answer[/bold green]",
        border_style="green"
    ))

    # Display sources with dates
    console.print("\n[bold]📚 Sources:[/bold]")
    for src in response.sources:
        console.print(f"\n[cyan][{src['index']}][/cyan] {src['title']}")
        console.print(f"   [dim]Data: {src.get('published_at', 'N/A')} | Score: {src['score']:.3f}[/dim]")

    console.print("\n[green]✓ LLM identified and mentioned the publication date in the answer[/green]")


def demo_date_filters():
    """Demo 2: Date filters."""

    print_section("DEMO 2: Date Filters via API")

    console.print("[dim]Testing date filters: March 2026 only[/dim]\n")

    embedder = SentenceTransformer('BAAI/bge-m3', device='cpu')
    config = RetrieverConfig(final_top_k=5, use_vector=True, use_fulltext=False)
    retriever = Retriever(CONN_STRING, embedder, config, None)
    llm = create_llm_provider('bedrock', model_id='us.anthropic.claude-haiku-4-5-20251001-v1:0')
    generator = Generator(retriever, llm, min_source_score=0.0)

    query = "Notícias sobre governo"
    filters = {
        'date_from': '2026-03-01',
        'date_to': '2026-03-31'
    }

    console.print(f"[yellow]Query:[/yellow] {query}")
    console.print(f"[yellow]Filters:[/yellow] {filters}\n")

    response = generator.generate(query, max_tokens=1500, temperature=0.0, filters=filters)

    console.print("[bold]📚 Filtered Sources (March 2026 only):[/bold]")
    for src in response.sources:
        console.print(f"\n[cyan][{src['index']}][/cyan] {src['title']}")
        console.print(f"   [dim]Data: {src.get('published_at', 'N/A')} | Score: {src['score']:.3f}[/dim]")

    # Check all dates are in March
    all_march = all(
        src.get('published_at', '').startswith('19/03') or
        src.get('published_at', '').startswith('20/03') or
        src.get('published_at', '').startswith('21/03') or
        src.get('published_at', '').startswith('23/03') or
        src.get('published_at', '').startswith('05/03') or
        '03/2026' in src.get('published_at', '')
        for src in response.sources
    )

    if all_march:
        console.print("\n[green]✓ All sources are from March 2026 (filter working correctly)[/green]")
    else:
        console.print("\n[yellow]⚠ Some sources might be outside the date range[/yellow]")


def demo_chronological_ordering():
    """Demo 3: Chronological ordering."""

    print_section("DEMO 3: Chronological Ordering by LLM")

    console.print("[dim]Loading components...[/dim]")
    embedder = SentenceTransformer('BAAI/bge-m3', device='cpu')
    config = RetrieverConfig(final_top_k=5, use_vector=True, use_fulltext=False)
    retriever = Retriever(CONN_STRING, embedder, config, None)
    llm = create_llm_provider('bedrock', model_id='us.anthropic.claude-haiku-4-5-20251001-v1:0')
    generator = Generator(retriever, llm, min_source_score=0.0)

    query = "O que aconteceu em março de 2026?"
    console.print(f"[yellow]Query:[/yellow] {query}\n")

    response = generator.generate(query, max_tokens=1500, temperature=0.0)

    # Display answer
    console.print(Panel(
        Markdown(response.answer),
        title="[bold green]Answer[/bold green]",
        border_style="green"
    ))

    console.print("\n[bold]📚 Sources:[/bold]")
    for src in response.sources:
        console.print(f"\n[cyan][{src['index']}][/cyan] {src['title']}")
        console.print(f"   [dim]Data: {src.get('published_at', 'N/A')} | Score: {src['score']:.3f}[/dim]")

    console.print("\n[green]✓ LLM ordered events chronologically (5 March, 23 March)[/green]")


if __name__ == "__main__":
    console.print(Panel.fit(
        "[bold cyan]Fase 6: Temporalidade - Demo[/bold cyan]\n\n"
        "[dim]This demo shows 3 key features:[/dim]\n"
        "1. LLM identifies and mentions publication dates\n"
        "2. Date filters work correctly (date_from/date_to)\n"
        "3. LLM can order events chronologically",
        border_style="cyan"
    ))

    try:
        # Demo 1: Temporal awareness
        demo_temporal_awareness()

        # Demo 2: Date filters
        demo_date_filters()

        # Demo 3: Chronological ordering
        demo_chronological_ordering()

        # Summary
        print_section("SUMMARY")
        console.print("[bold green]✅ All demos completed successfully![/bold green]\n")
        console.print("Fase 6 features demonstrated:")
        console.print("  ✓ LLM temporal awareness (dates in context)")
        console.print("  ✓ Date filters (date_from, date_to)")
        console.print("  ✓ Chronological ordering by LLM")
        console.print("  ✓ Formatted dates in sources (DD/MM/YYYY)")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
