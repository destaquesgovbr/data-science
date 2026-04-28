"""
Templates de prompts para classificação hierárquica de notícias.

Usa taxonomia em 3 níveis (arvore.yaml):
- Nível 1: 25 grandes áreas
- Nível 2: 115 subcategorias
- Nível 3: 500 tópicos específicos

Estratégias:
- Zero-shot: Classificação direta
- Chain-of-Thought: Raciocínio passo a passo (recomendado)
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


def get_zero_shot_prompt(text: str, taxonomy: TaxonomyParser = None) -> str:
    """
    Prompt zero-shot com taxonomia hierárquica.

    Inclui os 3 níveis completos e guia raciocínio hierárquico.
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    # Formatar nível 1 (25 grandes áreas)
    level1_categories = '\n'.join([f"  {cat}" for cat in sorted(taxonomy.get_level1_categories())])

    prompt = f"""Você é um sistema especializado em classificar notícias governamentais brasileiras usando uma taxonomia hierárquica em 3 níveis.

TAXONOMIA (25 grandes áreas):
{level1_categories}

INSTRUÇÕES:
1. Leia a notícia atentamente
2. Identifique a GRANDE ÁREA (nível 1) mais apropriada
3. Dentro dessa área, identifique a SUBCATEGORIA (nível 2) mais específica
4. Dentro da subcategoria, identifique o TÓPICO (nível 3) mais preciso

FORMATO DE RESPOSTA:
Responda APENAS com o código e nome completo do nível 3 no formato:
XX.XX.XX - Nome do Tópico

Exemplo: 01.01.01 - Política Fiscal

NOTÍCIA:
{text}

CLASSIFICAÇÃO:"""

    return prompt


def get_chain_of_thought_prompt(text: str, taxonomy: TaxonomyParser = None) -> str:
    """
    Prompt Chain-of-Thought com raciocínio hierárquico explícito.

    Guia o modelo a pensar em 3 etapas (nível 1 → 2 → 3).
    RECOMENDADO para melhor accuracy.

    IMPORTANTE: Inclui taxonomia completa (500 categorias) no prompt.
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    # Formatar taxonomia COMPLETA de forma compacta mas legível
    # Agrupar por Nível 1, mostrar Nível 2 e listar códigos de Nível 3
    taxonomy_text = []

    for level1 in sorted(set([cat['level1'] for cat in taxonomy.flat_categories])):
        taxonomy_text.append(f"\n{level1}")

        # Pegar subcategorias (nível 2) desta grande área
        level2_cats = sorted(set([cat['level2'] for cat in taxonomy.flat_categories if cat['level1'] == level1]))

        for level2 in level2_cats:
            # Pegar tópicos (nível 3) desta subcategoria
            level3_cats = [cat for cat in taxonomy.flat_categories if cat['level2'] == level2]

            # Listar apenas códigos (economiza espaço)
            level3_codes = ', '.join([cat['level3_code'] for cat in level3_cats])
            taxonomy_text.append(f"  {level2}: [{level3_codes}]")

    taxonomy_full = '\n'.join(taxonomy_text)

    prompt = f"""Você é um sistema especializado em classificar notícias governamentais brasileiras.

TAXONOMIA OFICIAL COMPLETA (3 NÍVEIS):
{taxonomy_full}

INSTRUÇÕES CRÍTICAS:
1. Você DEVE escolher um código que EXISTE na taxonomia acima
2. NÃO invente códigos novos (ex: 03.02.10, 11.01.35)
3. Escolha o tópico mais ESPECÍFICO (nível 3) que descreve a notícia
4. Se tiver dúvida, escolha o código mais PRÓXIMO do tema principal

PROCESSO MENTAL:
1. Identifique a GRANDE ÁREA (nível 1): Qual das 25 áreas? (Ex: 03 - Saúde)
2. Identifique a SUBCATEGORIA (nível 2): Qual aspecto? (Ex: 03.02 - Campanhas)
3. Identifique o TÓPICO (nível 3): Qual dos códigos listados? (Ex: 03.02.01)

FORMATO DA RESPOSTA:
Retorne EXATAMENTE no formato:
XX.XX.XX - Nome Completo do Tópico

Exemplos corretos:
01.01.01 - Política Fiscal
03.02.01 - Combate à Dengue
07.02.01 - Transporte Público

REGRAS ESTRITAS:
- Retorne APENAS uma linha
- NÃO adicione prefixos ("Código:", "Resposta:", etc)
- NÃO adicione explicações antes ou depois
- O código DEVE estar na lista acima

NOTÍCIA A CLASSIFICAR:
{text}

SUA RESPOSTA (apenas XX.XX.XX - Nome):"""

    return prompt


def get_few_shot_prompt(text: str, taxonomy: TaxonomyParser = None) -> str:
    """
    Prompt few-shot com exemplos de classificação hierárquica.

    Mostra 5 exemplos antes de classificar.
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    examples = """
Exemplo 1:
Notícia: "Ministério da Saúde lança nova fase de vacinação contra Covid-19 para crianças de 5 a 11 anos."
Classificação: 03.02.02 - Saúde da Criança

Exemplo 2:
Notícia: "Banco Central mantém taxa Selic em 10,75% ao ano pela terceira reunião consecutiva do Copom."
Classificação: 01.01.01 - Política Fiscal

Exemplo 3:
Notícia: "MEC divulga resultado do ENEM 2024 com mais de 4 milhões de candidatos inscritos."
Classificação: 02.04.05 - Apoio e Desenvolvimento Acadêmico

Exemplo 4:
Notícia: "Ibama autua fazendeiros por desmatamento ilegal na Amazônia e aplica multas de R$ 50 milhões."
Classificação: 05.01.01 - Proteção da Vida Selvagem

Exemplo 5:
Notícia: "Polícia Federal deflagra operação contra tráfico de drogas em 12 estados."
Classificação: 04.02.02 - Operações Contra o Tráfico de Drogas
"""

    prompt = f"""Você é um sistema especializado em classificar notícias governamentais brasileiras usando uma taxonomia hierárquica em 3 níveis.

EXEMPLOS DE CLASSIFICAÇÃO:
{examples}

INSTRUÇÕES:
1. Analise a notícia
2. Identifique: Grande Área → Subcategoria → Tópico Específico
3. Responda com o código completo: XX.XX.XX - Nome do Tópico

NOTÍCIA:
{text}

CLASSIFICAÇÃO:"""

    return prompt


def get_prompt(text: str, taxonomy: TaxonomyParser = None, strategy: str = 'chain-of-thought') -> str:
    """
    Retorna prompt baseado na estratégia escolhida.

    Args:
        text: Texto a classificar
        taxonomy: Parser da taxonomia (opcional, carrega automaticamente)
        strategy: 'zero-shot', 'few-shot', ou 'chain-of-thought'

    Returns:
        Prompt formatado
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    if strategy == 'few-shot':
        return get_few_shot_prompt(text, taxonomy)
    elif strategy == 'zero-shot':
        return get_zero_shot_prompt(text, taxonomy)
    else:
        # Chain-of-thought é o padrão (melhor para hierarquia)
        return get_chain_of_thought_prompt(text, taxonomy)
