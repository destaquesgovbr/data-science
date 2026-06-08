#!/usr/bin/env python3
"""
Test retrieval pipeline.

Tests:
1. Vector search only
2. Full-text search only
3. Hybrid (RRF fusion)
4. Hybrid + Re-ranking

Validates:
- Results are returned
- Scores are reasonable
- Categories match expectations
- Latency is acceptable
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import argparse

from src.retrieval import Retriever, RetrieverConfig
from src.reranking import create_reranker

console = Console()


def load_test_queries(file_path: str) -> List[Dict]:
    """Load test queries from JSON."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_single_query(
    retriever: Retriever,
    query_data: Dict,
    show_results: bool = True
):
    """Test retrieval for a single query."""

    query = query_data['query']

    console.print(f"\n[bold cyan]Query:[/bold cyan] {query}")
    console.print(f"[dim]Expected category: {query_data.get('expected_category', 'N/A')}[/dim]")
    console.print(f"[dim]Type: {query_data.get('type', 'N/A')}, Difficulty: {query_data.get('difficulty', 'N/A')}[/dim]")

    # Measure latency
    start = time.time()
    results = retriever.retrieve(query)
    latency = (time.time() - start) * 1000  # ms

    console.print(f"\n[green]✓ Retrieved {len(results)} results in {latency:.0f}ms[/green]")

    if not results:
        console.print("[yellow]⚠ No results returned[/yellow]")
        return {
            'query': query,
            'num_results': 0,
            'latency_ms': latency,
            'top_score': 0,
            'category_match': False
        }

    # Analyze results
    top_score = results[0].score
    top_category = results[0].doc_category
    expected_category = query_data.get('expected_category')

    category_match = (top_category == expected_category) if expected_category else None

    # Show top results
    if show_results:
        table = Table(show_header=True, header_style="bold cyan", width=120)
        table.add_column("#", width=3)
        table.add_column("Score", width=8)
        table.add_column("Category", width=15)
        table.add_column("Agency", width=15)
        table.add_column("Content Preview", width=70)

        for i, result in enumerate(results[:5], 1):
            score_str = f"{result.score:.3f}"
            content_preview = result.content[:100].replace('\n', ' ') + "..."

            # Highlight expected category
            category_str = result.doc_category or "N/A"
            if result.doc_category == expected_category:
                category_str = f"[green]{category_str}[/green]"

            table.add_row(
                str(i),
                score_str,
                category_str,
                result.doc_agency or "N/A",
                content_preview
            )

        console.print(table)

    # Metrics
    metrics = {
        'query': query,
        'num_results': len(results),
        'latency_ms': latency,
        'top_score': top_score,
        'top_category': top_category,
        'expected_category': expected_category,
        'category_match': category_match
    }

    return metrics


def test_retrieval_methods(
    conn_string: str,
    embedder,
    query: str,
    top_k: int = 5
):
    """Compare different retrieval methods."""

    console.print(f"\n[bold cyan]Comparing Retrieval Methods[/bold cyan]")
    console.print(f"Query: {query}\n")

    methods = [
        ('Vector Only', RetrieverConfig(use_vector=True, use_fulltext=False, final_top_k=top_k)),
        ('Full-text Only', RetrieverConfig(use_vector=False, use_fulltext=True, final_top_k=top_k)),
        ('Hybrid (RRF)', RetrieverConfig(use_vector=True, use_fulltext=True, final_top_k=top_k)),
    ]

    results_by_method = {}

    for method_name, config in methods:
        retriever = Retriever(conn_string, embedder, config)

        start = time.time()
        results = retriever.retrieve(query)
        latency = (time.time() - start) * 1000

        results_by_method[method_name] = {
            'results': results,
            'latency': latency
        }

        console.print(f"[green]{method_name}:[/green] {len(results)} results in {latency:.0f}ms")

    # Compare results
    console.print("\n[bold]Top 3 Results Comparison:[/bold]\n")

    for i in range(min(3, top_k)):
        console.print(f"[bold cyan]Rank {i+1}:[/bold cyan]")

        for method_name in results_by_method:
            data = results_by_method[method_name]
            results = data['results']

            if i < len(results):
                result = results[i]
                preview = result.content[:80].replace('\n', ' ')
                console.print(f"  {method_name:20s} [{result.doc_category}] {preview}...")
            else:
                console.print(f"  {method_name:20s} (no result)")

        console.print()


def run_benchmark(
    conn_string: str,
    embedder,
    queries_file: str,
    config: RetrieverConfig,
    reranker = None
):
    """Run benchmark on all test queries."""

    console.print(Panel.fit(
        "[bold cyan]Retrieval Pipeline Benchmark[/bold cyan]\n"
        "[dim]Testing multi-stage retrieval[/dim]",
        border_style="cyan"
    ))

    # Load queries
    console.print(f"\n📋 Loading queries from {queries_file}")
    queries = load_test_queries(queries_file)
    console.print(f"   ✓ Loaded {len(queries)} test queries")

    # Initialize retriever
    console.print("\n🔧 Initializing retriever...")
    retriever = Retriever(conn_string, embedder, config, reranker)
    console.print("   ✓ Retriever ready")

    # Run tests
    console.print(f"\n🚀 Running retrieval tests...")

    all_metrics = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Testing queries...", total=len(queries))

        for query_data in queries:
            metrics = test_single_query(retriever, query_data, show_results=False)
            all_metrics.append(metrics)
            progress.advance(task)

    # Aggregate metrics
    console.print("\n" + "="*80)
    console.print("[bold cyan]📊 Benchmark Results[/bold cyan]")
    console.print("="*80)

    total_queries = len(all_metrics)
    avg_latency = sum(m['latency_ms'] for m in all_metrics) / total_queries
    avg_results = sum(m['num_results'] for m in all_metrics) / total_queries
    avg_score = sum(m['top_score'] for m in all_metrics) / total_queries

    # Category match rate (only for queries with expected category)
    category_metrics = [m for m in all_metrics if m.get('category_match') is not None]
    if category_metrics:
        category_match_rate = sum(m['category_match'] for m in category_metrics) / len(category_metrics)
    else:
        category_match_rate = None

    # Print summary
    console.print(f"\n[bold]Overall Metrics:[/bold]")
    console.print(f"  Total queries:        {total_queries}")
    console.print(f"  Avg latency:          {avg_latency:.0f}ms")
    console.print(f"  Avg results returned: {avg_results:.1f}")
    console.print(f"  Avg top score:        {avg_score:.3f}")

    if category_match_rate is not None:
        console.print(f"  Category match rate:  {category_match_rate:.1%}")

    # Latency breakdown
    latencies = [m['latency_ms'] for m in all_metrics]
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) > 10 else latencies[-1]

    console.print(f"\n[bold]Latency Distribution:[/bold]")
    console.print(f"  P50:  {p50:.0f}ms")
    console.print(f"  P95:  {p95:.0f}ms")
    console.print(f"  P99:  {p99:.0f}ms")

    # Show individual results
    console.print(f"\n[bold]Individual Query Results:[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", width=3)
    table.add_column("Query", width=40)
    table.add_column("Results", width=8)
    table.add_column("Latency", width=10)
    table.add_column("Top Score", width=10)
    table.add_column("Category", width=15)

    for i, metrics in enumerate(all_metrics, 1):
        category_str = metrics.get('top_category', 'N/A')
        if metrics.get('category_match'):
            category_str = f"[green]{category_str}[/green]"
        elif metrics.get('category_match') is False:
            category_str = f"[yellow]{category_str}[/yellow]"

        table.add_row(
            str(i),
            metrics['query'][:40],
            str(metrics['num_results']),
            f"{metrics['latency_ms']:.0f}ms",
            f"{metrics['top_score']:.3f}",
            category_str
        )

    console.print(table)

    # Final verdict
    console.print("\n" + "="*80)

    if avg_latency < 100 and category_match_rate and category_match_rate > 0.7:
        console.print("[bold green]✅ Retrieval pipeline performing well![/bold green]")
    elif avg_latency < 200:
        console.print("[bold yellow]⚠ Retrieval pipeline functional but could be improved[/bold yellow]")
    else:
        console.print("[bold red]❌ Retrieval pipeline needs optimization[/bold red]")

    console.print("="*80)


def main():
    parser = argparse.ArgumentParser(description="Test retrieval pipeline")

    parser.add_argument(
        '--queries',
        default='data/test_queries.json',
        help='Path to test queries JSON'
    )

    parser.add_argument(
        '--mode',
        choices=['benchmark', 'compare', 'interactive'],
        default='benchmark',
        help='Test mode'
    )

    parser.add_argument(
        '--query',
        help='Single query to test (for compare/interactive mode)'
    )

    parser.add_argument(
        '--top-k',
        type=int,
        default=5,
        help='Number of results to return'
    )

    parser.add_argument(
        '--rerank',
        action='store_true',
        help='Enable re-ranking'
    )

    parser.add_argument(
        '--device',
        default='cpu',
        help='Device for embedder/reranker (cpu or cuda)'
    )

    args = parser.parse_args()

    # Setup
    conn_string = "host=localhost port=5433 dbname=news_db user=rag_user"

    # Load embedder
    console.print("\n[bold blue]Loading BGE-M3 embedder...[/bold blue]")
    embedder = SentenceTransformer('BAAI/bge-m3', device=args.device)
    console.print(f"   ✓ Loaded on {args.device}")

    # Load reranker (optional)
    reranker = None
    if args.rerank:
        console.print("\n[bold blue]Loading cross-encoder reranker...[/bold blue]")
        reranker = create_reranker('local', device=args.device)

    # Config
    config = RetrieverConfig(
        final_top_k=args.top_k,
        use_reranking=args.rerank,
        rerank_top_k=args.top_k
    )

    # Run mode
    if args.mode == 'benchmark':
        run_benchmark(conn_string, embedder, args.queries, config, reranker)

    elif args.mode == 'compare':
        query = args.query or "Qual foi a decisão do Copom sobre a Selic?"
        test_retrieval_methods(conn_string, embedder, query, args.top_k)

    elif args.mode == 'interactive':
        retriever = Retriever(conn_string, embedder, config, reranker)

        console.print("\n[bold cyan]Interactive Retrieval Mode[/bold cyan]")
        console.print("Type your query (or 'quit' to exit)\n")

        while True:
            query = input("Query: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                break

            if not query:
                continue

            query_data = {'query': query, 'type': 'interactive', 'difficulty': 'unknown'}
            test_single_query(retriever, query_data, show_results=True)


if __name__ == "__main__":
    main()
