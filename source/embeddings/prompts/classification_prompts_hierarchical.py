"""
Prompts para classificação hierárquica em 3 etapas.

Reduz drasticamente o tamanho do prompt dividindo em:
- Nível 1: Grandes áreas (10-20 opções)
- Nível 2: Subcategorias (dado L1, 5-30 opções)
- Nível 3: Tópicos específicos (dado L2, 3-20 opções)

Permite que modelos pequenos (2B-3B) processem sem timeout.
"""

import re
from typing import Dict, List


def get_level1_categories(taxonomy) -> List[Dict]:
    """Extrai apenas categorias de nível 1 da taxonomia."""
    level1_categories = []

    # Usar flat_categories do TaxonomyParser
    seen = set()
    for cat in taxonomy.flat_categories:
        code = cat['level1_code']
        label = cat['level1_name']

        key = f"{code}_{label}"
        if key not in seen:
            seen.add(key)
            level1_categories.append({
                'code': code,
                'label': label
            })

    return sorted(level1_categories, key=lambda x: x['code'])


def get_level2_categories(taxonomy, level1_code: str) -> List[Dict]:
    """Extrai categorias de nível 2 para um dado nível 1."""
    level2_categories = []

    seen = set()
    for cat in taxonomy.flat_categories:
        if cat['level1_code'] == level1_code:
            code = cat['level2_code']
            label = cat['level2_name']

            key = f"{code}_{label}"
            if key not in seen:
                seen.add(key)
                level2_categories.append({
                    'code': code,
                    'label': label
                })

    return sorted(level2_categories, key=lambda x: x['code'])


def get_level3_categories(taxonomy, level2_code: str) -> List[Dict]:
    """Extrai categorias de nível 3 para um dado nível 2."""
    level3_categories = []

    for cat in taxonomy.flat_categories:
        if cat['level2_code'] == level2_code:
            level3_categories.append({
                'code': cat['level3_code'],
                'label': cat['level3_name']
            })

    return sorted(level3_categories, key=lambda x: x['code'])


def get_prompt_level1(text: str, taxonomy) -> str:
    """Prompt para classificação de nível 1 (grande área)."""

    level1_cats = get_level1_categories(taxonomy)

    # Montar lista de categorias
    categories_text = "\n".join([
        f"  - {cat['code']}: {cat['label']}"
        for cat in level1_cats
    ])

    prompt = f"""Você é um classificador de notícias governamentais brasileiras.

Classifique a notícia abaixo em UMA das seguintes GRANDES ÁREAS (Nível 1):

{categories_text}

**Instruções:**
1. Leia a notícia com atenção
2. Identifique o tema PRINCIPAL
3. Escolha a categoria de Nível 1 mais apropriada
4. Retorne APENAS o código (ex: "01")

**Notícia:**
{text[:2000]}

**Classificação (apenas o código):**"""

    return prompt


def get_prompt_level2(text: str, taxonomy, level1_code: str) -> str:
    """Prompt para classificação de nível 2 (subcategoria)."""

    level2_cats = get_level2_categories(taxonomy, level1_code)

    if not level2_cats:
        return None

    # Montar lista de subcategorias
    categories_text = "\n".join([
        f"  - {cat['code']}: {cat['label']}"
        for cat in level2_cats
    ])

    prompt = f"""Você é um classificador de notícias governamentais brasileiras.

A notícia foi classificada na grande área "{level1_code}".

Agora, classifique em UMA das seguintes SUBCATEGORIAS (Nível 2):

{categories_text}

**Instruções:**
1. Leia a notícia com atenção
2. Identifique a subcategoria mais específica dentro da área "{level1_code}"
3. Retorne APENAS o código (ex: "01.03")

**Notícia:**
{text[:2000]}

**Classificação (apenas o código):**"""

    return prompt


def extract_level1_code(response: str) -> str:
    """
    Extrai código de nível 1 (2 dígitos) da resposta do modelo.
    Múltiplos fallbacks para lidar com respostas verbosas.

    Args:
        response: Resposta bruta do modelo

    Returns:
        Código L1 (ex: "01") ou string vazia se falhar
    """
    response = response.strip()

    # Estratégia 1: Primeiro padrão "NN" (2 dígitos isolados)
    match = re.search(r'\b(\d{2})\b', response)
    if match:
        return match.group(1)

    # Estratégia 2: Início da resposta com dígitos
    match = re.match(r'^[^\d]*(\d{2})', response)
    if match:
        return match.group(1)

    # Estratégia 3: Qualquer sequência de 2 dígitos
    digits = re.findall(r'\d+', response)
    for d in digits:
        if len(d) == 2:
            return d
        if len(d) > 2:
            return d[:2]

    # Estratégia 4: Pegar primeiros 2 dígitos encontrados
    all_digits = ''.join(c for c in response if c.isdigit())
    if len(all_digits) >= 2:
        return all_digits[:2]

    return ''


def extract_level2_code(response: str, level1_code: str) -> str:
    """
    Extrai código de nível 2 (formato NN.NN) da resposta do modelo.

    Args:
        response: Resposta bruta do modelo
        level1_code: Código L1 já extraído (para validação)

    Returns:
        Código L2 (ex: "01.03") ou string vazia se falhar
    """
    response = response.strip()

    # Estratégia 1: Padrão NN.NN exato
    match = re.search(r'\b(\d{2})\.(\d{2})\b', response)
    if match:
        code = f"{match.group(1)}.{match.group(2)}"
        # Validar que L1 bate
        if code.startswith(level1_code + '.'):
            return code
        # Se não bater, tentar construir com L1 correto
        return f"{level1_code}.{match.group(2)}"

    # Estratégia 2: Início da resposta
    match = re.match(r'^[^\d]*(\d{2})[^\d]*(\d{2})', response)
    if match:
        return f"{level1_code}.{match.group(2)}"

    # Estratégia 3: Encontrar qualquer NN.NN e forçar L1 correto
    match = re.search(r'(\d{2})\.(\d{2})', response)
    if match:
        return f"{level1_code}.{match.group(2)}"

    # Estratégia 4: Buscar 2º par de dígitos (assumindo que 1º é L1)
    digits = re.findall(r'\d{2,}', response)
    if len(digits) >= 2:
        l2_suffix = digits[1][:2] if len(digits[1]) >= 2 else digits[1].zfill(2)
        return f"{level1_code}.{l2_suffix}"

    return ''


def extract_level3_code(response: str, level2_code: str) -> str:
    """
    Extrai código de nível 3 (formato NN.NN.NN) da resposta do modelo.

    Args:
        response: Resposta bruta do modelo
        level2_code: Código L2 já extraído (para validação)

    Returns:
        Código L3 (ex: "01.03.02") ou string vazia se falhar
    """
    response = response.strip()

    # Estratégia 1: Padrão NN.NN.NN completo
    match = re.search(r'\b(\d{2})\.(\d{2})\.(\d{2})\b', response)
    if match:
        code = f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
        # Validar que L2 bate
        if code.startswith(level2_code + '.'):
            return code
        # Se não bater, construir com L2 correto
        return f"{level2_code}.{match.group(3)}"

    # Estratégia 2: Início da resposta
    match = re.match(r'^[^\d]*(\d{2})[^\d]*(\d{2})[^\d]*(\d{2})', response)
    if match:
        return f"{level2_code}.{match.group(3)}"

    # Estratégia 3: Qualquer NN.NN.NN e forçar L2 correto
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{2})', response)
    if match:
        return f"{level2_code}.{match.group(3)}"

    # Estratégia 4: Buscar 3º par de dígitos
    digits = re.findall(r'\d{2,}', response)
    if len(digits) >= 3:
        l3_suffix = digits[2][:2] if len(digits[2]) >= 2 else digits[2].zfill(2)
        return f"{level2_code}.{l3_suffix}"

    # Estratégia 5: Pegar últimos 2 dígitos
    all_digits = ''.join(c for c in response if c.isdigit())
    if len(all_digits) >= 2:
        l3_suffix = all_digits[-2:]
        return f"{level2_code}.{l3_suffix}"

    return ''


def get_prompt_level3(text: str, taxonomy, level2_code: str) -> str:
    """Prompt para classificação de nível 3 (tópico específico)."""

    level3_cats = get_level3_categories(taxonomy, level2_code)

    if not level3_cats:
        return None

    # Montar lista de tópicos
    categories_text = "\n".join([
        f"  - {cat['code']}: {cat['label']}"
        for cat in level3_cats
    ])

    prompt = f"""Você é um classificador de notícias governamentais brasileiras.

A notícia foi classificada na subcategoria "{level2_code}".

Agora, classifique em UM dos seguintes TÓPICOS ESPECÍFICOS (Nível 3):

{categories_text}

**Instruções:**
1. Leia a notícia com atenção
2. Identifique o tópico mais específico dentro da subcategoria "{level2_code}"
3. Retorne APENAS o código completo (ex: "01.03.02")

**Notícia:**
{text[:2000]}

**Classificação (apenas o código):**"""

    return prompt


def classify_hierarchical(text: str, taxonomy, classifier) -> Dict:
    """
    Executa classificação hierárquica em 3 etapas.

    Args:
        text: Texto da notícia
        taxonomy: Objeto TaxonomyParser
        classifier: Instância do classificador (LocalClassifier)

    Returns:
        Dict com level1_code, level2_code, level3_code, latency_total, success
    """
    import time

    total_start = time.time()
    result = {
        'level1_code': None,
        'level2_code': None,
        'level3_code': None,
        'latency_l1': 0,
        'latency_l2': 0,
        'latency_l3': 0,
        'latency_total': 0,
        'success': False,
        'error': None
    }

    try:
        # Nível 1
        prompt_l1 = get_prompt_level1(text, taxonomy)
        start = time.time()
        response_l1 = classifier._call_ollama_raw(prompt_l1)
        result['latency_l1'] = time.time() - start

        # Extrair código L1 com parsing robusto
        level1_code = extract_level1_code(response_l1)

        if not level1_code or len(level1_code) != 2:
            result['error'] = f"Falha ao extrair código L1 de: {response_l1[:100]}"
            return result

        result['level1_code'] = level1_code

        # Nível 2
        prompt_l2 = get_prompt_level2(text, taxonomy, level1_code)
        if not prompt_l2:
            result['error'] = "Sem categorias L2 disponíveis"
            return result

        start = time.time()
        response_l2 = classifier._call_ollama_raw(prompt_l2)
        result['latency_l2'] = time.time() - start

        # Extrair código L2 com parsing robusto
        level2_code = extract_level2_code(response_l2, level1_code)

        if not level2_code or '.' not in level2_code:
            result['error'] = f"Falha ao extrair código L2 de: {response_l2[:100]}"
            return result

        result['level2_code'] = level2_code

        # Nível 3
        prompt_l3 = get_prompt_level3(text, taxonomy, level2_code)
        if not prompt_l3:
            result['error'] = "Sem categorias L3 disponíveis"
            return result

        start = time.time()
        response_l3 = classifier._call_ollama_raw(prompt_l3)
        result['latency_l3'] = time.time() - start

        # Extrair código L3 com parsing robusto
        level3_code = extract_level3_code(response_l3, level2_code)

        if not level3_code or level3_code.count('.') != 2:
            result['error'] = f"Falha ao extrair código L3 de: {response_l3[:100]}"
            return result

        result['level3_code'] = level3_code
        result['success'] = True

    except Exception as e:
        result['error'] = str(e)

    finally:
        result['latency_total'] = time.time() - total_start

    return result
