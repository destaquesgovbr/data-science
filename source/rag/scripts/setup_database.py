#!/usr/bin/env python3
"""
Setup PostgreSQL database schema for RAG system.

Creates:
- news_documents table
- document_chunks table
- pgvector extension
- Indexes (vector, full-text, metadata)
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg
from psycopg import sql
import yaml
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint
import argparse
from dotenv import load_dotenv
import os

console = Console()


def load_config(config_path: str = "config/database.yaml") -> dict:
    """Load database configuration."""

    # Load environment variables
    load_dotenv()

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Replace ${VAR} with environment variables
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

    return replace_env_vars(config)


def get_connection_string(config: dict) -> str:
    """Build PostgreSQL connection string."""

    db_config = config['database']

    return (
        f"host={db_config['host']} "
        f"port={db_config['port']} "
        f"dbname={db_config['name']} "
        f"user={db_config['user']} "
        f"password={db_config['password']}"
    )


def create_extension(conn):
    """Create pgvector extension."""

    console.print("\n[bold blue]1. Creating pgvector extension...[/bold blue]")

    with conn.cursor() as cur:
        # Check if extension exists
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            );
        """)

        exists = cur.fetchone()[0]

        if exists:
            console.print("   ✓ pgvector extension already exists", style="green")
        else:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            console.print("   ✓ Created pgvector extension", style="green")


def create_documents_table(conn, drop_existing: bool = False):
    """Create news_documents table."""

    console.print("\n[bold blue]2. Creating news_documents table...[/bold blue]")

    with conn.cursor() as cur:
        if drop_existing:
            console.print("   ⚠️  Dropping existing table...", style="yellow")
            cur.execute("DROP TABLE IF EXISTS news_documents CASCADE;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS news_documents (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                url TEXT,
                source_agency TEXT,
                category TEXT,
                published_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                -- Metadata as JSONB for flexibility
                metadata JSONB,

                -- Constraints
                CONSTRAINT unique_url UNIQUE (url)
            );
        """)

        # Create indexes
        console.print("   Creating indexes...")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_published
            ON news_documents(published_at DESC);
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_category
            ON news_documents(category);
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_agency
            ON news_documents(source_agency);
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_metadata
            ON news_documents USING GIN(metadata);
        """)

        conn.commit()
        console.print("   ✓ Created news_documents table with indexes", style="green")


def create_chunks_table(conn, config: dict, drop_existing: bool = False):
    """Create document_chunks table."""

    console.print("\n[bold blue]3. Creating document_chunks table...[/bold blue]")

    vector_config = config['vector']
    dimension = vector_config['dimension']

    with conn.cursor() as cur:
        if drop_existing:
            console.print("   ⚠️  Dropping existing table...", style="yellow")
            cur.execute("DROP TABLE IF EXISTS document_chunks CASCADE;")

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY,
                document_id INTEGER NOT NULL REFERENCES news_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,

                -- Chunk content
                content TEXT NOT NULL,
                enriched_content TEXT,  -- Contextual enrichment (Anthropic pattern)

                -- Embeddings (BGE-M3: 1024 dimensions)
                embedding vector({dimension}),

                -- Chunk metadata
                chunk_type TEXT,  -- 'semantic', 'fixed', 'paragraph'
                char_start INTEGER,
                char_end INTEGER,

                -- Tokens for BM25 (optional, backup to full-text)
                tokens TEXT[],

                created_at TIMESTAMP DEFAULT NOW(),

                -- Constraints
                CONSTRAINT unique_chunk UNIQUE (document_id, chunk_index)
            );
        """)

        # Document index
        console.print("   Creating document_id index...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_document
            ON document_chunks(document_id);
        """)

        # Full-text search index
        console.print("   Creating full-text search index...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_content_fts
            ON document_chunks
            USING GIN (to_tsvector('portuguese', content));
        """)

        conn.commit()
        console.print("   ✓ Created document_chunks table with indexes", style="green")


def create_vector_index(conn, config: dict):
    """Create vector similarity index."""

    console.print("\n[bold blue]4. Creating vector similarity index...[/bold blue]")

    vector_config = config['vector']
    index_type = vector_config['index_type']

    with conn.cursor() as cur:
        # Check if index already exists
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'document_chunks'
                AND indexname = 'idx_chunks_embedding'
            );
        """)

        exists = cur.fetchone()[0]

        if exists:
            console.print("   ⚠️  Vector index already exists", style="yellow")
            console.print("   To recreate, drop it first: DROP INDEX idx_chunks_embedding;")
            return

        if index_type == 'ivfflat':
            lists = vector_config['ivfflat']['lists']
            distance = vector_config['distance_metric']

            # Map distance metric to operator
            ops = {
                'cosine': 'vector_cosine_ops',
                'l2': 'vector_l2_ops',
                'inner_product': 'vector_ip_ops'
            }

            console.print(f"   Creating IVFFlat index (lists={lists}, metric={distance})...")

            cur.execute(f"""
                CREATE INDEX idx_chunks_embedding
                ON document_chunks
                USING ivfflat (embedding {ops[distance]})
                WITH (lists = {lists});
            """)

        elif index_type == 'hnsw':
            # HNSW is available in pgvector 0.5.0+
            console.print("   Creating HNSW index...")

            cur.execute("""
                CREATE INDEX idx_chunks_embedding
                ON document_chunks
                USING hnsw (embedding vector_cosine_ops);
            """)

        conn.commit()
        console.print("   ✓ Created vector similarity index", style="green")


def configure_pgvector(conn, config: dict):
    """Configure pgvector settings."""

    console.print("\n[bold blue]5. Configuring pgvector settings...[/bold blue]")

    vector_config = config['vector']

    if vector_config['index_type'] == 'ivfflat':
        probes = vector_config['ivfflat']['probes']

        with conn.cursor() as cur:
            cur.execute(f"SET ivfflat.probes = {probes};")
            conn.commit()

        console.print(f"   ✓ Set ivfflat.probes = {probes}", style="green")


def analyze_tables(conn):
    """Run ANALYZE to update statistics."""

    console.print("\n[bold blue]6. Analyzing tables...[/bold blue]")

    with conn.cursor() as cur:
        cur.execute("ANALYZE news_documents;")
        cur.execute("ANALYZE document_chunks;")
        conn.commit()

    console.print("   ✓ Updated table statistics", style="green")


def verify_setup(conn, config: dict):
    """Verify database setup."""

    console.print("\n[bold blue]7. Verifying setup...[/bold blue]")

    checks = []

    with conn.cursor() as cur:
        # Check pgvector extension
        cur.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');")
        checks.append(("pgvector extension", cur.fetchone()[0]))

        # Check tables exist
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'news_documents'
            );
        """)
        checks.append(("news_documents table", cur.fetchone()[0]))

        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'document_chunks'
            );
        """)
        checks.append(("document_chunks table", cur.fetchone()[0]))

        # Check vector index
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'document_chunks'
                AND indexname = 'idx_chunks_embedding'
            );
        """)
        checks.append(("Vector index", cur.fetchone()[0]))

        # Check full-text index
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'document_chunks'
                AND indexname = 'idx_chunks_content_fts'
            );
        """)
        checks.append(("Full-text index", cur.fetchone()[0]))

    # Print results
    all_passed = True
    for check_name, result in checks:
        if result:
            console.print(f"   ✓ {check_name}", style="green")
        else:
            console.print(f"   ✗ {check_name}", style="red")
            all_passed = False

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Setup PostgreSQL database for RAG system")
    parser.add_argument(
        "--config",
        default="config/database.yaml",
        help="Path to database config file"
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing tables (DANGEROUS - will delete all data)"
    )
    parser.add_argument(
        "--skip-vector-index",
        action="store_true",
        help="Skip creating vector index (useful if adding data first)"
    )

    args = parser.parse_args()

    # Load config
    console.print(Panel.fit(
        "[bold cyan]PostgreSQL + pgvector Setup[/bold cyan]\n"
        "[dim]Issue #5: RAG System[/dim]",
        border_style="cyan"
    ))

    console.print(f"\n📋 Loading config from: {args.config}")
    config = load_config(args.config)

    # Warning if drop_existing
    if args.drop_existing:
        console.print("\n[bold red]⚠️  WARNING: --drop-existing will delete all data![/bold red]")
        response = input("Are you sure? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            console.print("Aborted.", style="yellow")
            return

    # Connect to database
    conn_string = get_connection_string(config)
    console.print(f"🔌 Connecting to database: {config['database']['name']}")

    try:
        with psycopg.connect(conn_string) as conn:
            console.print("✓ Connected successfully", style="green")

            # Run setup steps
            create_extension(conn)
            create_documents_table(conn, drop_existing=args.drop_existing)
            create_chunks_table(conn, config, drop_existing=args.drop_existing)

            if not args.skip_vector_index:
                create_vector_index(conn, config)
            else:
                console.print("\n⏭️  Skipping vector index creation", style="yellow")

            configure_pgvector(conn, config)
            analyze_tables(conn)

            # Verify
            all_passed = verify_setup(conn, config)

            if all_passed:
                console.print(
                    Panel.fit(
                        "[bold green]✅ Database setup complete![/bold green]\n\n"
                        "Next steps:\n"
                        "1. Index your corpus: python scripts/index_corpus.py\n"
                        "2. Test retrieval: python scripts/test_retrieval.py\n"
                        "3. Test generation: python scripts/test_generation.py",
                        border_style="green"
                    )
                )
            else:
                console.print(
                    Panel.fit(
                        "[bold red]❌ Setup incomplete[/bold red]\n\n"
                        "Some checks failed. Please review the output above.",
                        border_style="red"
                    )
                )
                sys.exit(1)

    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
