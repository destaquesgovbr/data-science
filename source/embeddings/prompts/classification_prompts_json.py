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


def get_prompt_json_explicit(text: str, taxonomy: TaxonomyParser = None) -> str:
    """
    Prompt com instruções MUITO explícitas sobre formatação JSON.

    Útil para modelos que têm dificuldade com parsing JSON (ex: Mistral).

    Args:
        text: Texto da notícia
        taxonomy: Parser da taxonomia

    Returns:
        Prompt com instruções explícitas
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    taxonomy_formatted = format_taxonomy_for_prompt(taxonomy)
    text_preview = text[:2000] if len(text) > 2000 else text

    prompt = f"""Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido.

TAXONOMIA DISPONÍVEL:
{taxonomy_formatted}

NOTÍCIA:
{text_preview}

FORMATO DE SAÍDA - RETORNE EXATAMENTE ESTE JSON (substituindo os valores):
{{
  "theme_1_level_1": "Nome da Grande Área",
  "theme_1_level_1_code": "XX",
  "theme_1_level_1_label": "Nome da Grande Área",
  "theme_1_level_2_code": "XX.XX",
  "theme_1_level_2_label": "Nome da Subcategoria",
  "theme_1_level_3_code": "XX.XX.XX",
  "theme_1_level_3_label": "Nome do Tópico Específico",
  "most_specific_theme_code": "XX.XX.XX",
  "most_specific_theme_label": "Nome do Tópico Específico",
  "summary": "Breve resumo da notícia"
}}

REGRAS EXTREMAMENTE IMPORTANTES:
1. Retorne APENAS o JSON acima
2. NÃO inclua ```json ou qualquer outra formatação markdown
3. NÃO adicione texto antes ou depois do JSON
4. NÃO invente códigos - use APENAS os códigos da taxonomia acima
5. Todos os campos são obrigatórios (summary pode ser string vazia "")
6. Use aspas duplas (") para strings
7. most_specific_theme_code DEVE ser igual a theme_1_level_3_code
8. Os códigos seguem o padrão: XX (nível 1), XX.XX (nível 2), XX.XX.XX (nível 3)

IMPORTANTE: Sua resposta deve começar com {{ e terminar com }}. Nada mais.

RESPOSTA JSON:"""

    return prompt


def get_prompt_json_fewshot(text: str, taxonomy: TaxonomyParser = None, num_examples: int = 3) -> str:
    """
    Prompt com few-shot examples para guiar o modelo.

    Args:
        text: Texto da notícia
        taxonomy: Parser da taxonomia
        num_examples: Número de exemplos (2 ou 3)

    Returns:
        Prompt com exemplos
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    taxonomy_formatted = format_taxonomy_for_prompt(taxonomy)
    text_preview = text[:2000] if len(text) > 2000 else text

    # Exemplos reais do dataset
    examples = [
        {
            'text': 'Governo federal anuncia R$ 10 bilhões em crédito rural para pequenos produtores na safra 2024/2025. Os recursos serão destinados ao custeio e investimento na agricultura familiar.',
            'json': '''{
  "theme_1_level_1": "Agricultura",
  "theme_1_level_1_code": "10",
  "theme_1_level_1_label": "Agricultura",
  "theme_1_level_2_code": "10.03",
  "theme_1_level_2_label": "Financiamento Agrícola",
  "theme_1_level_3_code": "10.03.02",
  "theme_1_level_3_label": "Crédito Agrícola",
  "most_specific_theme_code": "10.03.02",
  "most_specific_theme_label": "Crédito Agrícola",
  "summary": "Governo anuncia R$ 10 bilhões em crédito rural para agricultura familiar."
}'''
        },
        {
            'text': 'Ministério da Saúde lança campanha nacional de vacinação contra a gripe. Grupos prioritários incluem idosos, crianças e gestantes. Meta é imunizar 90% do público-alvo.',
            'json': '''{
  "theme_1_level_1": "Saúde",
  "theme_1_level_1_code": "18",
  "theme_1_level_1_label": "Saúde",
  "theme_1_level_2_code": "18.02",
  "theme_1_level_2_label": "Atenção à Saúde",
  "theme_1_level_3_code": "18.02.02",
  "theme_1_level_3_label": "Imunização",
  "most_specific_theme_code": "18.02.02",
  "most_specific_theme_label": "Imunização",
  "summary": "Ministério lança campanha de vacinação contra gripe com meta de 90%."
}'''
        },
        {
            'text': 'BNDES aprova financiamento de R$ 500 milhões para construção de nova rodovia federal no Nordeste. Obra deve gerar 2 mil empregos diretos.',
            'json': '''{
  "theme_1_level_1": "Infraestrutura",
  "theme_1_level_1_code": "07",
  "theme_1_level_1_label": "Infraestrutura",
  "theme_1_level_2_code": "07.01",
  "theme_1_level_2_label": "Rodovias",
  "theme_1_level_3_code": "07.01.01",
  "theme_1_level_3_label": "Construção de Estradas",
  "most_specific_theme_code": "07.01.01",
  "most_specific_theme_label": "Construção de Estradas",
  "summary": "BNDES aprova R$ 500 milhões para construção de rodovia no Nordeste."
}'''
        }
    ]

    # Selecionar número de exemplos
    selected_examples = examples[:num_examples]

    examples_text = "\n\n".join([
        f"EXEMPLO {i+1}:\nNOTÍCIA: {ex['text']}\nRESPOSTA: {ex['json']}"
        for i, ex in enumerate(selected_examples)
    ])

    prompt = f"""Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido (sem markdown, sem explicações).

TAXONOMIA DISPONÍVEL:
{taxonomy_formatted}

EXEMPLOS DE CLASSIFICAÇÃO:

{examples_text}

AGORA CLASSIFIQUE ESTA NOTÍCIA:
{text_preview}

FORMATO DE SAÍDA (JSON VÁLIDO):
{{
  "theme_1_level_1": "Nome da Grande Área",
  "theme_1_level_1_code": "XX",
  "theme_1_level_1_label": "Nome da Grande Área",
  "theme_1_level_2_code": "XX.XX",
  "theme_1_level_2_label": "Nome da Subcategoria",
  "theme_1_level_3_code": "XX.XX.XX",
  "theme_1_level_3_label": "Nome do Tópico Específico",
  "most_specific_theme_code": "XX.XX.XX",
  "most_specific_theme_label": "Nome do Tópico Específico",
  "summary": "Breve resumo"
}}

REGRAS CRÍTICAS:
- Retorne APENAS o JSON (sem ```json)
- Use APENAS códigos da taxonomia fornecida
- NÃO invente códigos
- Siga o formato dos exemplos acima

RESPOSTA JSON:"""

    return prompt
