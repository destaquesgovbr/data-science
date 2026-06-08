#!/usr/bin/env python3
"""
Test generation pipeline (Retrieval + LLM).

Tests RAG end-to-end with different providers (Bedrock, Ollama).
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from sentence_transformers import SentenceTransformer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from src.retrieval import Retriever, RetrieverConfig
from src.generation import Generator, PromptLibrary
from src.llm_providers import create_llm_provider
from src.reranking import create_reranker

console = Console()


def test_single_query(
    generator: Generator,
    query: str,
    show_context: bool = False
):
    """Test generation for a single query."""

    console.print(f"\n[bold cyan]Query:[/bold cyan] {query}\n")

    try:
        # Generate answer
        response = generator.generate(query)

        # Display answer
        console.print(Panel(
            Markdown(response.answer),
            title="[bold green]Answer[/bold green]",
            border_style="green"
        ))

        # Display sources
        console.print("\n[bold]📚 Sources:[/bold]")
        for source in response.sources:
            console.print(f"\n[cyan][{source['index']}][/cyan] {source['title']}")
            console.print(f"   [dim]Categoria: {source['category']} | Órgão: {source['agency']}[/dim]")
            console.print(f"   [dim]Score: {source['score']:.3f}[/dim]")
            if source['url'] != 'URL não disponível':
                console.print(f"   [link={source['url']}]{source['url']}[/link]")

        # Display metrics
        console.print("\n[bold]📊 Metrics:[/bold]")
        console.print(f"   Retrieval:  {response.latency_breakdown['retrieval_ms']:.0f}ms")
        console.print(f"   Generation: {response.latency_breakdown['generation_ms']:.0f}ms")
        console.print(f"   Total:      {response.latency_breakdown['total_ms']:.0f}ms")

        if response.tokens_input:
            console.print(f"   Tokens:     {response.tokens_input} → {response.tokens_output}")

        if response.cost_usd:
            console.print(f"   Cost:       ${response.cost_usd:.4f}")

        console.print(f"   Model:      {response.llm_model} ({response.llm_provider})")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


def test_multiple_queries(
    generator: Generator,
    queries: list
):
    """Test generation on multiple queries."""

    console.print(Panel.fit(
        "[bold cyan]RAG Generation Test[/bold cyan]\n"
        f"[dim]Testing {len(queries)} queries[/dim]",
        border_style="cyan"
    ))

    results = []

    for i, query in enumerate(queries, 1):
        console.print(f"\n{'='*80}")
        console.print(f"[bold]Query {i}/{len(queries)}[/bold]")
        console.print(f"{'='*80}")

        try:
            response = generator.generate(query)

            results.append({
                'query': query,
                'success': True,
                'answer_length': len(response.answer),
                'num_sources': len(response.sources),
                'latency_total': response.latency_breakdown['total_ms'],
                'latency_retrieval': response.latency_breakdown['retrieval_ms'],
                'latency_generation': response.latency_breakdown['generation_ms'],
                'tokens_output': response.tokens_output,
                'cost': response.cost_usd
            })

            # Show compact output
            console.print(f"\n[cyan]Q:[/cyan] {query}")
            console.print(f"\n[green]A:[/green] {response.answer[:200]}...")
            console.print(f"\n[dim]Sources: {len(response.sources)}, "
                         f"Latency: {response.latency_breakdown['total_ms']:.0f}ms, "
                         f"Tokens: {response.tokens_output or 0}[/dim]")

        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            results.append({
                'query': query,
                'success': False,
                'error': str(e)
            })

    # Summary
    console.print(f"\n{'='*80}")
    console.print("[bold cyan]📊 Summary[/bold cyan]")
    console.print(f"{'='*80}\n")

    successful = [r for r in results if r.get('success')]

    if successful:
        avg_latency_total = sum(r['latency_total'] for r in successful) / len(successful)
        avg_latency_retrieval = sum(r['latency_retrieval'] for r in successful) / len(successful)
        avg_latency_generation = sum(r['latency_generation'] for r in successful) / len(successful)
        avg_answer_length = sum(r['answer_length'] for r in successful) / len(successful)
        avg_sources = sum(r['num_sources'] for r in successful) / len(successful)

        total_tokens = sum(r.get('tokens_output', 0) for r in successful if r.get('tokens_output'))
        total_cost = sum(r.get('cost', 0) for r in successful if r.get('cost'))

        console.print(f"Successful: {len(successful)}/{len(results)}")
        console.print(f"\nLatency:")
        console.print(f"  Retrieval:  {avg_latency_retrieval:.0f}ms")
        console.print(f"  Generation: {avg_latency_generation:.0f}ms")
        console.print(f"  Total:      {avg_latency_total:.0f}ms")
        console.print(f"\nAnswer quality:")
        console.print(f"  Avg length: {avg_answer_length:.0f} chars")
        console.print(f"  Avg sources: {avg_sources:.1f}")

        if total_tokens:
            console.print(f"\nToken usage:")
            console.print(f"  Total: {total_tokens} tokens")
            console.print(f"  Avg per query: {total_tokens / len(successful):.0f} tokens")

        if total_cost:
            console.print(f"\nCost:")
            console.print(f"  Total: ${total_cost:.4f}")
            console.print(f"  Avg per query: ${total_cost / len(successful):.4f}")

    else:
        console.print("[red]All queries failed[/red]")

    failed = [r for r in results if not r.get('success')]
    if failed:
        console.print(f"\n[red]Failed: {len(failed)}[/red]")
        for r in failed:
            console.print(f"  - {r['query']}: {r.get('error', 'Unknown error')}")


def main():
    parser = argparse.ArgumentParser(description="Test RAG generation pipeline")

    # LLM provider
    parser.add_argument(
        '--provider',
        choices=['bedrock', 'ollama'],
        default='bedrock',
        help='LLM provider'
    )

    parser.add_argument(
        '--model',
        help='Model ID/name (e.g., anthropic.claude-sonnet-4-6 for Bedrock, llama3.1:8b for Ollama)'
    )

    # Query
    parser.add_argument(
        '--query',
        help='Single query to test'
    )

    parser.add_argument(
        '--queries-file',
        help='File with multiple queries (one per line)'
    )

    # Retrieval
    parser.add_argument(
        '--top-k',
        type=int,
        default=5,
        help='Number of chunks to retrieve'
    )

    parser.add_argument(
        '--rerank',
        action='store_true',
        help='Enable re-ranking'
    )

    # Prompt
    parser.add_argument(
        '--prompt-template',
        choices=PromptLibrary.list_templates(),
        default='default',
        help='Prompt template to use'
    )

    # Generation
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=2000,
        help='Max tokens for LLM response'
    )

    parser.add_argument(
        '--temperature',
        type=float,
        default=0.0,
        help='LLM temperature (0 = deterministic)'
    )

    args = parser.parse_args()

    # Setup
    conn_string = "host=localhost port=5433 dbname=news_db user=rag_user"

    console.print("\n[bold blue]🚀 RAG Generation Pipeline Test[/bold blue]\n")

    # Load embedder
    console.print("[dim]Loading BGE-M3 embedder...[/dim]")
    embedder = SentenceTransformer('BAAI/bge-m3', device='cpu')

    # Create retriever
    console.print("[dim]Initializing retriever...[/dim]")

    reranker = None
    if args.rerank:
        console.print("[dim]Loading reranker...[/dim]")
        reranker = create_reranker('local', device='cpu')

    config = RetrieverConfig(
        final_top_k=args.top_k,
        use_reranking=args.rerank,
        rerank_top_k=args.top_k
    )

    retriever = Retriever(conn_string, embedder, config, reranker)

    # Create LLM provider
    console.print(f"[dim]Initializing LLM provider: {args.provider}...[/dim]")

    if args.provider == 'bedrock':
        model_id = args.model or 'anthropic.claude-sonnet-4-6'
        llm = create_llm_provider('bedrock', model_id=model_id)

    elif args.provider == 'ollama':
        model = args.model or 'llama3.1:8b'
        llm = create_llm_provider('ollama', model=model)

    # Create generator
    prompt_template = PromptLibrary.get(args.prompt_template)
    generator = Generator(retriever, llm, prompt_template=prompt_template)

    console.print(f"[green]✓ Setup complete[/green]")
    console.print(f"   Provider: {args.provider}")
    console.print(f"   Model: {args.model or 'default'}")
    console.print(f"   Top-K: {args.top_k}")
    console.print(f"   Rerank: {args.rerank}")
    console.print(f"   Prompt: {args.prompt_template}")

    # Run tests
    if args.query:
        # Single query
        test_single_query(generator, args.query)

    elif args.queries_file:
        # Multiple queries from file
        with open(args.queries_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]

        test_multiple_queries(generator, queries)

    else:
        # Default test queries
        test_queries = [
            "Qual foi o valor destinado ao Plano Safra 2025/2026?",
            "Quais medidas foram anunciadas para proteção social em favelas e periferias?",
            "O que é o guia nacional de inteligência artificial mencionado nas notícias?",
        ]

        test_multiple_queries(generator, test_queries)


if __name__ == "__main__":
    main()
