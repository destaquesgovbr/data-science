"""
Templates de prompts para classificação de notícias.

Suporta 3 estratégias:
- Zero-shot: Direto ao ponto
- Few-shot: Com exemplos
- Chain-of-Thought: Raciocínio passo a passo
"""


def get_categories_list(categories):
    """Formata lista de categorias para o prompt."""
    return '\n'.join([f'- {cat}' for cat in categories])


def get_zero_shot_prompt(text: str, categories: list) -> str:
    """
    Prompt zero-shot: classificação direta.

    Simples e direto, economiza tokens.
    """
    categories_str = get_categories_list(categories)

    prompt = f"""Você é um sistema especializado em classificar notícias governamentais brasileiras.

Classifique a notícia abaixo em UMA das seguintes categorias:
{categories_str}

IMPORTANTE:
- Retorne APENAS o nome da categoria, sem explicações
- Escolha a categoria mais específica e relevante
- Se não tiver certeza, escolha "Outros"

Notícia:
{text}

Categoria:"""

    return prompt


def get_few_shot_prompt(text: str, categories: list) -> str:
    """
    Prompt few-shot: com exemplos.

    Melhora performance mostrando exemplos de classificação.
    """
    categories_str = get_categories_list(categories)

    # Exemplos fixos (escolhidos para cobrir categorias principais)
    examples = """
Exemplo 1:
Notícia: "Ministério da Saúde anuncia nova fase de vacinação contra Covid-19 para crianças de 5 a 11 anos em todo território nacional."
Categoria: Saúde

Exemplo 2:
Notícia: "Banco Central mantém taxa Selic em 10,75% ao ano pela terceira reunião consecutiva do Copom."
Categoria: Economia

Exemplo 3:
Notícia: "MEC divulga resultado do ENEM 2024 com mais de 4 milhões de candidatos inscritos."
Categoria: Educação

Exemplo 4:
Notícia: "Ibama autua fazendeiros por desmatamento ilegal na Amazônia e aplica multas de R$ 50 milhões."
Categoria: Meio Ambiente

Exemplo 5:
Notícia: "Embrapa desenvolve nova variedade de milho resistente à seca para agricultores do Nordeste."
Categoria: Agricultura
"""

    prompt = f"""Você é um sistema especializado em classificar notícias governamentais brasileiras.

Categorias disponíveis:
{categories_str}

{examples}

Agora classifique a seguinte notícia:
Notícia: {text}

IMPORTANTE: Retorne APENAS o nome da categoria, sem explicações.

Categoria:"""

    return prompt


def get_chain_of_thought_prompt(text: str, categories: list) -> str:
    """
    Prompt Chain-of-Thought: raciocínio explícito.

    Modelo explica o raciocínio antes de classificar.
    Melhor para casos ambíguos, mas usa mais tokens.
    """
    categories_str = get_categories_list(categories)

    prompt = f"""Você é um sistema especializado em classificar notícias governamentais brasileiras.

Categorias disponíveis:
{categories_str}

Analise a notícia abaixo seguindo estes passos:

1. Identifique o órgão ou ministério governamental mencionado
2. Identifique o tema principal da notícia
3. Identifique palavras-chave relevantes
4. Com base nessa análise, determine a categoria mais apropriada

Notícia:
{text}

Pense passo a passo:

1. Órgão/Ministério:
2. Tema principal:
3. Palavras-chave:
4. Categoria: """

    return prompt


def get_prompt(text: str, categories: list, strategy: str = 'zero-shot') -> str:
    """
    Retorna prompt baseado na estratégia escolhida.

    Args:
        text: Texto a classificar
        categories: Lista de categorias válidas
        strategy: 'zero-shot', 'few-shot', ou 'chain-of-thought'

    Returns:
        Prompt formatado
    """
    if strategy == 'few-shot':
        return get_few_shot_prompt(text, categories)
    elif strategy == 'chain-of-thought' or strategy == 'cot':
        return get_chain_of_thought_prompt(text, categories)
    else:
        return get_zero_shot_prompt(text, categories)
