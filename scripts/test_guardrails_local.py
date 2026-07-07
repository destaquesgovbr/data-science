#!/usr/bin/env python3
"""
Script de teste para Content Safety Guardrails em dados reais.

Conecta no PostgreSQL local, busca resumos existentes, roda guardrails
e gera relatório de bloqueios.

Usage:
    poetry run python scripts/test_guardrails_local.py --sample 1000
"""

import argparse
import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

# Adiciona src/ ao path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from news_enrichment.llm_client import check_content_safety_regex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Retorna DATABASE_URL do ambiente ou usa default local."""
    import os

    # Tenta pegar do env
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url

    # Default: PostgreSQL RAG (porta 5433) com corpus de 50k notícias
    return "postgresql://rag_user:rag_password_2024@localhost:5433/news_db"


def fetch_summaries(database_url: str, limit: int = 1000) -> List[Dict]:
    """
    Busca sample de resumos do PostgreSQL.

    Args:
        database_url: Connection string
        limit: Número máximo de resumos a buscar

    Returns:
        Lista de dicts com {unique_id, title, summary, agency_name}
    """
    logger.info(f"Conectando em {database_url.split('@')[1]}...")

    conn = psycopg2.connect(database_url)
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Busca resumos existentes (não-NULL) em ordem aleatória
        query = """
            SELECT
                unique_id,
                title,
                summary,
                source_agency as agency_name,
                published_at
            FROM news_corpus_repository
            WHERE summary IS NOT NULL
              AND summary != ''
            ORDER BY RANDOM()
            LIMIT %s
        """

        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        cursor.close()

        logger.info(f"✓ Encontrados {len(rows)} resumos para teste")
        return [dict(row) for row in rows]

    finally:
        conn.close()


def test_guardrails_regex_only(summaries: List[Dict]) -> Dict:
    """
    Testa guardrails (APENAS REGEX) em lista de resumos.

    Args:
        summaries: Lista de dicts com 'summary'

    Returns:
        Dict com estatísticas e lista de bloqueios
    """
    logger.info(f"Testando guardrails em {len(summaries)} resumos...")
    logger.info("NOTA: Testando APENAS regex (sem LLM)")

    results = {
        "total": len(summaries),
        "blocked": 0,
        "approved": 0,
        "blocked_items": [],
        "blocked_reasons": Counter(),
        "processing_time_ms": 0
    }

    start = time.time()

    for i, item in enumerate(summaries, 1):
        summary = item.get("summary", "")

        if not summary:
            continue

        # Testa guardrails (APENAS REGEX)
        is_safe, blocked_reason = check_content_safety_regex(summary)

        if not is_safe:
            results["blocked"] += 1
            results["blocked_reasons"][blocked_reason] += 1
            results["blocked_items"].append({
                "unique_id": item.get("unique_id"),
                "title": item.get("title"),
                "summary": summary[:200],  # primeiros 200 chars
                "reason": blocked_reason,
                "agency": item.get("agency_name")
            })
        else:
            results["approved"] += 1

        # Progress log a cada 100
        if i % 100 == 0:
            logger.info(f"Processados {i}/{len(summaries)} "
                       f"(bloqueados: {results['blocked']}, "
                       f"taxa: {results['blocked']/i*100:.2f}%)")

    elapsed_ms = (time.time() - start) * 1000
    results["processing_time_ms"] = elapsed_ms
    results["avg_time_per_summary_ms"] = elapsed_ms / len(summaries)

    return results


def print_report(results: Dict) -> None:
    """Imprime relatório formatado dos resultados."""

    print("\n" + "="*80)
    print("📊 RELATÓRIO DE TESTE - CONTENT SAFETY GUARDRAILS")
    print("="*80)

    print(f"\n📈 ESTATÍSTICAS GERAIS:")
    print(f"   Total de resumos testados:  {results['total']}")
    print(f"   ✅ Aprovados:                {results['approved']} ({results['approved']/results['total']*100:.2f}%)")
    print(f"   ❌ Bloqueados:               {results['blocked']} ({results['blocked']/results['total']*100:.2f}%)")

    print(f"\n⏱️  PERFORMANCE:")
    print(f"   Tempo total:                {results['processing_time_ms']:.0f} ms")
    print(f"   Tempo médio por resumo:     {results['avg_time_per_summary_ms']:.2f} ms")

    if results['blocked'] > 0:
        print(f"\n🚫 MOTIVOS DE BLOQUEIO:")
        for reason, count in results['blocked_reasons'].most_common():
            pct = count / results['blocked'] * 100
            print(f"   {reason:30s}  {count:4d} ({pct:5.1f}%)")

        print(f"\n📋 AMOSTRAS DE BLOQUEIOS (primeiras 10):")
        for i, item in enumerate(results['blocked_items'][:10], 1):
            print(f"\n   [{i}] {item['title'][:60]}...")
            print(f"       ID: {item['unique_id']}")
            print(f"       Agência: {item['agency']}")
            print(f"       Motivo: {item['reason']}")
            print(f"       Resumo: {item['summary'][:150]}...")

    print("\n" + "="*80)

    # Verifica taxa de bloqueio
    block_rate = results['blocked'] / results['total'] * 100

    if block_rate > 2.0:
        print("⚠️  ALERTA: Taxa de bloqueio > 2% - revisar para falsos positivos!")
    elif block_rate > 1.0:
        print("⚠️  ATENÇÃO: Taxa de bloqueio > 1% - validar amostras bloqueadas")
    else:
        print("✅ Taxa de bloqueio < 1% - dentro do esperado!")

    print("="*80 + "\n")


def save_results(results: Dict, output_file: str = "guardrails_test_results.json") -> None:
    """Salva resultados em arquivo JSON."""

    output_path = Path(__file__).parent / output_file

    # Adiciona metadata
    results["test_metadata"] = {
        "timestamp": datetime.now().isoformat(),
        "test_mode": "regex_only",
        "note": "LLM verification not tested (requires AWS credentials)"
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"✓ Resultados salvos em: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Testa Content Safety Guardrails em resumos do PostgreSQL local"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=1000,
        help="Número de resumos a testar (default: 1000)"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        help="PostgreSQL connection string (default: localhost:5433)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="guardrails_test_results.json",
        help="Arquivo de saída para resultados JSON"
    )

    args = parser.parse_args()

    try:
        # 1. Conecta e busca resumos
        db_url = args.database_url or get_database_url()
        summaries = fetch_summaries(db_url, limit=args.sample)

        if not summaries:
            logger.error("❌ Nenhum resumo encontrado no banco!")
            return 1

        # 2. Testa guardrails
        results = test_guardrails_regex_only(summaries)

        # 3. Imprime relatório
        print_report(results)

        # 4. Salva resultados
        save_results(results, output_file=args.output)

        logger.info("✓ Teste concluído com sucesso!")
        return 0

    except psycopg2.OperationalError as e:
        logger.error(f"❌ Erro ao conectar no PostgreSQL: {e}")
        logger.error("   Certifique-se de que o PostgreSQL está rodando:")
        logger.error("   $ docker-compose up -d postgres")
        return 1

    except Exception as e:
        logger.error(f"❌ Erro inesperado: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
