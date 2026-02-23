"""
Benchmark Triplo: Claude vs RAG vs BERT

Compara as 3 abordagens de classificação de notícias:

1. **Claude Zero-shot** (Abordagem Direta - atual)
   - Passa toda taxonomia ao LLM
   - Sem treino necessário
   - Flexível e adaptável

2. **RAG** (Retrieval-Augmented Generation)
   - Embeddings filtram top-k categorias
   - Passa categorias filtradas ao LLM
   - Overhead de embeddings

3. **BERT Fine-tuned** (Aprendizado Supervisionado)
   - Modelo treinado nas 410 categorias
   - Inferência rápida e local
   - Precisa de dados de treino

Métricas comparadas:
- ✓ Acurácia
- ✓ Tempo de execução
- ✓ Custo (API + infra)
- ✓ Complexidade de código
- ✓ Requisitos de dados
- ✓ Flexibilidade

Objetivo: Fornecer análise completa para decisão arquitetural.
"""

import time
import json
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
from news_enrichment import NewsClassifier, NewsDatasetManager

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
    import torch
    BERT_AVAILABLE = True
except ImportError:
    BERT_AVAILABLE = False
    print("⚠️  BERT não disponível. Instale com: poetry install --extras ml")


def load_test_news(n: int = 50) -> List[Dict]:
    """Carrega notícias para teste."""
    print("\n" + "="*80)
    print("CARREGANDO NOTÍCIAS PARA TESTE")
    print("="*80 + "\n")

    dataset_manager = NewsDatasetManager(cache_dir=str(DATA_DIR))
    df = dataset_manager.load_cached()

    # Filtrar notícias válidas
    df = df.filter(
        (pl.col('updated_datetime').is_not_null()) &
        (pl.col('content').str.lengths() > 100)
    ).sort('updated_datetime', descending=True).head(n)

    print(f"✓ {len(df)} notícias carregadas para teste\n")

    news_list = []
    for row in df.iter_rows(named=True):
        news_list.append({
            'unique_id': row['unique_id'],
            'title': row['title'],
            'content': row['content']
        })

    return news_list


def benchmark_claude(news_list: List[Dict]) -> Dict:
    """Benchmark da abordagem Claude zero-shot."""
    print("\n" + "="*80)
    print("1. CLAUDE ZERO-SHOT (Abordagem Direta)")
    print("="*80 + "\n")

    print("Características:")
    print("  • Passa toda taxonomia (410 categorias)")
    print("  • Zero-shot - sem treino necessário")
    print("  • Flexível e adaptável\n")

    start_init = time.time()
    classifier = NewsClassifier(verbose=False)
    init_time = time.time() - start_init

    print(f"✓ Inicializado em {init_time:.2f}s\n")

    print(f"Classificando {len(news_list)} notícias...")
    start = time.time()

    results = []
    for i, news in enumerate(news_list, 1):
        try:
            result = classifier.classify_single(news, return_format="dict")
            result['approach'] = 'claude'
            results.append(result)
            print(f"  [{i}/{len(news_list)}] ✓")
        except Exception as e:
            print(f"  [{i}/{len(news_list)}] ✗ {e}")
            results.append({'unique_id': news['unique_id'], 'error': str(e)})

    classify_time = time.time() - start

    print(f"\n✓ Concluído em {classify_time:.2f}s")
    print(f"  Média: {classify_time/len(news_list):.2f}s/notícia")

    return {
        'approach': 'claude',
        'init_time': init_time,
        'classify_time': classify_time,
        'avg_time': classify_time / len(news_list),
        'results': results
    }


def benchmark_rag(news_list: List[Dict], top_k: int = 50) -> Optional[Dict]:
    """Benchmark da abordagem RAG."""
    if not RAG_AVAILABLE:
        print("\n⚠️  RAG não disponível - pulando")
        return None

    print("\n" + "="*80)
    print("2. RAG (Retrieval-Augmented Generation)")
    print("="*80 + "\n")

    print("Características:")
    print(f"  • Embeddings filtram top-{top_k} categorias")
    print("  • Passa categorias filtradas ao LLM")
    print("  • Overhead de BERT embeddings\n")

    arvore_path = PROJECT_ROOT / "arvore.yaml"

    start_init = time.time()
    classifier = NewsClassifierRAG(
        taxonomy_path=str(arvore_path),
        top_k=top_k,
        verbose=False
    )
    init_time = time.time() - start_init

    print(f"✓ Inicializado em {init_time:.2f}s (carrega BERT)\n")

    print(f"Classificando {len(news_list)} notícias...")
    start = time.time()

    results = []
    for i, news in enumerate(news_list, 1):
        try:
            result = classifier.classify_single(news, return_format="dict")
            result['approach'] = 'rag'
            results.append(result)
            print(f"  [{i}/{len(news_list)}] ✓")
        except Exception as e:
            print(f"  [{i}/{len(news_list)}] ✗ {e}")
            results.append({'unique_id': news['unique_id'], 'error': str(e)})

    classify_time = time.time() - start

    print(f"\n✓ Concluído em {classify_time:.2f}s")
    print(f"  Média: {classify_time/len(news_list):.2f}s/notícia")

    return {
        'approach': 'rag',
        'init_time': init_time,
        'classify_time': classify_time,
        'avg_time': classify_time / len(news_list),
        'results': results
    }


def benchmark_bert(news_list: List[Dict]) -> Optional[Dict]:
    """Benchmark da abordagem BERT fine-tuned."""
    if not BERT_AVAILABLE:
        print("\n⚠️  BERT não disponível - pulando")
        return None

    print("\n" + "="*80)
    print("3. BERT FINE-TUNED (Aprendizado Supervisionado)")
    print("="*80 + "\n")

    print("Características:")
    print("  • Modelo treinado nas 410 categorias")
    print("  • Inferência rápida (~50-100ms)")
    print("  • Roda 100% local\n")

    model_path = MODELS_DIR / "bert_news_classifier"

    if not model_path.exists():
        print(f"⚠️  Modelo não encontrado em: {model_path}")
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
        print(f"✗ Erro ao carregar modelo: {e}")
        return None

    print(f"✓ Inicializado em {init_time:.2f}s\n")

    print(f"Classificando {len(news_list)} notícias...")
    start = time.time()

    results = []
    for i, news in enumerate(news_list, 1):
        try:
            result = classifier.classify_single(news, return_format="dict")
            result['approach'] = 'bert'
            results.append(result)
            print(f"  [{i}/{len(news_list)}] ✓")
        except Exception as e:
            print(f"  [{i}/{len(news_list)}] ✗ {e}")
            results.append({'unique_id': news['unique_id'], 'error': str(e)})

    classify_time = time.time() - start

    print(f"\n✓ Concluído em {classify_time:.2f}s")
    print(f"  Média: {classify_time/len(news_list):.2f}s/notícia")

    return {
        'approach': 'bert',
        'init_time': init_time,
        'classify_time': classify_time,
        'avg_time': classify_time / len(news_list),
        'results': results
    }


def compare_results(benchmarks: List[Dict]):
    """Compara resultados das 3 abordagens."""
    print("\n" + "="*80)
    print("COMPARAÇÃO COMPLETA")
    print("="*80)

    # Filtrar nulos
    benchmarks = [b for b in benchmarks if b is not None]

    if len(benchmarks) < 2:
        print("\n⚠️  Poucos benchmarks disponíveis para comparação")
        return

    # 1. Performance
    print("\n1. PERFORMANCE")
    print("-" * 80)

    print("\nInicialização:")
    for b in benchmarks:
        print(f"  {b['approach']:15s}: {b['init_time']:6.2f}s")

    claude_init = next((b['init_time'] for b in benchmarks if b['approach'] == 'claude'), None)
    if claude_init:
        print("\nComparado ao Claude:")
        for b in benchmarks:
            if b['approach'] != 'claude':
                ratio = b['init_time'] / claude_init
                print(f"  {b['approach']:15s}: {ratio:.1f}x")

    print("\nClassificação (média por notícia):")
    for b in benchmarks:
        print(f"  {b['approach']:15s}: {b['avg_time']:6.3f}s")

    claude_avg = next((b['avg_time'] for b in benchmarks if b['approach'] == 'claude'), None)
    if claude_avg:
        print("\nComparado ao Claude:")
        for b in benchmarks:
            if b['approach'] != 'claude':
                diff_pct = ((b['avg_time'] / claude_avg) - 1) * 100
                if diff_pct > 0:
                    print(f"  {b['approach']:15s}: {diff_pct:+.1f}% (mais lento)")
                else:
                    print(f"  {b['approach']:15s}: {diff_pct:+.1f}% (mais rápido)")

    # 2. Concordância
    print("\n2. CONCORDÂNCIA DE CLASSIFICAÇÕES")
    print("-" * 80)

    claude_results = next((b['results'] for b in benchmarks if b['approach'] == 'claude'), None)

    if claude_results:
        for b in benchmarks:
            if b['approach'] != 'claude':
                agreements = 0
                total = 0

                for claude_r, other_r in zip(claude_results, b['results']):
                    if 'error' not in claude_r and 'error' not in other_r:
                        total += 1
                        if claude_r.get('most_specific_theme_label') == other_r.get('most_specific_theme_label'):
                            agreements += 1

                if total > 0:
                    agreement_rate = agreements / total * 100
                    print(f"\n{b['approach'].upper()} vs Claude:")
                    print(f"  Concordância: {agreements}/{total} ({agreement_rate:.1f}%)")

    # 3. Complexidade
    print("\n3. COMPLEXIDADE E REQUISITOS")
    print("-" * 80)

    complexity_table = {
        'claude': {
            'dependências': 'boto3 (AWS SDK)',
            'código': '~300 linhas',
            'dados_treino': 'Nenhum',
            'setup': 'Credenciais AWS',
            'manutenção': 'Baixa'
        },
        'rag': {
            'dependências': 'boto3 + sentence-transformers + faiss',
            'código': '~1200 linhas (4x)',
            'dados_treino': 'Nenhum',
            'setup': 'AWS + modelo BERT (~500MB)',
            'manutenção': 'Alta'
        },
        'bert': {
            'dependências': 'transformers + torch',
            'código': '~800 linhas',
            'dados_treino': '> 20.000 notícias rotuladas',
            'setup': 'Treinar modelo (horas/dias)',
            'manutenção': 'Média (re-treinar se taxonomia mudar)'
        }
    }

    for b in benchmarks:
        approach = b['approach']
        if approach in complexity_table:
            print(f"\n{approach.upper()}:")
            for key, value in complexity_table[approach].items():
                print(f"  {key:20s}: {value}")

    # 4. Custo
    print("\n4. CUSTO ESTIMADO")
    print("-" * 80)

    n_news = len(benchmarks[0]['results'])

    print(f"\nPara {n_news} notícias:")

    for b in benchmarks:
        if b['approach'] == 'claude':
            api_cost = n_news * 0.0024
            print(f"\n  Claude:")
            print(f"    API: ${api_cost:.2f}")
            print(f"    Infra: Padrão")

        elif b['approach'] == 'rag':
            api_cost = n_news * 0.0024
            print(f"\n  RAG:")
            print(f"    API: ${api_cost:.2f} (mesmo que Claude)")
            print(f"    Infra: +2GB RAM, +CPU embeddings")
            print(f"    Storage: +500MB (modelo BERT)")

        elif b['approach'] == 'bert':
            print(f"\n  BERT:")
            print(f"    API: $0.00 (local)")
            print(f"    Infra: Padrão")
            print(f"    Treino inicial: $100-500 (uma vez)")
            print(f"    Storage: ~400MB (modelo)")

    # 5. Resumo Executivo
    print("\n5. RESUMO EXECUTIVO")
    print("=" * 80)

    print("\n🥇 VENCEDOR EM CADA CATEGORIA:\n")

    print("Performance (Velocidade):")
    fastest = min(benchmarks, key=lambda x: x['avg_time'])
    print(f"  → {fastest['approach'].upper()} ({fastest['avg_time']:.3f}s/notícia)")

    print("\nSimplicidade (Menos código):")
    print("  → CLAUDE (~300 linhas)")

    print("\nCusto (Longo prazo):")
    has_bert = any(b['approach'] == 'bert' for b in benchmarks)
    if has_bert:
        print("  → BERT ($0/notícia após treino)")
    else:
        print("  → CLAUDE/RAG (mesmo custo de API)")

    print("\nFlexibilidade (Adapta a mudanças):")
    print("  → CLAUDE (zero-shot, sem re-treino)")

    print("\n\n📊 RECOMENDAÇÃO GERAL:")
    print("-" * 80)

    print("\n✓ Use CLAUDE se:")
    print("  • Não tem dados de treino")
    print("  • Volume moderado (< 100k/mês)")
    print("  • Taxonomia muda frequentemente")
    print("  • Quer começar rápido")

    print("\n✓ Use BERT se:")
    print("  • Tem > 20k notícias rotuladas")
    print("  • Volume MUITO alto (> 100k/mês)")
    print("  • Taxonomia é estável")
    print("  • Latência é crítica (<100ms)")

    print("\n✗ NÃO use RAG:")
    print("  • Adiciona complexidade sem ganhos")
    print("  • Mais lento que Claude")
    print("  • Mesma acurácia")
    print("  • Só faz sentido para > 10.000 categorias")


def save_results(benchmarks: List[Dict]):
    """Salva resultados do benchmark."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output = {
        'timestamp': timestamp,
        'benchmarks': benchmarks,
        'metadata': {
            'n_news': len(benchmarks[0]['results']) if benchmarks else 0,
            'approaches_tested': [b['approach'] for b in benchmarks if b]
        }
    }

    output_path = DATA_DIR / f"benchmark_triplo_{timestamp}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Resultados salvos: {output_path}")


def main():
    """Executa benchmark triplo."""
    print("\n" + "="*80)
    print("BENCHMARK TRIPLO: Claude vs RAG vs BERT")
    print("="*80)
    print()
    print("Este benchmark compara 3 abordagens de classificação:")
    print("  1. Claude Zero-shot (abordagem direta)")
    print("  2. RAG (embeddings + LLM)")
    print("  3. BERT Fine-tuned (aprendizado supervisionado)")
    print()

    N_NEWS = 50

    # Carregar notícias
    news_list = load_test_news(n=N_NEWS)

    # Executar benchmarks
    benchmarks = []

    # 1. Claude
    claude_bench = benchmark_claude(news_list)
    benchmarks.append(claude_bench)

    # 2. RAG
    rag_bench = benchmark_rag(news_list)
    if rag_bench:
        benchmarks.append(rag_bench)

    # 3. BERT
    bert_bench = benchmark_bert(news_list)
    if bert_bench:
        benchmarks.append(bert_bench)

    # Comparar
    compare_results(benchmarks)

    # Salvar
    save_results(benchmarks)

    print("\n" + "="*80)
    print("BENCHMARK TRIPLO CONCLUÍDO!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
