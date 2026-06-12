#!/usr/bin/env python3
"""
Interactive CLI client for RAG API.

Simple REPL interface for testing queries in real-time.
"""

import requests
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.table import Table
import json

console = Console()

# API configuration
API_BASE_URL = "http://localhost:8000"

# Default config
DEFAULT_CONFIG = {
    "top_k": 5,
    "use_reranking": True,
    "provider": "bedrock",
    "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "max_tokens": 2000,
    "temperature": 0.0,
    "prompt_template": "default",
    "min_source_score": 0.0,
    "date_from": None,
    "date_to": None
}


def print_banner():
    """Print welcome banner."""
    console.print(Panel.fit(
        "[bold cyan]RAG Q&A - Interactive Client[/bold cyan]\n\n"
        "[dim]Ask questions about Brazilian government news[/dim]\n\n"
        "Commands:\n"
        "  [yellow]/help[/yellow]    - Show commands\n"
        "  [yellow]/config[/yellow]  - Change settings\n"
        "  [yellow]/exit[/yellow]    - Quit\n",
        border_style="cyan"
    ))


def check_health():
    """Check API health."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'ok':
                console.print("[green]✓ API is healthy[/green]")
                return True
            else:
                console.print(f"[yellow]⚠ API is degraded: {data}[/yellow]")
                return False
        else:
            console.print(f"[red]✗ API health check failed: {response.status_code}[/red]")
            return False
    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Cannot connect to API: {e}[/red]")
        console.print(f"[dim]Make sure server is running: python api/server.py[/dim]")
        return False


def send_query(query: str, config: dict):
    """Send query to API and display results."""

    console.print(f"\n[cyan]Query:[/cyan] {query}\n")

    # Build request (filter out None values for cleaner request)
    request_data = {
        "query": query,
        **{k: v for k, v in config.items() if v is not None}
    }

    try:
        # Send request
        console.print("[dim]Sending request...[/dim]")
        response = requests.post(
            f"{API_BASE_URL}/query",
            json=request_data,
            timeout=120
        )

        if response.status_code != 200:
            console.print(f"[red]✗ Error: {response.status_code}[/red]")
            console.print(response.text)
            return

        data = response.json()

        # Display answer
        console.print(Panel(
            Markdown(data['answer']),
            title="[bold green]Answer[/bold green]",
            border_style="green"
        ))

        # Display sources
        console.print("\n[bold]📚 Sources:[/bold]")
        for source in data['sources']:
            console.print(f"\n[cyan][{source['index']}][/cyan] {source['title']}")

            # Build metadata line
            metadata_parts = [f"Categoria: {source['category']}", f"Órgão: {source['agency']}"]
            if source.get('published_at'):
                metadata_parts.append(f"Data: {source['published_at']}")
            console.print(f"   [dim]{' | '.join(metadata_parts)}[/dim]")

            console.print(f"   [dim]Score: {source['score']:.3f}[/dim]")
            if source['url'] != 'URL não disponível':
                console.print(f"   [link={source['url']}]{source['url']}[/link]")

        # Display metrics
        console.print("\n[bold]📊 Metrics:[/bold]")
        console.print(f"   Retrieval:  {data['latency_ms']['retrieval_ms']:.0f}ms")
        console.print(f"   Generation: {data['latency_ms']['generation_ms']:.0f}ms")
        console.print(f"   Total:      {data['latency_ms']['total_ms']:.0f}ms")

        if data.get('tokens_input'):
            console.print(f"   Tokens:     {data['tokens_input']} → {data['tokens_output']}")

        if data.get('cost_usd'):
            console.print(f"   Cost:       ${data['cost_usd']:.4f}")

        console.print(f"   Model:      {data['llm_model']} ({data['llm_provider']})")

    except requests.exceptions.Timeout:
        console.print("[red]✗ Request timed out[/red]")
    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Request failed: {e}[/red]")
    except json.JSONDecodeError as e:
        console.print(f"[red]✗ Invalid JSON response: {e}[/red]")


def show_config(config: dict):
    """Display current configuration."""

    table = Table(title="Current Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")

    for key, value in config.items():
        table.add_row(key, str(value))

    console.print(table)


def change_config(config: dict) -> dict:
    """Interactive configuration change."""

    console.print("\n[bold]Change Configuration[/bold]")
    console.print("[dim]Press Enter to keep current value[/dim]\n")

    new_config = config.copy()

    # Provider
    provider = Prompt.ask(
        "Provider (bedrock/ollama)",
        default=config['provider'],
        choices=["bedrock", "ollama"]
    )
    new_config['provider'] = provider

    # Model
    if provider == "bedrock":
        default_model = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        console.print("\n[dim]Bedrock models:[/dim]")
        console.print("  [yellow]us.anthropic.claude-sonnet-4-6[/yellow] - Best quality")
        console.print("  [yellow]us.anthropic.claude-haiku-4-5-20251001-v1:0[/yellow] - Fast (default)")
        console.print("  [yellow]us.anthropic.claude-sonnet-4-5-20250929-v1:0[/yellow] - Balanced")
    else:
        default_model = "qwen2.5:7b"
        console.print("\n[dim]Ollama models (installed):[/dim]")
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            models = resp.json()['models']
            for m in models[:5]:  # Show first 5
                console.print(f"  [yellow]{m['name']}[/yellow]")
        except:
            console.print("  [dim](could not list models)[/dim]")

    model = Prompt.ask("\nModel", default=config.get('model') or default_model)
    new_config['model'] = model

    # Top-K
    top_k = Prompt.ask("Top-K chunks", default=str(config['top_k']))
    new_config['top_k'] = int(top_k)

    # Reranking
    use_reranking = Confirm.ask("Use re-ranking?", default=config['use_reranking'])
    new_config['use_reranking'] = use_reranking

    # Temperature
    temperature = Prompt.ask("Temperature (0.0-2.0)", default=str(config['temperature']))
    new_config['temperature'] = float(temperature)

    # Prompt template
    prompt_template = Prompt.ask(
        "Prompt template",
        default=config['prompt_template'],
        choices=["default", "factual", "summary", "comparison"]
    )
    new_config['prompt_template'] = prompt_template

    # Min source score
    min_score = Prompt.ask("Min source score (0.0 = filter negatives)", default=str(config['min_source_score']))
    new_config['min_source_score'] = float(min_score)

    # Date filters
    console.print("\n[dim]Date filters (YYYY-MM-DD format, leave empty for no filter)[/dim]")
    date_from = Prompt.ask("Date from", default=config.get('date_from') or "")
    new_config['date_from'] = date_from if date_from else None

    date_to = Prompt.ask("Date to", default=config.get('date_to') or "")
    new_config['date_to'] = date_to if date_to else None

    console.print("\n[green]✓ Configuration updated[/green]")
    return new_config


def show_help():
    """Show help message."""
    console.print(Panel(
        """[bold]RAG Q&A Client - Help[/bold]

[yellow]Commands:[/yellow]
  [cyan]/help[/cyan]      - Show this help message
  [cyan]/config[/cyan]    - Change configuration (model, top-k, etc.)
  [cyan]/show[/cyan]      - Show current configuration
  [cyan]/exit[/cyan]      - Quit the client
  [cyan]/quit[/cyan]      - Same as /exit

[yellow]Usage:[/yellow]
  Just type your question and press Enter
  Example: "Qual foi o valor do Plano Safra?"

[yellow]Tips:[/yellow]
  - Use specific questions for better results
  - Check sources to verify information
  - Try different models to compare quality/speed
  - Enable re-ranking for better retrieval (slower but more accurate)
""",
        border_style="blue"
    ))


def main():
    """Main REPL loop."""

    print_banner()

    # Check API health
    console.print("\n[dim]Checking API health...[/dim]")
    if not check_health():
        if not Confirm.ask("\nContinue anyway?"):
            return

    # Config
    config = DEFAULT_CONFIG.copy()

    # Show initial config
    console.print()
    show_config(config)
    console.print()

    # REPL loop
    while True:
        try:
            # Prompt
            query = Prompt.ask("\n[bold green]>[/bold green]", default="").strip()

            if not query:
                continue

            # Commands
            if query.lower() in ['/exit', '/quit']:
                console.print("[dim]Goodbye![/dim]")
                break

            elif query.lower() == '/help':
                show_help()

            elif query.lower() == '/config':
                config = change_config(config)

            elif query.lower() == '/show':
                show_config(config)

            elif query.startswith('/'):
                console.print(f"[red]Unknown command: {query}[/red]")
                console.print("[dim]Type /help for available commands[/dim]")

            else:
                # Regular query
                send_query(query, config)

        except KeyboardInterrupt:
            console.print("\n[dim]Use /exit to quit[/dim]")
        except EOFError:
            break


if __name__ == "__main__":
    main()
