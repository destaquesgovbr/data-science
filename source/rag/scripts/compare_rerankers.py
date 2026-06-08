#!/usr/bin/env python3
"""
Compare different reranker models on our corpus.

Tests:
1. ms-marco-MiniLM-L-12-v2 (baseline, English)
2. ms-marco-MiniLM-L-6-v2 (faster baseline)
3. bge-reranker-v2-m3 (multilingual SOTA)

Metrics:
- Category match rate
- Latency (P50, P95)
- Score distribution
- Per-query analysis
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time
from typing import List, Dict
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer, CrossEncoder
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import numpy as np

# FlagEmbedding has compatibility issues, we'll use CrossEncoder for all models
HAS_FLAG = False

from src.retrieval import Retriever, RetrieverConfig

console = Console()


@dataclass
class RerankerResult:
    """Results from a single reranker."""
    model_name: str
    query: str
    expected_category: str

    # Performance
    latency_ms: float
    load_time_s: float

    # Results
    top_category: str
    top_score: float
    scores: List[float]

    # Metrics
    category_match: bool
    num_results: int


class RerankerComparator:
    """Compare multiple reranker models."""

    def __init__(self, conn_string: str, embedder):
        self.conn_string = conn_string
        self.embedder = embedder
        self.console = console

    def test_reranker(
        self,
        model_name: str,
        model_type: str,
        query_data: Dict,
        show_progress: bool = True
    ) -> RerankerResult:
        """Test a single reranker on one query."""

        query = query_data['query']
        expected = query_data.get('expected_category')

        # Stage 1: Retrieval (same for all rerankers)
        config = RetrieverConfig(
            final_top_k=10,
            use_reranking=False  # We'll rerank manually
        )
        retriever = Retriever(self.conn_string, self.embedder, config)

        # Get candidates
        candidates = retriever.retrieve(query)

        if not candidates:
            return RerankerResult(
                model_name=model_name,
                query=query,
                expected_category=expected,
                latency_ms=0,
                load_time_s=0,
                top_category=None,
                top_score=0,
                scores=[],
                category_match=False,
                num_results=0
            )

        # Stage 2: Re-rank
        if model_type == 'flag':
            load_start = time.time()
            reranker = FlagReranker(model_name, use_fp16=True)
            load_time = time.time() - load_start

            # Prepare pairs
            pairs = [[query, c.content] for c in candidates]

            # Inference
            start = time.time()
            scores = reranker.compute_score(pairs, normalize=False)
            latency = (time.time() - start) * 1000

            # Convert to list if numpy
            if isinstance(scores, np.ndarray):
                scores = scores.tolist()
            elif not isinstance(scores, list):
                scores = [scores]

        elif model_type == 'cross-encoder':
            load_start = time.time()
            reranker = CrossEncoder(model_name, max_length=512, device='cpu')
            load_time = time.time() - load_start

            # Prepare pairs
            pairs = [(query, c.content) for c in candidates]

            # Inference
            start = time.time()
            scores = reranker.predict(pairs, show_progress_bar=False)
            latency = (time.time() - start) * 1000

            # Convert to list
            scores = scores.tolist()

        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        # Re-order candidates by new scores
        sorted_indices = np.argsort(scores)[::-1]
        top_idx = sorted_indices[0]

        top_category = candidates[top_idx].doc_category
        top_score = scores[top_idx]
        category_match = (top_category == expected) if expected else None

        return RerankerResult(
            model_name=model_name,
            query=query,
            expected_category=expected,
            latency_ms=latency,
            load_time_s=load_time,
            top_category=top_category,
            top_score=float(top_score),
            scores=[float(s) for s in scores],
            category_match=category_match,
            num_results=len(candidates)
        )

    def compare_models(
        self,
        models: List[tuple],  # [(name, model_id, type)]
        queries: List[Dict]
    ):
        """Compare multiple models on multiple queries."""

        console.print(Panel.fit(
            "[bold cyan]Reranker Model Comparison[/bold cyan]\n"
            f"[dim]Testing {len(models)} models on {len(queries)} queries[/dim]",
            border_style="cyan"
        ))

        all_results = {model[0]: [] for model in models}

        # Test each model
        for model_name, model_id, model_type in models:
            console.print(f"\n[bold blue]Testing: {model_name}[/bold blue]")
            console.print(f"Model ID: {model_id}")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"Processing queries...", total=len(queries))

                for query_data in queries:
                    try:
                        result = self.test_reranker(
                            model_id,
                            model_type,
                            query_data,
                            show_progress=False
                        )
                        all_results[model_name].append(result)
                    except Exception as e:
                        console.print(f"  [red]✗ Error on query '{query_data['query'][:30]}...': {e}[/red]")

                    progress.advance(task)

        # Aggregate and display
        self._display_comparison(models, all_results, queries)

        return all_results

    def _display_comparison(
        self,
        models: List[tuple],
        all_results: Dict,
        queries: List[Dict]
    ):
        """Display comparison results."""

        console.print("\n" + "="*80)
        console.print("[bold cyan]📊 Comparison Results[/bold cyan]")
        console.print("="*80)

        # Aggregate metrics per model
        console.print("\n[bold]Overall Performance:[/bold]\n")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Model", width=30)
        table.add_column("Match Rate", width=12)
        table.add_column("Avg Latency", width=12)
        table.add_column("P95 Latency", width=12)
        table.add_column("Load Time", width=12)
        table.add_column("Avg Score", width=12)

        for model_name, _, _ in models:
            results = all_results[model_name]

            if not results:
                continue

            # Metrics
            match_rate = sum(r.category_match for r in results if r.category_match is not None) / \
                         len([r for r in results if r.category_match is not None])

            latencies = [r.latency_ms for r in results]
            avg_latency = np.mean(latencies)
            p95_latency = np.percentile(latencies, 95)

            load_time = results[0].load_time_s if results else 0

            avg_score = np.mean([r.top_score for r in results])

            # Format
            match_str = f"{match_rate:.1%}"
            if match_rate >= 0.9:
                match_str = f"[green]{match_str}[/green]"
            elif match_rate >= 0.7:
                match_str = f"[yellow]{match_str}[/yellow]"
            else:
                match_str = f"[red]{match_str}[/red]"

            table.add_row(
                model_name,
                match_str,
                f"{avg_latency:.0f}ms",
                f"{p95_latency:.0f}ms",
                f"{load_time:.1f}s",
                f"{avg_score:.3f}"
            )

        console.print(table)

        # Score distribution comparison
        console.print("\n[bold]Score Distribution:[/bold]\n")

        for model_name, _, _ in models:
            results = all_results[model_name]
            if not results:
                continue

            scores = [r.top_score for r in results]

            console.print(f"{model_name:30s} "
                         f"Range: [{min(scores):6.2f}, {max(scores):6.2f}]  "
                         f"Mean: {np.mean(scores):6.2f}  "
                         f"STD: {np.std(scores):6.2f}")

        # Per-query comparison (show interesting cases)
        console.print("\n[bold]Per-Query Comparison (top 5 queries):[/bold]\n")

        for i, query_data in enumerate(queries[:5]):
            query = query_data['query']
            expected = query_data.get('expected_category', 'N/A')

            console.print(f"\n[cyan]Query {i+1}:[/cyan] {query}")
            console.print(f"[dim]Expected: {expected}[/dim]")

            # Compare results
            for model_name, _, _ in models:
                results = all_results[model_name]
                if i >= len(results):
                    continue

                result = results[i]

                match_icon = "✓" if result.category_match else "✗"
                match_color = "green" if result.category_match else "yellow"

                console.print(
                    f"  {model_name:30s} "
                    f"[{match_color}]{match_icon}[/{match_color}] "
                    f"[{result.top_category}] "
                    f"score: {result.top_score:6.2f}  "
                    f"{result.latency_ms:4.0f}ms"
                )

        # Disagreement analysis
        console.print("\n[bold]Disagreements (where models differ):[/bold]\n")

        disagreements = []
        for i, query_data in enumerate(queries):
            categories = set()
            for model_name in all_results:
                results = all_results[model_name]
                if i < len(results):
                    categories.add(results[i].top_category)

            if len(categories) > 1:
                disagreements.append((i, query_data, categories))

        if disagreements:
            console.print(f"Found {len(disagreements)} disagreements:\n")
            for i, query_data, categories in disagreements[:5]:
                console.print(f"[yellow]Query {i+1}:[/yellow] {query_data['query']}")
                console.print(f"  Expected: {query_data.get('expected_category', 'N/A')}")
                console.print(f"  Models predict: {categories}")

                # Show each model's prediction
                for model_name in all_results:
                    results = all_results[model_name]
                    if i < len(results):
                        r = results[i]
                        console.print(f"    {model_name:30s} → [{r.top_category}] (score: {r.top_score:.2f})")
                console.print()
        else:
            console.print("✓ All models agree on all queries!")

        # Final verdict
        console.print("\n" + "="*80)

        best_model = max(
            models,
            key=lambda m: sum(r.category_match for r in all_results[m[0]] if r.category_match is not None)
        )

        best_results = all_results[best_model[0]]
        best_match_rate = sum(r.category_match for r in best_results if r.category_match is not None) / \
                         len([r for r in best_results if r.category_match is not None])

        console.print(f"[bold green]🏆 Best Model: {best_model[0]}[/bold green]")
        console.print(f"   Match Rate: {best_match_rate:.1%}")
        console.print(f"   Avg Latency: {np.mean([r.latency_ms for r in best_results]):.0f}ms")

        console.print("="*80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Compare reranker models")
    parser.add_argument('--queries', default='data/test_queries.json', help='Test queries JSON')
    parser.add_argument('--device', default='cpu', help='Device (cpu or cuda)')
    args = parser.parse_args()

    # Setup
    conn_string = "host=localhost port=5433 dbname=news_db user=rag_user"

    # Load embedder
    console.print("\n[bold blue]Loading BGE-M3 embedder...[/bold blue]")
    embedder = SentenceTransformer('BAAI/bge-m3', device=args.device)
    console.print(f"   ✓ Loaded on {args.device}")

    # Load queries
    with open(args.queries, 'r', encoding='utf-8') as f:
        queries = json.load(f)

    # Models to compare
    models = [
        ('ms-marco-L-12 (baseline)', 'cross-encoder/ms-marco-MiniLM-L-12-v2', 'cross-encoder'),
        ('ms-marco-L-6 (fast)', 'cross-encoder/ms-marco-MiniLM-L-6-v2', 'cross-encoder'),
        ('bge-reranker-v2-m3 (multilingual)', 'BAAI/bge-reranker-v2-m3', 'cross-encoder'),
    ]

    # Run comparison
    comparator = RerankerComparator(conn_string, embedder)
    results = comparator.compare_models(models, queries)

    # Save results
    output_file = 'results/reranker_comparison.json'
    Path(output_file).parent.mkdir(exist_ok=True)

    # Convert results to JSON-serializable format
    results_json = {}
    for model_name, result_list in results.items():
        results_json[model_name] = [
            {
                'query': r.query,
                'expected_category': r.expected_category,
                'top_category': r.top_category,
                'top_score': r.top_score,
                'latency_ms': r.latency_ms,
                'category_match': r.category_match,
                'num_results': r.num_results,
                'scores': r.scores[:3]  # Save only top 3 scores
            }
            for r in result_list
        ]

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)

    console.print(f"\n✓ Results saved to {output_file}")


if __name__ == "__main__":
    main()
