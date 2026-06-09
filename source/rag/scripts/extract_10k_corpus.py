#!/usr/bin/env python3
"""
Extract 10k most recent news from news_corpus_repository and export to JSON.

This script connects to the local PostgreSQL database, extracts the 10,000
most recent news articles, and exports them in a format compatible with
index_corpus.py for indexing on EC2.

Usage:
    python scripts/extract_10k_corpus.py --output data/corpus_10k.json --limit 10000
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich import print as rprint

console = Console()


def connect_to_database(host="localhost", port=5432, dbname="postgres", user="postgres", password=None):
    """Connect to local PostgreSQL database."""
    # Try with authentication disabled first (trust mode)
    try:
        conn = psycopg.connect(
            f"host={host} port={port} dbname={dbname} user={user}",
            row_factory=dict_row
        )
        console.print(f"[green]✅ Connected to {dbname} (trust mode)[/green]")
        return conn
    except Exception as e1:
        # Try with password if provided
        if password:
            try:
                conn = psycopg.connect(
                    f"host={host} port={port} dbname={dbname} user={user} password={password}",
                    row_factory=dict_row
                )
                console.print(f"[green]✅ Connected to {dbname} (password auth)[/green]")
                return conn
            except Exception as e2:
                console.print(f"[red]❌ Failed to connect with password: {e2}[/red]")

        console.print(f"[red]❌ Failed to connect to database: {e1}[/red]")
        console.print(f"[yellow]💡 Tip: Make sure PostgreSQL is running and accessible[/yellow]")
        console.print(f"[yellow]   Try: pg_isready -h {host} -p {port}[/yellow]")
        sys.exit(1)


def extract_news(conn, limit: int = 10000):
    """Extract most recent news from corpus repository."""
    console.print(f"\n[cyan]📊 Extracting {limit:,} most recent news...[/cyan]")

    query = """
        SELECT
            unique_id,
            title,
            content,
            url,
            source_agency,
            category,
            published_at,
            updated_at,
            subtitle,
            editorial_lead,
            summary,
            tags,
            metadata
        FROM news_corpus_repository
        ORDER BY published_at DESC NULLS LAST
        LIMIT %s
    """

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Fetching from database...", total=None)

        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

        progress.update(task, completed=True)

    console.print(f"[green]✅ Extracted {len(rows):,} documents[/green]")
    return rows


def transform_to_index_format(rows):
    """Transform database rows to format expected by index_corpus.py."""
    console.print("\n[cyan]🔄 Transforming to indexing format...[/cyan]")

    documents = []

    for row in rows:
        # Build document in expected format
        doc = {
            "id": row["unique_id"],
            "title": row["title"] or "",
            "content": row["content"] or "",
            "metadata": {
                "url": row["url"] or "",
                "source_agency": row["source_agency"] or "",
                "category": row["category"] or "",
                "published_at": row["published_at"].isoformat() if row["published_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "subtitle": row["subtitle"] or "",
                "editorial_lead": row["editorial_lead"] or "",
                "summary": row["summary"] or "",
                "tags": row["tags"] or [],
                "original_metadata": row["metadata"] or {}
            }
        }

        documents.append(doc)

    console.print(f"[green]✅ Transformed {len(documents):,} documents[/green]")
    return documents


def export_to_json(documents, output_path: str):
    """Export documents to JSON file."""
    console.print(f"\n[cyan]💾 Exporting to {output_path}...[/cyan]")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    # Get file size
    size_mb = output_file.stat().st_size / (1024 * 1024)

    console.print(f"[green]✅ Exported to {output_path} ({size_mb:.2f} MB)[/green]")
    return output_file


def print_statistics(documents):
    """Print statistics about extracted corpus."""
    from collections import Counter

    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]📈 Corpus Statistics[/bold cyan]",
        border_style="cyan"
    ))

    # Count by category
    categories = Counter(doc["metadata"]["category"] for doc in documents)

    # Date range
    dates = [doc["metadata"]["published_at"] for doc in documents if doc["metadata"]["published_at"]]
    if dates:
        dates_sorted = sorted(dates)
        date_range = f"{dates_sorted[0][:10]} to {dates_sorted[-1][:10]}"
    else:
        date_range = "N/A"

    # Average content length
    avg_content_length = sum(len(doc["content"]) for doc in documents) / len(documents)

    console.print(f"[white]Total documents:[/white] [green]{len(documents):,}[/green]")
    console.print(f"[white]Date range:[/white] [yellow]{date_range}[/yellow]")
    console.print(f"[white]Avg content length:[/white] [cyan]{avg_content_length:.0f} chars[/cyan]")
    console.print(f"\n[white]Top 5 categories:[/white]")
    for category, count in categories.most_common(5):
        percentage = (count / len(documents)) * 100
        console.print(f"  [cyan]•[/cyan] {category or 'Unknown'}: {count:,} ({percentage:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Extract 10k news from corpus repository for indexing"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/corpus_10k.json",
        help="Output JSON file path (default: data/corpus_10k.json)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Number of documents to extract (default: 10000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="PostgreSQL host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5432,
        help="PostgreSQL port (default: 5432)"
    )
    parser.add_argument(
        "--dbname",
        type=str,
        default="postgres",
        help="Database name (default: postgres)"
    )
    parser.add_argument(
        "--user",
        type=str,
        default="postgres",
        help="Database user (default: postgres)"
    )

    args = parser.parse_args()

    # Print header
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]📦 Corpus Extraction Tool[/bold green]\n"
        f"Extracting {args.limit:,} most recent news from local database",
        border_style="green"
    ))

    # Connect to database
    conn = connect_to_database(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user
    )

    try:
        # Extract news
        rows = extract_news(conn, limit=args.limit)

        if not rows:
            console.print("[red]❌ No documents found in database[/red]")
            sys.exit(1)

        # Transform to indexing format
        documents = transform_to_index_format(rows)

        # Export to JSON
        output_file = export_to_json(documents, args.output)

        # Print statistics
        print_statistics(documents)

        # Print next steps
        console.print("\n")
        console.print(Panel.fit(
            "[bold yellow]📋 Next Steps[/bold yellow]\n\n"
            f"1. Transfer to EC2:\n"
            f"   [cyan]scp {output_file} ec2-user@<EC2-IP>:/home/ec2-user/rag/data/[/cyan]\n\n"
            f"2. SSH to EC2:\n"
            f"   [cyan]ssh ec2-user@<EC2-IP>[/cyan]\n\n"
            f"3. Index on EC2:\n"
            f"   [cyan]cd /home/ec2-user/rag[/cyan]\n"
            f"   [cyan]python scripts/index_corpus.py --input data/corpus_10k.json --format json[/cyan]",
            border_style="yellow"
        ))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
