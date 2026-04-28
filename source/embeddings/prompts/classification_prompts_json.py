"""
Templates de prompts JSON para classificação hierárquica de notícias.

Usa o mesmo formato da implementação working em news-enrichment:
Retorna JSON com campos separados para cada nível da hierarquia.

Baseado em: source/news-enrichment/news_enrichment/llm_client.py
"""

from pathlib import Path
import sys

# Adicionar path para importar TaxonomyParser
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.utils.taxonomy_parser import TaxonomyParser


def load_taxonomy():
    """Carrega taxonomia do arquivo arvore.yaml."""
    taxonomy_path = BASE_DIR / "data" / "classification" / "arvore.yaml"
    return TaxonomyParser(taxonomy_path)


def format_taxonomy_for_prompt(taxonomy: TaxonomyParser) -> str:
    """
    Formata taxonomia de forma compacta para inclusão no prompt.

    Formato:
    01 - Economia e Finanças
      01.01 - Política Econômica: [01.01.01 - Política Fiscal, 01.01.02 - Autonomia Econômica, ...]
      01.02 - Fiscalização: [01.02.01 - ..., 01.02.02 - ...]
    """
    taxonomy_text = []

    for level1 in sorted(set([cat['level1'] for cat in taxonomy.flat_categories])):
        taxonomy_text.append(f"\n{level1}")

        # Pegar subcategorias (nível 2) desta grande área
        level2_cats = sorted(set([cat['level2'] for cat in taxonomy.flat_categories if cat['level1'] == level1]))

        for level2 in level2_cats:
            # Pegar tópicos (nível 3) desta subcategoria
            level3_cats = [cat for cat in taxonomy.flat_categories if cat['level2'] == level2]

            # Listar códigos e nomes (primeiro 3 por brevidade)
            level3_items = [f"{cat['level3_code']} - {cat['level3']}" for cat in level3_cats[:3]]
            if len(level3_cats) > 3:
                level3_items.append(f"... e mais {len(level3_cats) - 3}")
            level3_list = ', '.join(level3_items)
            taxonomy_text.append(f"  {level2}: [{level3_list}]")

    return '\n'.join(taxonomy_text)


def get_json_classification_prompt(text: str, taxonomy: TaxonomyParser = None) -> str:
    """
    Prompt que retorna classificação em formato JSON.

    Segue o formato working da implementação news-enrichment:
    - Retorna JSON com campos separados para cada nível
    - Inclui theme_1_level_1_code, theme_1_level_2_code, theme_1_level_3_code
    - Inclui most_specific_theme_code (nível 3)
    - Inclui summary opcional

    Args:
        text: Texto da notícia a classificar
        taxonomy: Parser da taxonomia (carrega automaticamente se None)

    Returns:
        Prompt formatado
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    # Formatar taxonomia completa
    taxonomy_formatted = format_taxonomy_for_prompt(taxonomy)

    # Limitar texto para não exceder contexto (similar ao working: 2000 chars)
    text_preview = text[:2000] if len(text) > 2000 else text

    prompt = f"""Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido (sem markdown, sem explicações).

INSTRUÇÕES:
Escolha as categorias da taxonomia abaixo que melhor se adequam à notícia.
Use EXATAMENTE os códigos e labels fornecidos na taxonomia.

TAXONOMIA DISPONÍVEL:
{taxonomy_formatted}

NOTÍCIA:
{text_preview}

FORMATO DE SAÍDA (JSON VÁLIDO):
{{
  "theme_1_level_1": "Economia e Finanças",
  "theme_1_level_1_code": "01",
  "theme_1_level_1_label": "Economia e Finanças",
  "theme_1_level_2_code": "01.02",
  "theme_1_level_2_label": "Fiscalização e Tributação",
  "theme_1_level_3_code": "01.02.03",
  "theme_1_level_3_label": "Reforma Tributária",
  "most_specific_theme_code": "01.02.03",
  "most_specific_theme_label": "Reforma Tributária",
  "summary": "Governo federal anuncia proposta de reforma tributária."
}}

REGRAS CRÍTICAS:
- Retorne APENAS o JSON (sem ```json ou explicações)
- Os códigos DEVEM existir na taxonomia acima
- NÃO invente códigos (ex: 03.02.10, 11.01.35)
- theme_1_level_3_code é o mais específico (XX.XX.XX)
- most_specific_theme_code = theme_1_level_3_code
- summary é opcional (pode ser string vazia)

RESPOSTA JSON:"""

    return prompt


def get_prompt_json(text: str, taxonomy: TaxonomyParser = None) -> str:
    """
    Wrapper para manter compatibilidade com código existente.

    Retorna prompt JSON (única estratégia neste módulo).
    """
    return get_json_classification_prompt(text, taxonomy)
