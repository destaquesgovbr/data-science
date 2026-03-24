#!/usr/bin/env python3
"""
Generate query template with anchor documents and keyword suggestions.

Selects 60 balanced anchor documents (6 per category) and extracts
keywords to help manual query creation.

Usage:
    python generate_query_template.py
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
import re


# Jargões para destacar
JARGOES_BR = [
    'ministério', 'secretaria', 'agência', 'portaria', 'decreto', 'resolução',
    'sus', 'anvisa', 'ubs', 'mec', 'enem', 'sisu', 'fies', 'prouni', 'ideb', 'bncc',
    'pib', 'ipca', 'selic', 'copom', 'bacen', 'cvm', 'bolsa família', 'cadastro único',
    'bpc', 'ibama', 'icmbio', 'embrapa', 'conab', 'paa', 'pronaf', 'dnit', 'antt',
    'anac', 'antaq', 'cnpq', 'capes', 'finep', 'polícia federal', 'seop', 'senasp'
]


def load_corpus():
    """Load curated corpus."""
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"

    categories = defaultdict(list)
    for json_file in sorted(corpus_dir.glob("doc_*.json")):
        with open(json_file) as f:
            doc = json.load(f)
            categories[doc['category']].append(doc)

    return categories


def select_anchor_docs(category_docs):
    """Select 6 anchor docs per category (2 short, 3 medium, 1 long)."""
    by_size = defaultdict(list)

    for doc in category_docs:
        size = doc['metadata']['size_category']
        by_size[size].append(doc)

    # Target: 2 short, 3 medium, 1 long
    selected = []
    selected.extend(by_size.get('Curta', [])[:2])
    selected.extend(by_size.get('Média', [])[:3])
    selected.extend(by_size.get('Longa', [])[:1])

    return selected[:6]  # Ensure exactly 6


def extract_keywords(text, n=15):
    """Extract most relevant keywords from text."""
    # Clean and tokenize
    text_lower = text.lower()

    # Remove URLs, emails, special chars
    text_clean = re.sub(r'http\S+|www\.\S+', '', text_lower)
    text_clean = re.sub(r'\S+@\S+', '', text_clean)
    text_clean = re.sub(r'[^\w\s]', ' ', text_clean)

    # Extract words (minimum 3 chars)
    words = [w for w in text_clean.split() if len(w) >= 3]

    # Remove common stopwords (simplified list)
    stopwords = {
        'para', 'que', 'com', 'uma', 'dos', 'das', 'pelo', 'pela', 'mais',
        'sobre', 'como', 'entre', 'quando', 'onde', 'qual', 'todo', 'toda',
        'muito', 'também', 'pode', 'ter', 'sido', 'seus', 'suas', 'este',
        'esta', 'esse', 'essa', 'isso', 'aqui', 'ali', 'está', 'são', 'foi'
    }
    words_filtered = [w for w in words if w not in stopwords and len(w) > 3]

    # Count frequencies
    word_freq = Counter(words_filtered)

    # Get top keywords
    keywords = [word for word, count in word_freq.most_common(n)]

    return keywords


def extract_jargoes(text):
    """Extract government jargon terms from text."""
    text_lower = text.lower()
    found_jargoes = []

    for jargao in JARGOES_BR:
        if jargao in text_lower:
            found_jargoes.append(jargao)

    return found_jargoes[:10]  # Max 10


def categorize_query_type(doc):
    """Suggest query type based on document characteristics."""
    length = doc['length']
    jargoes = extract_jargoes(doc['content'])

    # Long doc
    if length > 5500 or doc['metadata']['size_category'] == 'Longa':
        return 'doc_longo'

    # Many jargon terms
    if len(jargoes) >= 5:
        return 'jargao_br'

    # Default
    return 'geral'


def generate_template():
    """Generate query creation template."""
    print("📂 Carregando corpus...")
    categories = load_corpus()

    print(f"✅ {len(categories)} categorias carregadas")
    print(f"📊 Total de documentos: {sum(len(docs) for docs in categories.values())}\n")

    print("="*70)
    print("🎯 SELECIONANDO DOCUMENTOS ÂNCORA")
    print("="*70)

    all_anchors = []
    query_counter = 1

    for category, docs in sorted(categories.items()):
        print(f"\n📂 {category}")
        anchors = select_anchor_docs(docs)

        print(f"  Selecionados: {len(anchors)} docs")

        for anchor in anchors:
            # Extract suggestions
            keywords = extract_keywords(anchor['content'], n=10)
            jargoes = extract_jargoes(anchor['content'])
            query_type = categorize_query_type(anchor)

            anchor_info = {
                'query_id': f'q{query_counter:03d}',
                'anchor_doc_id': anchor['id'],
                'category': category,
                'title': anchor['title'],
                'content_preview': anchor['content'][:300] + '...',
                'length': anchor['length'],
                'size_category': anchor['metadata']['size_category'],
                'agency': anchor['metadata']['agency'],
                'suggested_type': query_type,
                'keywords': keywords[:10],
                'jargoes': jargoes,
                'query_text': '',  # TO BE FILLED
            }

            all_anchors.append(anchor_info)
            query_counter += 1

    # Save to JSON
    output_dir = Path(__file__).parent.parent / "data"
    output_file = output_dir / "query_template.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_anchors, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print("📄 TEMPLATE GERADO")
    print(f"{'='*70}")
    print(f"\n✅ Template salvo em: {output_file}")
    print(f"📊 Total de queries âncora: {len(all_anchors)}")

    # Statistics
    by_type = Counter(a['suggested_type'] for a in all_anchors)
    print(f"\n📊 Distribuição por tipo sugerido:")
    print(f"  Geral: {by_type.get('geral', 0)} queries")
    print(f"  Jargão BR: {by_type.get('jargao_br', 0)} queries")
    print(f"  Doc Longo: {by_type.get('doc_longo', 0)} queries")

    # Generate markdown guide
    generate_markdown_guide(all_anchors, output_dir)


def generate_markdown_guide(anchors, output_dir):
    """Generate markdown guide for query creation."""

    md_content = """# Guia para Criação de Queries

## 📋 Instruções

Este documento lista os **60 documentos âncora** selecionados para criação de queries.

Para cada documento, você deve:

1. ✅ **Ler o documento completo** (disponível em `source/embeddings/data/corpus/`)
2. ✅ **Entender o tema principal**
3. ✅ **Escrever uma query** como um usuário real buscaria
4. ✅ **Usar as sugestões** de keywords/jargões (mas não copiar literalmente!)
5. ✅ **Editar o arquivo** `query_template.json` preenchendo o campo `"query_text"`

---

## 🎯 Critérios para Boas Queries

### ✅ Faça:
- Usar 3-6 palavras
- Linguagem natural/coloquial (queries gerais)
- Incluir siglas/jargões (queries técnicas)
- Variar níveis de especificidade

### ❌ Evite:
- Copiar título do documento
- Usar apenas 1 palavra
- Queries muito genéricas (>100 docs relevantes)
- Queries muito específicas (apenas 1 doc relevante)

---

## 📊 Distribuição de Tipos

"""

    by_type = Counter(a['suggested_type'] for a in anchors)
    md_content += f"- **Geral:** {by_type.get('geral', 0)} queries (linguagem natural, sem jargões)\n"
    md_content += f"- **Jargão BR:** {by_type.get('jargao_br', 0)} queries (siglas, termos técnicos)\n"
    md_content += f"- **Doc Longo:** {by_type.get('doc_longo', 0)} queries (complexas, múltiplos conceitos)\n"

    md_content += "\n---\n\n## 📄 Documentos Âncora por Categoria\n\n"

    # Group by category
    by_category = defaultdict(list)
    for anchor in anchors:
        by_category[anchor['category']].append(anchor)

    for category, cat_anchors in sorted(by_category.items()):
        md_content += f"### {category}\n\n"

        for anchor in cat_anchors:
            md_content += f"#### {anchor['query_id']} - {anchor['anchor_doc_id']}\n\n"
            md_content += f"**Título:** {anchor['title']}\n\n"
            md_content += f"**Tipo Sugerido:** `{anchor['suggested_type']}`\n\n"
            md_content += f"**Tamanho:** {anchor['size_category']} ({anchor['length']} chars)\n\n"
            md_content += f"**Órgão:** {anchor['agency']}\n\n"

            if anchor['keywords']:
                md_content += f"**Keywords Sugeridas:** {', '.join(anchor['keywords'][:8])}\n\n"

            if anchor['jargoes']:
                md_content += f"**Jargões Encontrados:** {', '.join(anchor['jargoes'][:5])}\n\n"

            md_content += f"**Preview:**\n> {anchor['content_preview']}\n\n"
            md_content += f"**Query a criar:** _(preencher no JSON)_\n\n"
            md_content += "---\n\n"

    # Add examples
    md_content += """
## 💡 Exemplos de Boas Queries

### Queries Gerais (linguagem natural):
```
✅ "vacinação infantil obrigatória"
✅ "atendimento hospital público fila"
✅ "nota enem para medicina universidade"
✅ "inflação preços supermercado"
```

### Queries com Jargão BR (termos técnicos):
```
✅ "ANVISA registro medicamento genérico"
✅ "SUS atenção básica UBS cobertura"
✅ "ENEM SISU FIES Prouni inscrição"
✅ "IPCA SELIC COPOM taxa juros"
✅ "PRONAF crédito rural agricultura familiar"
```

### Queries para Docs Longos (complexas):
```
✅ "impacto reforma tributária desenvolvimento regional"
✅ "política ambiental desmatamento Amazônia preservação"
✅ "investimento infraestrutura portos aeroportos concessões"
```

---

## 🚀 Próximos Passos

1. **Edite `query_template.json`** e preencha o campo `"query_text"` para cada query
2. **Execute o script de validação** (será criado) para verificar queries
3. **Anote relevâncias** - marcar quais dos 250 docs são relevantes para cada query

---

**Data de Criação:** {datetime.now().strftime('%d/%m/%Y')}
"""

    from datetime import datetime
    md_content = md_content.replace('{datetime.now().strftime(\'%d/%m/%Y\')}',
                                     datetime.now().strftime('%d/%m/%Y'))

    md_file = output_dir / "GUIA_CRIACAO_QUERIES.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"📖 Guia criado em: {md_file}")


if __name__ == "__main__":
    generate_template()
