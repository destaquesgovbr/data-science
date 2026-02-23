"""
Benchmark para Curadoria Humana

Pega 50 notícias aleatórias do dataset, classifica com 3 abordagens e salva
em formato Excel/CSV para revisão manual.

Saída:
- Excel com colunas lado-a-lado para comparação visual fácil
- Inclui título, conteúdo (resumido), e categoria de cada abordagem
- Campo "observacoes" vazio para curador preencher

Uso:
    poetry run python source/news-enrichment/benchmarks/benchmark_curadoria.py
"""

import time
import random
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import polars as pl
import sys

# Configuração de paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "source" / "news-enrichment"))

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"

# Imports
from news_enrichment import NewsClassifier

# RAG (opcional)
try:
    from news_enrichment.classifier_rag import NewsClassifierRAG
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("⚠️  RAG não disponível. Instale com: poetry install --extras rag")

# BERT (opcional)
try:
    from news_enrichment.classifier_bert import NewsClassifierBERT
    BERT_AVAILABLE = True
except ImportError:
    BERT_AVAILABLE = False
    print("⚠️  BERT não disponível. Instale com: poetry install --extras ml")


def load_random_news(n: int = 50, seed: Optional[int] = None) -> List[Dict]:
    """Carrega n notícias aleatórias do dataset."""
    print("\n" + "="*80)
    print("CARREGANDO NOTÍCIAS ALEATÓRIAS")
    print("="*80 + "\n")

    dataset_path = DATA_DIR / "govbrnews_full.parquet"

    if not dataset_path.exists():
        print(f"✗ Dataset não encontrado: {dataset_path}")
        print("\nProcurando alternativas...")

        # Tentar outros arquivos
        alternatives = [
            DATA_DIR / "sample_enriched.parquet",
            DATA_DIR / "sample_enriched_otimizado_500.parquet",
        ]

        for alt in alternatives:
            if alt.exists():
                dataset_path = alt
                print(f"✓ Usando: {alt.name}")
                break
        else:
            raise FileNotFoundError("Nenhum dataset de notícias encontrado")

    print(f"Carregando dataset: {dataset_path.name}")
    df = pl.read_parquet(dataset_path)

    # Filtrar notícias válidas
    df = df.filter(
        (pl.col('title').is_not_null()) &
        (pl.col('content').is_not_null()) &
        (pl.col('content').str.lengths() > 100)
    )

    print(f"✓ {len(df):,} notícias válidas no dataset")

    # Selecionar aleatoriamente
    if seed is not None:
        random.seed(seed)

    total = len(df)
    if total < n:
        print(f"⚠️  Dataset tem apenas {total} notícias (pedido: {n})")
        n = total

    # Pegar índices aleatórios
    random_indices = random.sample(range(total), n)
    df = df[random_indices]

    print(f"✓ {n} notícias selecionadas aleatoriamente\n")

    news_list = []
    for row in df.iter_rows(named=True):
        news_list.append({
            'unique_id': row.get('unique_id', f'news_{random.randint(1000, 9999)}'),
            'title': row['title'],
            'content': row['content']
        })

    return news_list


def classify_with_claude(news_list: List[Dict]) -> List[Dict]:
    """Classifica notícias com Claude."""
    print("\n" + "="*80)
    print("1/3 CLASSIFICANDO COM CLAUDE")
    print("="*80 + "\n")

    start_init = time.time()
    classifier = NewsClassifier(verbose=False)
    init_time = time.time() - start_init

    print(f"✓ Inicializado em {init_time:.2f}s\n")
    print(f"Classificando {len(news_list)} notícias...\n")

    results = []
    start = time.time()

    for i, news in enumerate(news_list, 1):
        try:
            result = classifier.classify_single(news, return_format="dict")
            results.append({
                'unique_id': news['unique_id'],
                'categoria': result.get('most_specific_theme_label', 'N/A'),
                'nivel_1': result.get('theme_1_level_1_label', 'N/A'),
                'nivel_2': result.get('theme_1_level_2_label', 'N/A'),
                'success': True
            })
            print(f"  [{i:2d}/{len(news_list)}] ✓ {news['title'][:60]}...")
        except Exception as e:
            results.append({
                'unique_id': news['unique_id'],
                'categoria': f'ERRO: {str(e)[:50]}',
                'nivel_1': '',
                'nivel_2': '',
                'success': False
            })
            print(f"  [{i:2d}/{len(news_list)}] ✗ Erro: {e}")

    elapsed = time.time() - start
    print(f"\n✓ Claude: {elapsed:.1f}s total ({elapsed/len(news_list):.2f}s/notícia)")

    return results


def classify_with_rag(news_list: List[Dict], top_k: int = 50) -> Optional[List[Dict]]:
    """Classifica notícias com RAG."""
    if not RAG_AVAILABLE:
        print("\n⚠️  RAG não disponível - pulando")
        return None

    print("\n" + "="*80)
    print("2/3 CLASSIFICANDO COM RAG")
    print("="*80 + "\n")

    arvore_path = PROJECT_ROOT / "arvore.yaml"

    start_init = time.time()
    classifier = NewsClassifierRAG(
        taxonomy_path=str(arvore_path),
        top_k=top_k,
        verbose=False
    )
    init_time = time.time() - start_init

    print(f"✓ Inicializado em {init_time:.2f}s (BERT embeddings)\n")
    print(f"Classificando {len(news_list)} notícias...\n")

    results = []
    start = time.time()

    for i, news in enumerate(news_list, 1):
        try:
            result = classifier.classify_single(news, return_format="dict")
            results.append({
                'unique_id': news['unique_id'],
                'categoria': result.get('most_specific_theme_label', 'N/A'),
                'nivel_1': result.get('theme_1_level_1_label', 'N/A'),
                'nivel_2': result.get('theme_1_level_2_label', 'N/A'),
                'success': True
            })
            print(f"  [{i:2d}/{len(news_list)}] ✓ {news['title'][:60]}...")
        except Exception as e:
            results.append({
                'unique_id': news['unique_id'],
                'categoria': f'ERRO: {str(e)[:50]}',
                'nivel_1': '',
                'nivel_2': '',
                'success': False
            })
            print(f"  [{i:2d}/{len(news_list)}] ✗ Erro: {e}")

    elapsed = time.time() - start
    print(f"\n✓ RAG: {elapsed:.1f}s total ({elapsed/len(news_list):.2f}s/notícia)")

    return results


def classify_with_bert(news_list: List[Dict]) -> Optional[List[Dict]]:
    """Classifica notícias com BERT."""
    if not BERT_AVAILABLE:
        print("\n⚠️  BERT não disponível - pulando")
        return None

    print("\n" + "="*80)
    print("3/3 CLASSIFICANDO COM BERT")
    print("="*80 + "\n")

    model_path = MODELS_DIR / "bert_news_classifier"

    if not model_path.exists():
        print(f"⚠️  Modelo BERT não encontrado: {model_path}")
        print("   Execute train_bert_classifier.py primeiro")
        return None

    start_init = time.time()
    try:
        classifier = NewsClassifierBERT(
            model_path=str(model_path),
            verbose=False
        )
        init_time = time.time() - start_init
    except Exception as e:
        print(f"✗ Erro ao carregar BERT: {e}")
        return None

    print(f"✓ Inicializado em {init_time:.2f}s\n")
    print(f"Classificando {len(news_list)} notícias...\n")

    results = []
    start = time.time()

    for i, news in enumerate(news_list, 1):
        try:
            result = classifier.classify_single(news, return_format="dict")
            results.append({
                'unique_id': news['unique_id'],
                'categoria': result.get('most_specific_theme_label', 'N/A'),
                'nivel_1': result.get('theme_1_level_1_label', 'N/A'),
                'nivel_2': result.get('theme_1_level_2_label', 'N/A'),
                'success': True
            })
            print(f"  [{i:2d}/{len(news_list)}] ✓ {news['title'][:60]}...")
        except Exception as e:
            results.append({
                'unique_id': news['unique_id'],
                'categoria': f'ERRO: {str(e)[:50]}',
                'nivel_1': '',
                'nivel_2': '',
                'success': False
            })
            print(f"  [{i:2d}/{len(news_list)}] ✗ Erro: {e}")

    elapsed = time.time() - start
    print(f"\n✓ BERT: {elapsed:.1f}s total ({elapsed/len(news_list):.2f}s/notícia)")

    return results


def create_curation_dataframe(
    news_list: List[Dict],
    claude_results: List[Dict],
    rag_results: Optional[List[Dict]],
    bert_results: Optional[List[Dict]]
) -> pl.DataFrame:
    """Cria DataFrame para curadoria humana."""
    print("\n" + "="*80)
    print("PREPARANDO PLANILHA PARA CURADORIA")
    print("="*80 + "\n")

    rows = []

    for i, news in enumerate(news_list):
        unique_id = news['unique_id']

        # Buscar resultados
        claude = next((r for r in claude_results if r['unique_id'] == unique_id), {})
        rag = next((r for r in rag_results if r['unique_id'] == unique_id), {}) if rag_results else {}
        bert = next((r for r in bert_results if r['unique_id'] == unique_id), {}) if bert_results else {}

        # Categorias
        cat_claude = claude.get('categoria', 'N/A')
        cat_rag = rag.get('categoria', 'N/A') if rag_results else 'N/A'
        cat_bert = bert.get('categoria', 'N/A') if bert_results else 'N/A'

        # Verificar concordância
        categories = [cat_claude]
        if rag_results and cat_rag != 'N/A':
            categories.append(cat_rag)
        if bert_results and cat_bert != 'N/A':
            categories.append(cat_bert)

        if len(set(categories)) == 1:
            concordancia = "✓ Todas concordam"
        elif len(set(categories)) == 2:
            concordancia = "⚠ Discordância parcial"
        else:
            concordancia = "✗ Todas diferentes"

        # Resumir conteúdo (máx 200 chars)
        content_preview = news['content'][:200].replace('\n', ' ') + "..."

        row = {
            'unique_id': unique_id,
            'titulo': news['title'],
            'conteudo_preview': content_preview,
            'claude_categoria': cat_claude,
            'claude_nivel_1': claude.get('nivel_1', ''),
            'claude_nivel_2': claude.get('nivel_2', ''),
            'rag_categoria': cat_rag if rag_results else '',
            'rag_nivel_1': rag.get('nivel_1', '') if rag_results else '',
            'rag_nivel_2': rag.get('nivel_2', '') if rag_results else '',
            'bert_categoria': cat_bert if bert_results else '',
            'bert_nivel_1': bert.get('nivel_1', '') if bert_results else '',
            'bert_nivel_2': bert.get('nivel_2', '') if bert_results else '',
            'concordancia': concordancia,
            'observacoes': '',  # Vazio para curador preencher
            'avaliacao_curador': '',  # Vazio para curador preencher
        }

        rows.append(row)

    df = pl.DataFrame(rows)

    print(f"✓ Planilha criada com {len(df)} linhas")
    print(f"  Colunas: {len(df.columns)}")

    # Estatísticas de concordância
    concordancia_counts = df.group_by('concordancia').len()
    print("\nConcordância:")
    for row in concordancia_counts.iter_rows(named=True):
        print(f"  {row['concordancia']:25s}: {row['len']} notícias")

    return df


def save_curation_files(df: pl.DataFrame, news_list: List[Dict]):
    """Salva arquivos para curadoria."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Excel para curadoria visual
    excel_path = DATA_DIR / f"curadoria_3_abordagens_{timestamp}.xlsx"
    df.write_excel(excel_path)
    print(f"\n✓ Excel salvo: {excel_path.name}")

    # 2. CSV como backup
    csv_path = DATA_DIR / f"curadoria_3_abordagens_{timestamp}.csv"
    df.write_csv(csv_path)
    print(f"✓ CSV salvo: {csv_path.name}")

    # 3. JSON com conteúdo completo (para referência)
    import json
    json_data = []
    for news in news_list:
        df_row = df.filter(pl.col('unique_id') == news['unique_id'])[0]
        json_data.append({
            'unique_id': news['unique_id'],
            'title': news['title'],
            'content': news['content'],  # Conteúdo completo
            'classifications': {
                'claude': {
                    'categoria': df_row['claude_categoria'][0],
                    'nivel_1': df_row['claude_nivel_1'][0],
                    'nivel_2': df_row['claude_nivel_2'][0],
                },
                'rag': {
                    'categoria': df_row['rag_categoria'][0],
                    'nivel_1': df_row['rag_nivel_1'][0],
                    'nivel_2': df_row['rag_nivel_2'][0],
                } if df_row['rag_categoria'][0] else None,
                'bert': {
                    'categoria': df_row['bert_categoria'][0],
                    'nivel_1': df_row['bert_nivel_1'][0],
                    'nivel_2': df_row['bert_nivel_2'][0],
                } if df_row['bert_categoria'][0] else None,
            },
            'concordancia': df_row['concordancia'][0]
        })

    json_path = DATA_DIR / f"curadoria_3_abordagens_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f"✓ JSON salvo: {json_path.name}")

    print("\n" + "="*80)
    print("ARQUIVOS GERADOS")
    print("="*80)
    print(f"\n1. {excel_path.name}")
    print("   → Abra no Excel/LibreOffice para curadoria visual")
    print("   → Preencha colunas 'observacoes' e 'avaliacao_curador'")
    print(f"\n2. {csv_path.name}")
    print("   → Backup em CSV")
    print(f"\n3. {json_path.name}")
    print("   → Conteúdo completo das notícias")

    return excel_path, csv_path, json_path


def main():
    """Executa benchmark para curadoria."""
    print("\n" + "="*80)
    print("BENCHMARK PARA CURADORIA HUMANA")
    print("="*80)
    print()
    print("Este script:")
    print("  1. Pega 50 notícias ALEATÓRIAS do dataset")
    print("  2. Classifica com 3 abordagens (Claude, RAG, BERT)")
    print("  3. Salva em Excel/CSV para revisão manual")
    print()

    N_NEWS = 50
    SEED = 42  # Para reprodutibilidade

    # 1. Carregar notícias aleatórias
    news_list = load_random_news(n=N_NEWS, seed=SEED)

    # 2. Classificar com as 3 abordagens
    claude_results = classify_with_claude(news_list)
    rag_results = classify_with_rag(news_list)
    bert_results = classify_with_bert(news_list)

    # 3. Criar planilha de curadoria
    df = create_curation_dataframe(
        news_list,
        claude_results,
        rag_results,
        bert_results
    )

    # 4. Salvar arquivos
    excel_path, csv_path, json_path = save_curation_files(df, news_list)

    print("\n" + "="*80)
    print("✓ BENCHMARK PARA CURADORIA CONCLUÍDO!")
    print("="*80)
    print()
    print("Próximos passos:")
    print(f"  1. Abrir: {excel_path.name}")
    print("  2. Revisar cada linha:")
    print("     • Comparar classificações")
    print("     • Preencher 'observacoes'")
    print("     • Avaliar qual abordagem foi melhor")
    print("  3. Usar dados para apresentação ao gestor")
    print()


if __name__ == "__main__":
    main()
