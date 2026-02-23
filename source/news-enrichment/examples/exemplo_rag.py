"""
Exemplo de Uso: Classificador com RAG

Este exemplo demonstra o uso do classificador com Retrieval-Augmented Generation.

IMPORTANTE: Requer instalação das dependências RAG:
    poetry install --extras rag

O que este exemplo faz:
1. Inicializa classificador com RAG
2. Para cada notícia, busca top-50 categorias mais relevantes via embeddings
3. Classifica usando apenas essas categorias filtradas
4. Compara com abordagem direta

Nota: Este é um exemplo educacional. Na prática, a abordagem direta
(sem RAG) é superior para taxonomias de tamanho moderado (< 1000 categorias).
"""

from pathlib import Path
import time

# Configuração de paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ARVORE_PATH = PROJECT_ROOT / "arvore.yaml"

# Imports
try:
    from news_enrichment import NewsClassifierRAG, NewsClassifier
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Erro ao importar: {e}")
    print("\nDependências RAG não instaladas.")
    print("Instale com: poetry install --extras rag")
    exit(1)


def exemplo_basico():
    """Exemplo básico de classificação com RAG."""
    print("=" * 80)
    print("EXEMPLO: Classificação com RAG")
    print("=" * 80)
    print()

    # Notícias de exemplo
    noticias = [
        {
            'unique_id': 'exemplo-001',
            'title': 'Governo anuncia reforma tributária para simplificar impostos',
            'content': (
                'O Ministério da Fazenda apresentou hoje uma proposta de reforma '
                'tributária que visa simplificar o sistema de impostos brasileiro, '
                'unificando tributos federais, estaduais e municipais.'
            )
        },
        {
            'unique_id': 'exemplo-002',
            'title': 'Ministério da Saúde lança campanha de vacinação',
            'content': (
                'O Ministério da Saúde iniciou hoje uma campanha nacional de '
                'vacinação contra a dengue, com foco em crianças e adolescentes. '
                'A meta é vacinar 10 milhões de pessoas até dezembro.'
            )
        },
        {
            'unique_id': 'exemplo-003',
            'title': 'MEC anuncia investimento em educação profissional',
            'content': (
                'O Ministério da Educação anunciou R$ 500 milhões para expansão '
                'de cursos técnicos e profissionalizantes. O foco é capacitar '
                'jovens para o mercado de trabalho.'
            )
        }
    ]

    print(f"Notícias para classificar: {len(noticias)}\n")

    # Inicializar classificador RAG
    print("Inicializando classificador RAG...")
    print("(Carregando modelo BERT português - pode demorar ~30s)")
    start = time.time()

    classifier_rag = NewsClassifierRAG(
        taxonomy_path=str(ARVORE_PATH),
        top_k=30,  # Busca top-30 categorias mais relevantes
        verbose=True
    )

    init_time = time.time() - start
    print(f"✓ Inicializado em {init_time:.1f}s\n")

    # Classificar cada notícia
    print("=" * 80)
    print("CLASSIFICANDO COM RAG")
    print("=" * 80)
    print()

    for i, noticia in enumerate(noticias, 1):
        print(f"\n{i}. {noticia['title']}")
        print("-" * 80)

        start = time.time()
        result = classifier_rag.classify_single(
            noticia,
            return_format="dict",
            include_rag_metadata=True
        )
        elapsed = time.time() - start

        print(f"Categoria: {result.get('most_specific_theme_label', 'N/A')}")
        print(f"Nível 1: {result.get('theme_1_level_1_label', 'N/A')}")
        print(f"Nível 2: {result.get('theme_1_level_2_label', 'N/A')}")
        print(f"Tempo: {elapsed:.2f}s")

        if 'rag_metadata' in result:
            print(f"\nTop-3 categorias recuperadas pelo RAG:")
            for cat in result['rag_metadata']['top_5_similarities'][:3]:
                print(f"  [{cat['score']:.3f}] {cat['category']}")

    print("\n" + "=" * 80)
    print("✓ Exemplo concluído!")
    print("=" * 80)


def comparacao_rag_vs_direto():
    """Compara RAG vs abordagem direta em uma notícia."""
    print("\n" + "=" * 80)
    print("COMPARAÇÃO: RAG vs DIRETO")
    print("=" * 80)
    print()

    noticia = {
        'unique_id': 'comp-001',
        'title': 'Governo lança programa de microcrédito para empreendedores',
        'content': (
            'O governo federal anunciou um novo programa de microcrédito '
            'destinado a pequenos empreendedores. A iniciativa prevê '
            'empréstimos de até R$ 20 mil com juros subsidiados.'
        )
    }

    print(f"Notícia:")
    print(f"  {noticia['title']}\n")

    # 1. Classificar com RAG
    print("1. Classificando com RAG...")
    print("   (Usa embeddings para filtrar 30 categorias)")
    start_rag = time.time()

    classifier_rag = NewsClassifierRAG(
        taxonomy_path=str(ARVORE_PATH),
        top_k=30,
        verbose=False
    )
    result_rag = classifier_rag.classify_single(noticia, return_format="dict")
    time_rag = time.time() - start_rag

    print(f"   ✓ Categoria: {result_rag.get('most_specific_theme_label', 'N/A')}")
    print(f"   ✓ Tempo: {time_rag:.2f}s")

    # 2. Classificar direto
    print("\n2. Classificando direto...")
    print("   (Passa todas 410 categorias)")
    start_direct = time.time()

    classifier_direct = NewsClassifier(verbose=False)
    result_direct = classifier_direct.classify_single(noticia, return_format="dict")
    time_direct = time.time() - start_direct

    print(f"   ✓ Categoria: {result_direct.get('most_specific_theme_label', 'N/A')}")
    print(f"   ✓ Tempo: {time_direct:.2f}s")

    # Comparação
    print("\n" + "-" * 80)
    print("COMPARAÇÃO:")
    print("-" * 80)

    concordance = result_rag.get('most_specific_theme_label') == result_direct.get('most_specific_theme_label')
    print(f"Concordância: {'✓ SIM' if concordance else '✗ NÃO'}")

    if time_rag > time_direct:
        diff = ((time_rag / time_direct) - 1) * 100
        print(f"Performance: RAG é {diff:.1f}% mais lento")
    else:
        diff = ((time_direct / time_rag) - 1) * 100
        print(f"Performance: RAG é {diff:.1f}% mais rápido")

    print("\nCategorias escolhidas:")
    print(f"  RAG:    {result_rag.get('most_specific_theme_label', 'N/A')}")
    print(f"  Direto: {result_direct.get('most_specific_theme_label', 'N/A')}")

    if not concordance:
        print("\n⚠️  As abordagens discordaram!")
        print("    Isso pode acontecer quando o RAG filtra a categoria correta.")

    print()


def main():
    """Função principal."""
    print("\n" + "=" * 80)
    print("EXEMPLOS: Classificação com RAG")
    print("=" * 80)
    print()
    print("Este script demonstra o uso do classificador com RAG.")
    print()
    print("O que é RAG?")
    print("  • Retrieval-Augmented Generation")
    print("  • Usa embeddings para filtrar categorias relevantes")
    print("  • Reduz tamanho do contexto enviado ao LLM")
    print()
    print("Quando usar RAG?")
    print("  • Taxonomias com milhares de categorias (> 5.000)")
    print("  • LLMs com contexto limitado")
    print("  • Necessidade de explicabilidade via similaridade")
    print()
    print("Para nosso caso (410 categorias):")
    print("  • RAG adiciona complexidade desnecessária")
    print("  • Abordagem direta é mais simples e eficaz")
    print("  • Veja: ../RAG_COMPARISON.md")
    print()

    # Menu
    print("Escolha um exemplo:")
    print("  1. Exemplo básico (3 notícias)")
    print("  2. Comparação RAG vs Direto")
    print("  3. Ambos")
    print()

    choice = input("Opção (1/2/3): ").strip()

    if choice == "1":
        exemplo_basico()
    elif choice == "2":
        comparacao_rag_vs_direto()
    elif choice == "3":
        exemplo_basico()
        comparacao_rag_vs_direto()
    else:
        print("Opção inválida. Rodando exemplo básico...")
        exemplo_basico()


if __name__ == "__main__":
    main()
