#!/usr/bin/env python3
"""
Quick demo script showing RAG API in action.

Runs a few sample queries and displays results.
"""

import requests
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
import time

console = Console()

API_BASE_URL = "http://localhost:8000"

# Sample queries
DEMO_QUERIES = [
    "Qual foi o valor destinado ao Plano Safra 2025/2026?",
    "Quais ações o governo tomou relacionadas à saúde?",
    "O que foi anunciado sobre agricultura familiar?",
]


def send_query(query: str, show_sources: bool = True):
    """Send query and display results."""

    console.print(f"\n[bold cyan]Query:[/bold cyan] {query}\n")

    request_data = {
        "query": query,
        "top_k": 3,
        "use_reranking": True,
        "provider": "bedrock",
        "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "max_tokens": 1000,
        "temperature": 0.0
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/query",
            json=request_data,
            timeout=120
        )
        elapsed = time.time() - start_time

        if response.status_code != 200:
            console.print(f"[red]✗ Error: {response.status_code}[/red]")
            return

        data = response.json()

        # Display answer
        console.print(Panel(
            Markdown(data['answer']),
            title="[bold green]Answer[/bold green]",
            border_style="green"
        ))

        # Display sources (compact)
        if show_sources:
            console.print(f"\n[bold]📚 Sources ({len(data['sources'])}):[/bold]")
            for source in data['sources']:
                console.print(f"  [{source['index']}] {source['title'][:70]}... (score: {source['score']:.2f})")

        # Metrics
        console.print(
            f"\n[dim]⏱  {data['latency_ms']['total_ms']:.0f}ms total "
            f"({data['latency_ms']['retrieval_ms']:.0f}ms retrieval + {data['latency_ms']['generation_ms']:.0f}ms generation) "
            f"| {data.get('tokens_output', '?')} tokens"
        )
        if data.get('cost_usd'):
            console.print(f"[dim]💰 ${data['cost_usd']:.4f}[/dim]")

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Request failed: {e}[/red]")


def main():
    """Run demo."""

    console.print(Panel.fit(
        "[bold cyan]RAG API - Live Demo[/bold cyan]\n\n"
        "[dim]Running sample queries to demonstrate the system[/dim]",
        border_style="cyan"
    ))

    # Check API
    console.print("\n[dim]Checking API health...[/dim]")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            console.print("[green]✓ API is ready[/green]")
        else:
            console.print("[red]✗ API health check failed[/red]")
            return
    except:
        console.print("[red]✗ Cannot connect to API. Start with: python api/server.py[/red]")
        return

    # Show config
    console.print("\n[bold]Configuration:[/bold]")
    console.print("  Provider: AWS Bedrock")
    console.print("  Model: Claude Haiku 4.5")
    console.print("  Retrieval: BGE-M3 + Re-ranking (ms-marco)")
    console.print("  Top-K: 3 chunks")

    # Run queries
    console.print(f"\n{'='*80}")
    console.print("[bold]Running demo queries...[/bold]")
    console.print(f"{'='*80}")

    for i, query in enumerate(DEMO_QUERIES, 1):
        console.print(f"\n[bold yellow]Query {i}/{len(DEMO_QUERIES)}[/bold yellow]")
        send_query(query, show_sources=True)

        if i < len(DEMO_QUERIES):
            console.print(f"\n{'-'*80}")

    # Summary
    console.print(f"\n{'='*80}")
    console.print("[bold green]✓ Demo complete![/bold green]")
    console.print(f"{'='*80}\n")

    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Try the interactive client: [cyan]python api/client.py[/cyan]")
    console.print("  2. View API docs: [cyan]http://localhost:8000/docs[/cyan]")
    console.print("  3. Make custom requests using curl or Python requests")


if __name__ == "__main__":
    main()
