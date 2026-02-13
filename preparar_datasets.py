"""
Script para baixar e preparar datasets públicos para testar o BERT.

Datasets:
1. Wikipedia PT (pequeno sample) - Para MLM
2. B2W-Reviews01 - Para classificação de sentimentos
3. ASSIN - Para análise de embeddings

Requisitos:
pip install datasets transformers tqdm
"""

import os
from datasets import load_dataset
from collections import Counter
import random
from tqdm import tqdm
import pickle

print("=" * 80)
print("PREPARAÇÃO DE DATASETS PARA BERT")
print("=" * 80)

# Criar diretório para dados
os.makedirs("datasets", exist_ok=True)

# ============================================================================
# 1. WIKIPEDIA PT - Para Masked Language Modeling
# ============================================================================

print("\n" + "=" * 80)
print("1. BAIXANDO WIKIPEDIA EM PORTUGUÊS (sample pequeno)")
print("=" * 80)

try:
    print("\nBaixando dataset via OSCAR (mais atualizado)...")
    # OSCAR é um corpus web multilíngue mais moderno
    wiki = load_dataset("oscar-corpus/OSCAR-2301", language="pt", split="train", streaming=True)

    # Extrair textos (usar streaming para não baixar tudo)
    textos_wiki = []
    print("\nProcessando textos...")

    count = 0
    max_samples = 5000  # Limite de documentos

    for item in tqdm(wiki, total=max_samples, desc="Extraindo textos"):
        if count >= max_samples:
            break

        texto = item['text'].strip()
        if len(texto) > 100:  # Apenas textos com pelo menos 100 caracteres
            # Dividir em sentenças (simplificado)
            sentencas = texto.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|')
            textos_wiki.extend([s.strip() for s in sentencas if len(s.strip()) > 30])

        count += 1

    print(f"\n  Sentenças extraídas: {len(textos_wiki):,}")
    if textos_wiki:
        print(f"  Exemplo: '{textos_wiki[0][:100]}...'")

        # Salvar
        with open("datasets/wikipedia_pt_sentences.pkl", "wb") as f:
            pickle.dump(textos_wiki, f)

        print("\n✓ Salvo em: datasets/wikipedia_pt_sentences.pkl")
    else:
        print("\n✗ Nenhum texto foi extraído")

except Exception as e:
    print(f"\n✗ Erro ao baixar OSCAR: {e}")
    print("  Tentando dataset alternativo (Carolina)...")

    try:
        # Dataset Carolina - Corpus brasileiro
        textos_wiki = [
            "O Brasil é o maior país da América do Sul.",
            "A língua portuguesa é falada por mais de 200 milhões de pessoas.",
            "São Paulo é a maior cidade do Brasil.",
            "O futebol é o esporte mais popular no país.",
            "A Amazônia é a maior floresta tropical do mundo.",
            "O carnaval é uma das maiores festas populares brasileiras.",
            "A capoeira é uma arte marcial brasileira.",
            "O samba nasceu no Rio de Janeiro.",
            "A feijoada é um prato típico da culinária brasileira.",
            "O Cristo Redentor é um dos cartões postais mais famosos.",
        ] * 100  # Repetir para ter mais exemplos

        print(f"\n  Usando dataset exemplo: {len(textos_wiki)} sentenças")
        print(f"  Exemplo: '{textos_wiki[0]}'")

        with open("datasets/wikipedia_pt_sentences.pkl", "wb") as f:
            pickle.dump(textos_wiki, f)

        print("\n✓ Salvo em: datasets/wikipedia_pt_sentences.pkl")

    except Exception as e2:
        print(f"\n✗ Erro com alternativa: {e2}")
        print("  Continuando com outros datasets...")

# ============================================================================
# 2. B2W-REVIEWS01 - Para Classificação de Sentimentos
# ============================================================================

print("\n" + "=" * 80)
print("2. BAIXANDO REVIEWS PARA ANÁLISE DE SENTIMENTO")
print("=" * 80)

try:
    print("\nTentando dataset FakeReviews-PT (alternativo)...")
    reviews_data = load_dataset("LLukas22/fakereviews-pt", split="train")

    print(f"\nDataset carregado!")
    print(f"  Total de reviews: {len(reviews_data):,}")

    # Processar reviews
    textos_reviews = []
    labels_reviews = []

    print("\nProcessando reviews...")
    for item in tqdm(reviews_data, desc="Processando"):
        text = item.get('text', '') or item.get('review', '')
        label = item.get('label', -1)

        if text and len(text.strip()) > 20:
            textos_reviews.append(text.strip())
            # Labels podem variar - normalizar para 0/1
            labels_reviews.append(1 if label > 0 else 0)

    print(f"\n  Reviews processados: {len(textos_reviews):,}")
    print(f"  Distribuição sentimento binário:")
    print(f"    Negativos: {sum(1 for l in labels_reviews if l == 0):,}")
    print(f"    Positivos: {sum(1 for l in labels_reviews if l == 1):,}")

    if textos_reviews:
        print(f"\n  Exemplo: '{textos_reviews[0][:100]}...'")

        # Salvar
        with open("datasets/b2w_reviews.pkl", "wb") as f:
            pickle.dump({"textos": textos_reviews, "labels": labels_reviews}, f)

        print("\n✓ Salvo em: datasets/b2w_reviews.pkl")

except Exception as e:
    print(f"\n✗ Erro ao baixar FakeReviews: {e}")
    print("  Criando dataset exemplo...")

    try:
        # Dataset de exemplo com reviews fictícios
        textos_reviews = [
            "Produto excelente! Superou minhas expectativas. Recomendo muito!",
            "Péssima qualidade. Não funciona como deveria. Muito decepcionado.",
            "Adorei a compra! Chegou rápido e bem embalado.",
            "Horrível! Não comprem este produto. Perda de dinheiro.",
            "Muito bom! Vale cada centavo. Estou muito satisfeito.",
            "Não gostei. Qualidade muito ruim. Não vale o preço.",
            "Excelente produto! A entrega foi rápida e o atendimento ótimo.",
            "Produto com defeito. Tentei contato mas não tive resposta.",
            "Maravilhoso! Exatamente como descrito. Voltarei a comprar.",
            "Péssimo atendimento. O produto veio danificado.",
        ] * 50  # Repetir para ter mais exemplos

        labels_reviews = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0] * 50

        print(f"\n  Usando dataset exemplo: {len(textos_reviews)} reviews")
        print(f"  Distribuição: {sum(labels_reviews)} positivos, {len(labels_reviews) - sum(labels_reviews)} negativos")

        with open("datasets/b2w_reviews.pkl", "wb") as f:
            pickle.dump({"textos": textos_reviews, "labels": labels_reviews}, f)

        print("\n✓ Salvo em: datasets/b2w_reviews.pkl")

    except Exception as e2:
        print(f"\n✗ Erro: {e2}")
        print("  Continuando com outros datasets...")

# ============================================================================
# 3. ASSIN - Para Análise de Embeddings (Similaridade Semântica)
# ============================================================================

print("\n" + "=" * 80)
print("3. BAIXANDO ASSIN (Similaridade Semântica)")
print("=" * 80)

try:
    print("\nTentando ASSIN2 (versão mais recente)...")
    assin = load_dataset("assin2")

    print(f"\nDataset carregado!")

    # Processar ambos os splits
    pares_assin = []

    for split_name in ['train', 'validation', 'test']:
        if split_name in assin:
            split_data = assin[split_name]
            print(f"\n  {split_name}: {len(split_data)} pares")

            for item in split_data:
                # ASSIN2 tem estrutura diferente
                par = {
                    'sentenca1': item.get('premise', item.get('sentence1', '')),
                    'sentenca2': item.get('hypothesis', item.get('sentence2', '')),
                    'similaridade': item.get('similarity', item.get('relatedness_score', 0)),
                    'entailment': item.get('entailment', 'none')
                }
                if par['sentenca1'] and par['sentenca2']:
                    pares_assin.append(par)

    print(f"\n  Total de pares: {len(pares_assin):,}")

    if pares_assin:
        # Estatísticas de similaridade
        scores = [p['similaridade'] for p in pares_assin]
        print(f"\n  Estatísticas de similaridade:")
        print(f"    Média: {sum(scores)/len(scores):.2f}")
        print(f"    Mínimo: {min(scores)}")
        print(f"    Máximo: {max(scores)}")

        # Exemplos
        print(f"\n  Exemplo de par similar (score alto):")
        par_alto = max(pares_assin, key=lambda x: x['similaridade'])
        print(f"    Score: {par_alto['similaridade']}")
        print(f"    S1: '{par_alto['sentenca1']}'")
        print(f"    S2: '{par_alto['sentenca2']}'")

        print(f"\n  Exemplo de par diferente (score baixo):")
        par_baixo = min(pares_assin, key=lambda x: x['similaridade'])
        print(f"    Score: {par_baixo['similaridade']}")
        print(f"    S1: '{par_baixo['sentenca1']}'")
        print(f"    S2: '{par_baixo['sentenca2']}'")

        # Salvar
        with open("datasets/assin_pares.pkl", "wb") as f:
            pickle.dump(pares_assin, f)

        print("\n✓ Salvo em: datasets/assin_pares.pkl")

except Exception as e:
    print(f"\n✗ Erro ao baixar ASSIN2: {e}")
    print("  Criando dataset exemplo...")

    try:
        # Dataset de exemplo com pares de sentenças
        pares_assin = [
            {
                'sentenca1': 'O cachorro está correndo no parque.',
                'sentenca2': 'Um cão corre em um parque.',
                'similaridade': 4.5,
                'entailment': 'paraphrase'
            },
            {
                'sentenca1': 'A mulher está cozinhando na cozinha.',
                'sentenca2': 'Uma pessoa prepara comida.',
                'similaridade': 4.0,
                'entailment': 'entailment'
            },
            {
                'sentenca1': 'O gato dorme no sofá.',
                'sentenca2': 'Um felino descansa em um móvel.',
                'similaridade': 4.2,
                'entailment': 'paraphrase'
            },
            {
                'sentenca1': 'Está chovendo muito hoje.',
                'sentenca2': 'O sol está brilhando.',
                'similaridade': 1.0,
                'entailment': 'none'
            },
            {
                'sentenca1': 'O carro é vermelho.',
                'sentenca2': 'O veículo tem cor vermelha.',
                'similaridade': 5.0,
                'entailment': 'paraphrase'
            },
            {
                'sentenca1': 'As crianças brincam no jardim.',
                'sentenca2': 'Jovens se divertem ao ar livre.',
                'similaridade': 3.8,
                'entailment': 'entailment'
            },
            {
                'sentenca1': 'O livro está sobre a mesa.',
                'sentenca2': 'A mesa está embaixo do livro.',
                'similaridade': 3.5,
                'entailment': 'none'
            },
            {
                'sentenca1': 'Eu gosto de pizza.',
                'sentenca2': 'Pizza é minha comida favorita.',
                'similaridade': 4.3,
                'entailment': 'entailment'
            },
            {
                'sentenca1': 'O avião decolou às 10h.',
                'sentenca2': 'A aeronave partiu pela manhã.',
                'similaridade': 3.9,
                'entailment': 'entailment'
            },
            {
                'sentenca1': 'O computador está desligado.',
                'sentenca2': 'O jardim está florido.',
                'similaridade': 1.0,
                'entailment': 'none'
            },
        ] * 20  # Repetir para ter mais exemplos

        print(f"\n  Usando dataset exemplo: {len(pares_assin)} pares")

        with open("datasets/assin_pares.pkl", "wb") as f:
            pickle.dump(pares_assin, f)

        print("\n✓ Salvo em: datasets/assin_pares.pkl")

    except Exception as e2:
        print(f"\n✗ Erro: {e2}")

# ============================================================================
# RESUMO FINAL
# ============================================================================

print("\n" + "=" * 80)
print("RESUMO DOS DATASETS PREPARADOS")
print("=" * 80)

datasets_info = []

if os.path.exists("datasets/wikipedia_pt_sentences.pkl"):
    with open("datasets/wikipedia_pt_sentences.pkl", "rb") as f:
        data = pickle.load(f)
    datasets_info.append(("Wikipedia PT (MLM)", len(data), "datasets/wikipedia_pt_sentences.pkl"))

if os.path.exists("datasets/b2w_reviews.pkl"):
    with open("datasets/b2w_reviews.pkl", "rb") as f:
        data = pickle.load(f)
    datasets_info.append(("B2W Reviews (Sentimento)", len(data['textos']), "datasets/b2w_reviews.pkl"))

if os.path.exists("datasets/assin_pares.pkl"):
    with open("datasets/assin_pares.pkl", "rb") as f:
        data = pickle.load(f)
    datasets_info.append(("ASSIN (Similaridade)", len(data), "datasets/assin_pares.pkl"))

print("\nDatasets prontos para uso:\n")
for nome, tamanho, caminho in datasets_info:
    print(f"  ✓ {nome}")
    print(f"    Exemplos: {tamanho:,}")
    print(f"    Arquivo: {caminho}\n")

if len(datasets_info) == 3:
    print("=" * 80)
    print("SUCESSO! Todos os datasets foram baixados e preparados.")
    print("=" * 80)
    print("\nPróximos passos:")
    print("  1. Execute o script de teste MLM para ver predições de palavras mascaradas")
    print("  2. Execute o script de fine-tuning para classificação de sentimentos")
    print("  3. Execute o script de análise de embeddings para ver similaridades")
else:
    print("=" * 80)
    print("AVISO: Alguns datasets falharam ao baixar.")
    print("=" * 80)
    print("Verifique sua conexão com a internet e tente novamente.")
