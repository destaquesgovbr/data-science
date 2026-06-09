"""
Carrega taxonomia de temas do PostgreSQL para uso no classificador LLM.

A tabela `themes` contém a taxonomia hierárquica de 3 níveis usada para
classificar notícias governamentais. Este módulo carrega essa taxonomia
e a formata para o prompt do LLM.
"""

import logging
from typing import Dict, Optional

import psycopg2

logger = logging.getLogger(__name__)


def load_taxonomy_from_postgres(database_url: str) -> Dict:
    """
    Carrega árvore de temas do PostgreSQL no formato esperado pelo BedrockLLMClient.

    Args:
        database_url: Connection string PostgreSQL

    Returns:
        Dict hierárquico no formato:
        {
            "01": {
                "label": "Economia e Finanças",
                "subcategories": {
                    "01.01": {
                        "label": "Política Econômica",
                        "subcategories": {
                            "01.01.01": {"label": "Inflação"}
                        }
                    }
                }
            }
        }
    """
    query = """
        SELECT code, label, level, parent_code
        FROM themes
        ORDER BY code
    """

    conn = psycopg2.connect(database_url)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    logger.info(f"Carregadas {len(rows)} categorias da tabela themes")

    # Construir hierarquia
    taxonomy = {}

    # Primeiro pass: nível 1
    for code, label, level, parent_code in rows:
        if level == 1:
            taxonomy[code] = {"label": label, "subcategories": {}}

    # Segundo pass: nível 2
    for code, label, level, parent_code in rows:
        if level == 2 and parent_code in taxonomy:
            taxonomy[parent_code]["subcategories"][code] = {
                "label": label,
                "subcategories": {},
            }

    # Terceiro pass: nível 3
    for code, label, level, parent_code in rows:
        if level == 3:
            # Encontrar o pai (nível 2) dentro da taxonomia
            for l1_code, l1_data in taxonomy.items():
                if parent_code in l1_data["subcategories"]:
                    l1_data["subcategories"][parent_code]["subcategories"][code] = {
                        "label": label
                    }
                    break

    # Estatísticas
    l1 = len(taxonomy)
    l2 = sum(len(v["subcategories"]) for v in taxonomy.values())
    l3 = sum(
        len(sub["subcategories"])
        for v in taxonomy.values()
        for sub in v["subcategories"].values()
    )
    logger.info(f"Taxonomia: {l1} L1, {l2} L2, {l3} L3 ({l1 + l2 + l3} total)")

    return taxonomy


def build_theme_code_to_id_map(database_url: str) -> Dict[str, int]:
    """
    Constrói mapeamento de theme code → theme id para UPDATE no PostgreSQL.

    Args:
        database_url: Connection string PostgreSQL

    Returns:
        Dict {"01": 1, "01.01": 5, "01.01.01": 15, ...}
    """
    query = "SELECT code, id FROM themes"

    conn = psycopg2.connect(database_url)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    code_to_id = {code: theme_id for code, theme_id in rows}
    logger.info(f"Mapeamento code→id: {len(code_to_id)} temas")

    return code_to_id
