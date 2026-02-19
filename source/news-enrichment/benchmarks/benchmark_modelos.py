"""
Benchmark: Claude Haiku vs Claude Sonnet
Teste com 25 notícias mais recentes para comparação de qualidade e performance
"""

from news_enrichment import NewsDatasetManager, BedrockLLMClient, NewsEnricher
import polars as pl
import time
from datetime import datetime
from pathlib import Path

# Configuração de paths (independente de onde o script é executado)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def filtrar_noticias_recentes(dataset_manager, n=25):
    """Filtra as N notícias mais recentes com data válida."""
    print("\n" + "="*80)
    print("FILTRANDO NOTÍCIAS MAIS RECENTES")
    print("="*80 + "\n")

    # Carregar dataset completo
    df = dataset_manager.load_cached()
    print(f"Dataset completo: {len(df):,} notícias")

    # Filtrar apenas com data válida
    df = df.filter(pl.col('updated_datetime').is_not_null())
    print(f"Com data válida: {len(df):,} notícias")

    # Ordenar por data (mais recente primeiro)
    df = df.sort('updated_datetime', descending=True)

    # Pegar as N mais recentes
    sample = df.head(n)

    print(f"\nSelecionadas {len(sample)} notícias mais recentes:")
    print(f"  Data mais recente: {sample['updated_datetime'].max()}")
    print(f"  Data mais antiga: {sample['updated_datetime'].min()}")

    return sample


def testar_modelo(model_id, model_name, sample_df, batch_size=4, sleep=0.5):
    """Testa um modelo específico com a amostra."""
    print("\n" + "="*80)
    print(f"TESTE: {model_name}")
    print("="*80)
    print(f"Modelo: {model_id}")
    print(f"Configuração: batch_size={batch_size}, sleep={sleep}s\n")

    start_time = time.time()

    # Setup
    dataset_manager = NewsDatasetManager(cache_dir=str(DATA_DIR))

    llm_client = BedrockLLMClient(
        model_id=model_id,
        region="us-east-1",
        taxonomy=None,
        batch_size=batch_size,
        sleep_between_batches=sleep
    )

    enricher = NewsEnricher(
        dataset_manager=dataset_manager,
        llm_client=llm_client,
        verbose=True
    )

    # Processar (sem usar enrich_sample, processar direto o dataframe filtrado)
    print(f"Processando {len(sample_df)} notícias...\n")

    # Converter para lista de dicts para processar
    rows = sample_df.to_dicts()
    enriched_rows = llm_client.enrich_news_batch(rows)

    # Criar DataFrame enriquecido
    enriched_df = pl.DataFrame(enriched_rows, infer_schema_length=len(enriched_rows))

    total_time = time.time() - start_time

    # Calcular estatísticas
    success_count = enriched_df.filter(
        pl.col('theme_1_level_1').is_not_null()
    ).height

    success_rate = success_count / len(enriched_df) * 100
    avg_time = total_time / len(enriched_df)

    # Adicionar metadados do teste
    enriched_df = enriched_df.with_columns([
        pl.lit(model_name).alias('model_name'),
        pl.lit(model_id).alias('model_id'),
        pl.lit(datetime.now().isoformat()).alias('benchmark_timestamp')
    ])

    print("\n" + "="*80)
    print(f"RESULTADOS - {model_name}")
    print("="*80)
    print(f"✓ Total: {len(enriched_df)} notícias")
    print(f"✓ Sucesso: {success_count}/{len(enriched_df)} ({success_rate:.1f}%)")
    print(f"✓ Tempo total: {total_time:.1f}s ({total_time/60:.2f} min)")
    print(f"✓ Tempo médio: {avg_time:.2f}s por notícia")

    return {
        'model_name': model_name,
        'model_id': model_id,
        'total_time': total_time,
        'avg_time': avg_time,
        'success_count': success_count,
        'success_rate': success_rate,
        'enriched_df': enriched_df
    }


def calcular_custos_estimados(results):
    """Calcula custos estimados baseado nos preços do Bedrock."""
    # Preços Bedrock por 1M tokens (aproximados)
    prices = {
        'Claude Haiku': {
            'input': 0.25,   # $0.25 per 1M input tokens
            'output': 1.25   # $1.25 per 1M output tokens
        },
        'Claude Sonnet 3.5': {
            'input': 3.00,   # $3.00 per 1M input tokens
            'output': 15.00  # $15.00 per 1M output tokens
        }
    }

    # Estimativas de tokens (baseado em observações anteriores)
    # Por notícia: ~1500 tokens input, ~200 tokens output
    tokens_input_per_news = 1500
    tokens_output_per_news = 200

    for result in results:
        model = result['model_name']
        n_noticias = 25

        if model in prices:
            input_cost = (tokens_input_per_news * n_noticias / 1_000_000) * prices[model]['input']
            output_cost = (tokens_output_per_news * n_noticias / 1_000_000) * prices[model]['output']
            total_cost = input_cost + output_cost

            result['estimated_input_cost'] = input_cost
            result['estimated_output_cost'] = output_cost
            result['estimated_total_cost'] = total_cost
            result['cost_per_news'] = total_cost / n_noticias


def comparar_resultados(results):
    """Compara os resultados dos modelos."""
    print("\n" + "="*80)
    print("COMPARAÇÃO DETALHADA: HAIKU vs SONNET")
    print("="*80 + "\n")

    # Tabela comparativa
    print(f"{'Métrica':<30} {'Haiku':<25} {'Sonnet 3.5':<25} {'Diferença':<20}")
    print("-" * 100)

    haiku = results[0]
    sonnet = results[1]

    # Tempo
    print(f"{'Tempo Total':<30} "
          f"{haiku['total_time']:.1f}s ({haiku['total_time']/60:.2f}min) "
          f"{'':<5}"
          f"{sonnet['total_time']:.1f}s ({sonnet['total_time']/60:.2f}min) "
          f"{'':<5}"
          f"{((sonnet['total_time'] - haiku['total_time'])/haiku['total_time']*100):+.1f}%")

    print(f"{'Tempo Médio/Notícia':<30} "
          f"{haiku['avg_time']:.2f}s"
          f"{'':<20}"
          f"{sonnet['avg_time']:.2f}s"
          f"{'':<20}"
          f"{((sonnet['avg_time'] - haiku['avg_time'])/haiku['avg_time']*100):+.1f}%")

    # Taxa de sucesso
    print(f"{'Taxa de Sucesso':<30} "
          f"{haiku['success_rate']:.1f}%"
          f"{'':<20}"
          f"{sonnet['success_rate']:.1f}%"
          f"{'':<20}"
          f"{(sonnet['success_rate'] - haiku['success_rate']):+.1f}pp")

    # Custos
    print(f"\n{'Custo (25 notícias)':<30} "
          f"${haiku['estimated_total_cost']:.4f}"
          f"{'':<20}"
          f"${sonnet['estimated_total_cost']:.4f}"
          f"{'':<20}"
          f"{(sonnet['estimated_total_cost']/haiku['estimated_total_cost']):.1f}x")

    print(f"{'Custo por Notícia':<30} "
          f"${haiku['cost_per_news']:.5f}"
          f"{'':<20}"
          f"${sonnet['cost_per_news']:.5f}"
          f"{'':<20}"
          f"{(sonnet['cost_per_news']/haiku['cost_per_news']):.1f}x")

    # Projeções
    print("\n" + "="*80)
    print("PROJEÇÕES MENSAIS (110 notícias/dia × 30 dias = 3.300 notícias)")
    print("="*80 + "\n")

    noticias_mes = 110 * 30

    haiku_custo_mes = haiku['cost_per_news'] * noticias_mes
    haiku_tempo_mes = haiku['avg_time'] * noticias_mes / 60  # minutos

    sonnet_custo_mes = sonnet['cost_per_news'] * noticias_mes
    sonnet_tempo_mes = sonnet['avg_time'] * noticias_mes / 60  # minutos

    print(f"{'Modelo':<20} {'Custo/Mês':<20} {'Tempo/Mês':<20} {'Tempo/Dia':<20}")
    print("-" * 80)
    print(f"{'Haiku':<20} ${haiku_custo_mes:<19.2f} {haiku_tempo_mes:<19.0f}min {haiku_tempo_mes/30:<19.0f}min")
    print(f"{'Sonnet 3.5':<20} ${sonnet_custo_mes:<19.2f} {sonnet_tempo_mes:<19.0f}min {sonnet_tempo_mes/30:<19.0f}min")

    print(f"\nDiferença mensal:")
    print(f"  Custo: ${sonnet_custo_mes - haiku_custo_mes:.2f} a mais ({sonnet_custo_mes/haiku_custo_mes:.1f}x)")
    print(f"  Tempo: {sonnet_tempo_mes - haiku_tempo_mes:.0f}min a mais ({sonnet_tempo_mes/haiku_tempo_mes:.1f}x)")

    # Análise de qualidade
    print("\n" + "="*80)
    print("ANÁLISE DE QUALIDADE (Amostra)")
    print("="*80 + "\n")

    print("Comparando primeiras 3 notícias de cada modelo:\n")

    # Converter para dicts para acesso mais fácil
    haiku_rows = haiku['enriched_df'].to_dicts()
    sonnet_rows = sonnet['enriched_df'].to_dicts()

    for idx in range(min(3, len(haiku_rows))):
        haiku_row = haiku_rows[idx]
        sonnet_row = sonnet_rows[idx]

        print(f"--- NOTÍCIA {idx+1} ---")
        print(f"Título: {haiku_row['title'][:80] if haiku_row['title'] else 'N/A'}...")
        print(f"\nHaiku:")
        print(f"  Tema: {haiku_row['most_specific_theme_label'] or 'N/A'}")
        summary_haiku = haiku_row['summary'] or 'N/A'
        print(f"  Resumo: {summary_haiku[:120] if len(str(summary_haiku)) > 120 else summary_haiku}...")
        print(f"\nSonnet:")
        print(f"  Tema: {sonnet_row['most_specific_theme_label'] or 'N/A'}")
        summary_sonnet = sonnet_row['summary'] or 'N/A'
        print(f"  Resumo: {summary_sonnet[:120] if len(str(summary_sonnet)) > 120 else summary_sonnet}...")
        print()


def main():
    """Executa benchmark completo."""
    print("\n" + "="*80)
    print("BENCHMARK: CLAUDE HAIKU vs CLAUDE SONNET 3.5")
    print("Teste com 25 notícias mais recentes")
    print("="*80 + "\n")

    # 1. Filtrar notícias mais recentes
    dataset_manager = NewsDatasetManager(cache_dir=str(DATA_DIR))
    sample = filtrar_noticias_recentes(dataset_manager, n=25)

    # 2. Testar ambos os modelos
    results = []

    # Teste 1: Claude Haiku (atual)
    result_haiku = testar_modelo(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        model_name="Claude Haiku",
        sample_df=sample,
        batch_size=4,
        sleep=0.5
    )
    results.append(result_haiku)

    print("\n" + "="*80)
    print("Aguardando 10 segundos antes do próximo teste...")
    print("="*80)
    time.sleep(10)

    # Teste 2: Claude Sonnet 3.5
    result_sonnet = testar_modelo(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        model_name="Claude Sonnet 3.5",
        sample_df=sample,
        batch_size=4,
        sleep=0.5
    )
    results.append(result_sonnet)

    # 3. Calcular custos
    calcular_custos_estimados(results)

    # 4. Comparar resultados
    comparar_resultados(results)

    # 5. Salvar resultados combinados
    print("\n" + "="*80)
    print("SALVANDO RESULTADOS")
    print("="*80 + "\n")

    # Combinar os DataFrames enriquecidos
    haiku_df = results[0]['enriched_df'].with_columns(
        pl.lit("haiku").alias("modelo_teste")
    )
    sonnet_df = results[1]['enriched_df'].with_columns(
        pl.lit("sonnet").alias("modelo_teste")
    )

    combined = pl.concat([haiku_df, sonnet_df])

    output_path = DATA_DIR / "benchmark_haiku_vs_sonnet.parquet"
    combined.write_parquet(str(output_path))
    print(f"✓ Resultados salvos: {output_path}")
    print(f"  Total: {len(combined)} notícias ({len(haiku_df)} Haiku + {len(sonnet_df)} Sonnet)")

    # Salvar também CSV para fácil inspeção
    csv_path = DATA_DIR / "benchmark_haiku_vs_sonnet.csv"

    # Selecionar colunas relevantes para CSV
    compare_cols = [
        'unique_id', 'title', 'modelo_teste',
        'theme_1_level_1_label', 'theme_1_level_2_label', 'theme_1_level_3_label',
        'most_specific_theme_label', 'summary',
        'model_name', 'benchmark_timestamp'
    ]

    combined.select(compare_cols).write_csv(str(csv_path))
    print(f"✓ CSV comparativo salvo: {csv_path}")

    # Salvar metadados do benchmark
    import json
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'n_noticias': 25,
        'haiku': {
            'model_id': results[0]['model_id'],
            'total_time': results[0]['total_time'],
            'avg_time': results[0]['avg_time'],
            'success_rate': results[0]['success_rate'],
            'estimated_cost': results[0]['estimated_total_cost']
        },
        'sonnet': {
            'model_id': results[1]['model_id'],
            'total_time': results[1]['total_time'],
            'avg_time': results[1]['avg_time'],
            'success_rate': results[1]['success_rate'],
            'estimated_cost': results[1]['estimated_total_cost']
        }
    }

    metadata_path = DATA_DIR / "benchmark_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Metadados salvos: {metadata_path}")

    print("\n" + "="*80)
    print("BENCHMARK CONCLUÍDO!")
    print("="*80 + "\n")

    print("Arquivos gerados:")
    print(f"  • {output_path} (dados completos)")
    print(f"  • {csv_path} (comparação lado-a-lado)")
    print(f"  • {metadata_path} (estatísticas)")
    print()


if __name__ == "__main__":
    main()
