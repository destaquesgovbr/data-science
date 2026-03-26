#!/usr/bin/env python3
"""
Generate query variants (with/without jargon) for 85 queries.

Creates automatic query suggestions to speed up manual creation.

Usage:
    python generate_query_variants.py
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
import re


# Jargões brasileiros
JARGOES_BR = {
    'ministério', 'secretaria', 'agência', 'portaria', 'decreto', 'resolução',
    'sus', 'anvisa', 'ubs', 'mec', 'enem', 'sisu', 'fies', 'prouni', 'ideb', 'bncc',
    'pib', 'ipca', 'selic', 'copom', 'bacen', 'cvm', 'bolsa família', 'cadastro único',
    'bpc', 'ibama', 'icmbio', 'embrapa', 'conab', 'paa', 'pronaf', 'dnit', 'antt',
    'anac', 'antaq', 'cnpq', 'capes', 'finep', 'polícia federal', 'seop', 'senasp',
    'loa', 'ppa', 'ldo', 'dnocs', 'incra', 'funai', 'inss', 'rdc', 'agu', 'mapa'
}

# Stopwords PT-BR (simplificado)
STOPWORDS = {
    'para', 'que', 'com', 'uma', 'dos', 'das', 'pelo', 'pela', 'mais',
    'sobre', 'como', 'entre', 'quando', 'onde', 'qual', 'todo', 'toda',
    'muito', 'também', 'pode', 'ter', 'sido', 'seus', 'suas', 'este',
    'esta', 'esse', 'essa', 'isso', 'aqui', 'ali', 'está', 'são', 'foi',
    'ser', 'fazer', 'após', 'durante', 'cerca', 'através', 'governo'
}


def load_corpus():
    """Load curated corpus."""
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"

    categories = defaultdict(list)
    for json_file in sorted(corpus_dir.glob("doc_*.json")):
        with open(json_file) as f:
            doc = json.load(f)
            categories[doc['category']].append(doc)

    return categories


def select_anchor_docs(category_docs, n=9):
    """Select n anchor docs per category (balanced by size)."""
    by_size = defaultdict(list)

    for doc in category_docs:
        size = doc['metadata']['size_category']
        by_size[size].append(doc)

    # Target: ~3 short, 4-5 medium, 1-2 long
    selected = []
    selected.extend(by_size.get('Curta', [])[:3])
    selected.extend(by_size.get('Média', [])[:5])
    selected.extend(by_size.get('Longa', [])[:2])

    return selected[:n]


def extract_jargoes(text):
    """Extract jargon terms from text."""
    text_lower = text.lower()
    found = []

    for jargao in sorted(JARGOES_BR, key=len, reverse=True):  # Longest first
        if jargao in text_lower:
            found.append(jargao)

    return found[:8]  # Max 8


def extract_keywords(text, exclude_jargoes=False):
    """Extract important keywords from text."""
    text_lower = text.lower()

    # Clean text
    text_clean = re.sub(r'http\S+|www\.\S+', '', text_lower)
    text_clean = re.sub(r'\S+@\S+', '', text_clean)
    text_clean = re.sub(r'[^\w\s]', ' ', text_clean)

    # Tokenize
    words = [w for w in text_clean.split() if len(w) >= 4]

    # Filter stopwords
    words = [w for w in words if w not in STOPWORDS]

    # Optionally exclude jargoes
    if exclude_jargoes:
        words = [w for w in words if w not in JARGOES_BR]

    # Count and sort
    word_freq = Counter(words)

    return [word for word, count in word_freq.most_common(15)]


def simplify_title(title):
    """Simplify title to query-like format."""
    # Remove location details (CE, SP, etc)
    title_clean = re.sub(r'\s+em\s+[A-Z][a-zá-ú]+(/[A-Z]{2})?', '', title)
    title_clean = re.sub(r'\([A-Z]{2}\)', '', title_clean)

    # Remove dates
    title_clean = re.sub(r'\d{4}(/\d{4})?', '', title_clean)

    # Extract key terms (remove articles, prepositions)
    words = title_clean.lower().split()
    words = [w for w in words if len(w) > 3 and w not in STOPWORDS]

    return ' '.join(words[:6])  # Max 6 words


def generate_query_variants(doc):
    """
    Generate query variants (with and without jargon).

    Query length targets based on research:
    - General queries: 2-3 words (Jansen et al., 2000: avg 2.35 words)
    - Jargon queries: 3-4 words (technical terms need context)
    - Long doc queries: 4-5 words (complex topics)
    """
    title = doc['title']
    content = doc['content']
    length = doc['length']

    # Extract features
    jargoes = extract_jargoes(content)
    keywords_all = extract_keywords(content, exclude_jargoes=False)
    keywords_clean = extract_keywords(content, exclude_jargoes=True)

    variants = []

    # Variant 1: From simplified title (max 3 words)
    title_simple = simplify_title(title)
    if title_simple:
        title_words = title_simple.split()[:3]  # Limit to 3 words
        variants.append({
            'text': ' '.join(title_words),
            'type': 'from_title',
            'has_jargon': any(j in ' '.join(title_words) for j in jargoes)
        })

    # Variant 2: Keywords with jargon (max 4 words for technical queries)
    if jargoes:
        # Mix jargon + keywords (prioritize jargon)
        jargon_query_words = (jargoes[:2] + keywords_all[:2])[:4]
        jargon_query = ' '.join(jargon_query_words)
        variants.append({
            'text': jargon_query,
            'type': 'with_jargon',
            'has_jargon': True
        })

    # Variant 3: Keywords without jargon (max 3 words for general queries)
    clean_query = ' '.join(keywords_clean[:3])
    variants.append({
        'text': clean_query,
        'type': 'without_jargon',
        'has_jargon': False
    })

    # Variant 4: For long docs, add context (max 5 words)
    if length > 5500:
        long_query_words = (keywords_all[:3] + keywords_clean[:2])[:5]
        long_query = ' '.join(long_query_words)
        variants.append({
            'text': long_query,
            'type': 'long_doc',
            'has_jargon': any(j in long_query for j in jargoes)
        })

    return variants


def categorize_query_type(doc, variant):
    """Suggest query type based on doc and variant characteristics."""
    length = doc['length']
    has_jargon = variant['has_jargon']

    # Long doc
    if length > 5500 or doc['metadata']['size_category'] == 'Longa':
        return 'doc_longo'

    # Has jargon
    if has_jargon:
        return 'jargao_br'

    # Default
    return 'geral'


def generate_template():
    """Generate query template with 85 queries."""
    print("📂 Carregando corpus...")
    categories = load_corpus()

    print(f"✅ {len(categories)} categorias carregadas")
    print(f"📊 Total de documentos: {sum(len(docs) for docs in categories.values())}\n")

    print("="*70)
    print("🎯 GERANDO 85 QUERIES COM VARIAÇÕES AUTOMÁTICAS")
    print("="*70)

    all_queries = []
    query_counter = 1

    # Target distribution
    target_counts = {
        'geral': 35,
        'jargao_br': 35,
        'doc_longo': 15
    }
    current_counts = defaultdict(int)

    for category, docs in sorted(categories.items()):
        print(f"\n📂 {category}")

        # Select 8-9 anchor docs per category
        n_docs = 9 if query_counter <= 50 else 8  # 85 total
        anchors = select_anchor_docs(docs, n=n_docs)

        print(f"  Selecionados: {len(anchors)} docs âncora")

        for anchor in anchors:
            # Generate variants
            variants = generate_query_variants(anchor)

            # Determine best variant based on remaining quotas
            best_variant = None
            for variant in variants:
                suggested_type = categorize_query_type(anchor, variant)
                if current_counts[suggested_type] < target_counts[suggested_type]:
                    best_variant = variant
                    best_variant['suggested_type'] = suggested_type
                    break

            # Fallback: use first variant
            if not best_variant:
                best_variant = variants[0]
                best_variant['suggested_type'] = categorize_query_type(anchor, best_variant)

            # Count
            current_counts[best_variant['suggested_type']] += 1

            # Build query entry
            query_entry = {
                'query_id': f'q{query_counter:03d}',
                'anchor_doc_id': anchor['id'],
                'category': category,
                'title': anchor['title'],
                'length': anchor['length'],
                'size_category': anchor['metadata']['size_category'],
                'agency': anchor['metadata']['agency'],
                'suggested_type': best_variant['suggested_type'],
                'variants': [
                    {
                        'text': v['text'],
                        'type': v['type'],
                        'has_jargon': v['has_jargon']
                    }
                    for v in variants
                ],
                'recommended_query': best_variant['text'],
                'query_text': '',  # TO BE FILLED OR USE RECOMMENDED
            }

            all_queries.append(query_entry)
            query_counter += 1

            if query_counter > 85:
                break

        if query_counter > 85:
            break

    # Trim to exactly 85
    all_queries = all_queries[:85]

    # Save
    output_dir = Path(__file__).parent.parent / "data"
    output_file = output_dir / "query_template_85.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_queries, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print("📄 TEMPLATE GERADO")
    print(f"{'='*70}")
    print(f"\n✅ Template salvo em: {output_file}")
    print(f"📊 Total de queries: {len(all_queries)}")

    # Statistics
    final_counts = Counter(q['suggested_type'] for q in all_queries)
    print(f"\n📊 Distribuição por tipo:")
    print(f"  Geral:      {final_counts.get('geral', 0)} queries")
    print(f"  Jargão BR:  {final_counts.get('jargao_br', 0)} queries")
    print(f"  Doc Longo:  {final_counts.get('doc_longo', 0)} queries")

    # Generate guide
    generate_markdown_guide(all_queries, output_dir)


def generate_markdown_guide(queries, output_dir):
    """Generate markdown guide."""
    from datetime import datetime

    md = f"""# Guia para Criação de 85 Queries

**Data:** {datetime.now().strftime('%d/%m/%Y')}

## 📊 Distribuição

**Total: 85 queries**
- 35 queries gerais (linguagem natural, público leigo)
- 35 queries jargão BR (termos técnicos, profissionais)
- 15 queries docs longos (complexas, múltiplos conceitos)

---

## 📏 Tamanho das Queries: Fundamentação

### **Por que queries curtas?**

Baseado em estudos de comportamento de busca e Information Retrieval:

#### **Pesquisas Acadêmicas:**
- **Jansen et al. (2000)**: Análise de 51.473 queries do Excite.com
  - Média: **2.35 palavras por query**
  - Mediana: 2 palavras
  - Ref: *"Real life, real users, and real needs: a study and analysis of user queries on the web"*

- **Spink et al. (2001)**: Estudo com 1 milhão de queries do Excite
  - Média: **2.6 palavras**
  - Distribuição: 1 palavra (20%), 2 palavras (32%), 3 palavras (26%)
  - Ref: *"Searching the Web: The public and their queries"*

- **Estudos recentes (2015-2020)**: Google/Bing
  - Média cresceu para **3-4 palavras** (influência de mobile e busca por voz)
  - Queries técnicas tendem a ser mais longas (3-5 palavras)

#### **Nosso Critério:**

| Tipo de Query | Palavras | Justificativa |
|---------------|----------|---------------|
| **Geral** | 2-3 | Simula usuário leigo/curioso buscando informação geral |
| **Jargão BR** | 3-4 | Profissionais usam siglas + contexto técnico |
| **Doc Longo** | 4-5 | Tópicos complexos exigem múltiplos conceitos |

**Média esperada: ~3 palavras** (alinhado com estudos atuais)

#### **Exemplos:**

```
✅ Queries Gerais (2-3 palavras):
- "vacinação infantil"
- "microcrédito pescadores"
- "nota enem medicina"

✅ Queries Jargão BR (3-4 palavras):
- "PRONAF crédito rural agricultura"
- "ANVISA registro medicamento genérico"
- "SUS atenção básica UBS"

✅ Queries Docs Longos (4-5 palavras):
- "reforma tributária impacto pequenas empresas"
- "política ambiental desmatamento Amazônia preservação"
```

---

## 🎯 Como Usar Este Template

Para cada query, você tem **3 opções**:

### Opção 1: Usar a query recomendada (MAIS RÁPIDO)
```json
"recommended_query": "peixamento açude piscicultura alevinos"
"query_text": "peixamento açude piscicultura alevinos"  ← Copiar
```

### Opção 2: Escolher uma das variantes
```json
"variants": [
  {{"text": "dnocs realiza peixamento açude", "type": "from_title"}},
  {{"text": "dnocs piscicultura alevinos", "type": "with_jargon"}},
  {{"text": "piscicultura município alevinos", "type": "without_jargon"}}
]
"query_text": "piscicultura município alevinos"  ← Escolher variante
```

### Opção 3: Criar sua própria (SE NECESSÁRIO)
```json
"query_text": "sua query customizada aqui"
```

## 💡 Dicas

✅ **Para queries GERAIS:** Prefira variantes `without_jargon`
✅ **Para queries JARGÃO BR:** Prefira variantes `with_jargon`
✅ **Para queries LONGAS:** Use mais palavras, múltiplos conceitos

---

## 📄 Queries por Categoria

"""

    by_cat = defaultdict(list)
    for q in queries:
        by_cat[q['category']].append(q)

    for cat, cat_queries in sorted(by_cat.items()):
        md += f"### {cat} ({len(cat_queries)} queries)\n\n"

        for q in cat_queries:
            md += f"#### {q['query_id']} - {q['suggested_type']}\n\n"
            md += f"**Doc:** {q['anchor_doc_id']} - {q['title'][:80]}...\n\n"
            md += f"**Recomendada:** `{q['recommended_query']}`\n\n"

            md += "**Variantes:**\n"
            for v in q['variants']:
                jargon_icon = "🔧" if v['has_jargon'] else "💬"
                md += f"- {jargon_icon} `{v['text']}` ({v['type']})\n"

            md += "\n---\n\n"

    # Add references section
    md += """
---

## 📚 Referências

### Estudos sobre Tamanho de Queries

1. **Jansen, B. J., Spink, A., & Saracevic, T. (2000)**
   *"Real life, real users, and real needs: a study and analysis of user queries on the web"*
   Information Processing & Management, 36(2), 207-227.
   **Principais achados:** Média de 2.35 palavras por query em 51.473 queries analisadas.

2. **Spink, A., Wolfram, D., Jansen, M. B., & Saracevic, T. (2001)**
   *"Searching the Web: The public and their queries"*
   Journal of the American Society for Information Science and Technology, 52(3), 226-234.
   **Principais achados:** Média de 2.6 palavras; distribuição: 1 palavra (20%), 2 palavras (32%), 3 palavras (26%).

3. **Google Search Research (2015-2020)**
   Tendências atuais mostram aumento para 3-4 palavras em média, impulsionado por:
   - Busca móvel (queries mais conversacionais)
   - Busca por voz (frases mais naturais)
   - Maior familiaridade com motores de busca

### Justificativa do Design

Nosso design de queries reflete **dois perfis de usuários reais**:

1. **Público Geral (~40%)**: Queries curtas (2-3 palavras), linguagem natural
   - Ex: cidadãos buscando informações sobre serviços públicos

2. **Profissionais/Especialistas (~40%)**: Queries técnicas (3-4 palavras), com jargões
   - Ex: servidores públicos, jornalistas, gestores buscando informações específicas

3. **Pesquisas Complexas (~20%)**: Queries longas (4-5 palavras), múltiplos conceitos
   - Ex: pesquisadores, analistas buscando contexto detalhado

Esta distribuição permite avaliar a capacidade dos embeddings em **ambos os cenários de uso real**.

---

**Gerado por:** `generate_query_variants.py`
**Projeto:** Estudo Comparativo de Embeddings - Issue #1
**Repositório:** [data-science/embeddings](../../)
"""

    md_file = output_dir / "GUIA_CRIACAO_QUERIES_85.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f"📖 Guia criado em: {md_file}")


if __name__ == "__main__":
    generate_template()
