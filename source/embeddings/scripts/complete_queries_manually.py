#!/usr/bin/env python3
"""
Complete remaining queries (q032-q085) by reading documents and creating realistic variants.

Follows the pattern established by user in q001-q031.
"""

import json
from pathlib import Path
import re


# Jargões conhecidos
JARGOES = {
    'ministério', 'secretaria', 'mec', 'sus', 'anvisa', 'enem', 'sisu', 'fies',
    'prouni', 'ipca', 'selic', 'copom', 'bacen', 'dnit', 'antt', 'anac',
    'ibama', 'icmbio', 'embrapa', 'conab', 'pronaf', 'cnpq', 'capes',
    'bolsa família', 'cadastro único', 'bpc', 'mds', 'mdr', 'agu',
    'polícia federal', 'prf', 'seop', 'dnocs', 'incra', 'funai', 'inss'
}


def load_corpus():
    """Load corpus documents."""
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    docs = {}

    for json_file in corpus_dir.glob("doc_*.json"):
        with open(json_file) as f:
            doc = json.load(f)
            docs[doc['id']] = doc

    return docs


def extract_key_terms(content, n=10):
    """Extract key terms from content."""
    # Clean text
    text = content.lower()
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s]', ' ', text)

    # Split and filter
    words = text.split()
    words = [w for w in words if len(w) >= 4]

    # Remove stopwords simples
    stop = {'para', 'que', 'com', 'uma', 'dos', 'das', 'pelo', 'pela',
            'mais', 'sobre', 'como', 'entre', 'quando', 'onde', 'qual',
            'todo', 'toda', 'muito', 'também', 'pode', 'ter', 'sido',
            'seus', 'suas', 'este', 'esta', 'esse', 'essa', 'isso',
            'está', 'são', 'foi', 'ser', 'fazer', 'após', 'durante',
            'cerca', 'através', 'governo', 'brasil', 'federal'}

    words_filtered = [w for w in words if w not in stop]

    # Count frequency
    from collections import Counter
    freq = Counter(words_filtered)

    return [w for w, c in freq.most_common(n)]


def has_jargon(text):
    """Check if text contains government jargon."""
    text_lower = text.lower()
    return any(j in text_lower for j in JARGOES)


def create_variants_for_doc(doc):
    """Create 3 realistic query variants for a document."""
    title = doc['title']
    content = doc['content']
    agency = doc['metadata']['agency']

    # Extract info
    key_terms = extract_key_terms(content, n=15)

    # Simplify title for first variant
    title_clean = title.lower()
    title_clean = re.sub(r'\s+em\s+[A-Z][a-zá-ú]+(/[A-Z]{2})?', '', title_clean)
    title_clean = re.sub(r'\([A-Z]{2}\)', '', title_clean)
    title_clean = re.sub(r'\d{4}(/\d{4})?', '', title_clean)
    title_words = [w for w in title_clean.split() if len(w) > 3 and w not in {'para', 'que', 'com', 'uma', 'dos', 'das'}]

    variants = []

    # Variant 1: From simplified title (2-3 words)
    if title_words:
        v1_text = ' '.join(title_words[:3])
        variants.append({
            "text": v1_text,
            "type": "from_title",
            "has_jargon": has_jargon(v1_text)
        })

    # Variant 2: With agency/jargon (3-4 words)
    agency_terms = [agency] if agency else []
    v2_words = (agency_terms + key_terms[:3])[:4]
    v2_text = ' '.join(v2_words)
    variants.append({
        "text": v2_text,
        "type": "with_jargon",
        "has_jargon": True
    })

    # Variant 3: Natural/contextual (2-4 words)
    # Use most frequent terms from content
    v3_text = ' '.join(key_terms[:3])
    variants.append({
        "text": v3_text,
        "type": "without_jargon",
        "has_jargon": has_jargon(v3_text)
    })

    # Pick best as recommended (prefer from_title if good)
    recommended = variants[0]['text'] if len(variants[0]['text'].split()) <= 4 else variants[2]['text']

    return variants, recommended


def main():
    print("📂 Loading corpus and query template...")

    # Load corpus
    corpus = load_corpus()
    print(f"✅ Loaded {len(corpus)} documents")

    # Load current template
    template_file = Path(__file__).parent.parent / "data" / "query_template_85.json"
    with open(template_file) as f:
        queries = json.load(f)

    print(f"✅ Loaded {len(queries)} queries\n")

    # Process q032-q085
    updated_count = 0

    for i, query in enumerate(queries):
        query_id = query['query_id']
        query_num = int(query_id[1:])

        # Skip q001-q031 (already done by user)
        if query_num <= 31:
            continue

        doc_id = query['anchor_doc_id']

        if doc_id not in corpus:
            print(f"⚠️  {query_id}: Document {doc_id} not found in corpus")
            continue

        doc = corpus[doc_id]

        print(f"📝 {query_id} ({doc_id}): {doc['title'][:60]}...")

        # Create variants
        variants, recommended = create_variants_for_doc(doc)

        # Update query
        query['variants'] = variants
        query['recommended_query'] = recommended

        updated_count += 1

    # Save updated template
    with open(template_file, 'w', encoding='utf-8') as f:
        json.dump(queries, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Updated {updated_count} queries")
    print(f"💾 Saved to: {template_file}")
    print(f"\n📊 Summary:")
    print(f"  User-edited (q001-q031): 31 queries")
    print(f"  Auto-completed (q032-q085): {updated_count} queries")
    print(f"  Total: {31 + updated_count} queries")


if __name__ == "__main__":
    main()
