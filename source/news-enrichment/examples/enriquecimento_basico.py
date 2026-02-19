"""
Script de exemplo para testar o sistema de enriquecimento de notícias
Valida com amostra de 10 notícias antes do processamento completo
"""

from news_enrichment import NewsDatasetManager, BedrockLLMClient, NewsEnricher, PostgresExporter
from pathlib import Path

# Configuração de paths (independente de onde o script é executado)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def main():
    """Função principal de teste."""

    print("\n" + "="*80)
    print("SISTEMA DE ENRIQUECIMENTO DE NOTÍCIAS - VALIDAÇÃO")
    print("="*80 + "\n")

    # 1. Setup
    print("1. Configurando componentes...")
    print("-" * 80)

    dataset_manager = NewsDatasetManager(cache_dir=str(DATA_DIR))
    print("NewsDatasetManager inicializado")

    # LLM Client com batch processing (inicialmente sem taxonomia, orgânico)
    llm_client = BedrockLLMClient(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region="sa-east-1",
        taxonomy=None,  # ← Quando definir taxonomia, injetar aqui
        batch_size=8,  # Processa 8 notícias em paralelo
        sleep_between_batches=0.2  # 200ms entre batches
    )
    print("BedrockLLMClient inicializado")

    # Enricher com logs detalhados
    enricher = NewsEnricher(
        dataset_manager=dataset_manager,
        llm_client=llm_client,
        verbose=True
    )
    print("NewsEnricher inicializado\n")

    # 2. Testar com amostra de 500 notícias (cenário diário)
    print("\n" + "="*80)
    print("2. TESTE PRODUÇÃO - 500 NOTÍCIAS")
    print("="*80 + "\n")

    try:
        sample_enriched = enricher.enrich_sample(n=500, seed=42)
        enricher.save_enriched(sample_enriched, str(DATA_DIR / "sample_enriched.parquet"))
        print(f"Amostra enriquecida e salva em {DATA_DIR / 'sample_enriched.parquet'}")

    except Exception as e:
        print(f"\nErro ao enriquecer amostra: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Validar resultados
    print("\n" + "="*80)
    print("3. RESULTADOS DA AMOSTRA")
    print("="*80 + "\n")

    # Exibir preview dos resultados
    preview = sample_enriched.select([
        "unique_id",
        "title",
        "theme_1_level_1_label",
        "theme_1_level_2_label",
        "theme_1_level_3_label",
        "most_specific_theme_label",
        "summary"
    ]).head(10)

    print(preview)

    # 4. Estatísticas
    print("\n" + "="*80)
    print("4. ESTATÍSTICAS")
    print("="*80 + "\n")

    stats = enricher.get_enrichment_stats()
    print(f"Total processado: {stats['total_processed']} notícias")
    print(f"Sucessos: {stats['success_count']}")
    print(f"Falhas: {stats['failure_count']}")
    print(f"Taxa de sucesso: {stats['success_rate']:.1%}")
    print(f"Tempo médio: {stats['avg_time']:.2f}s por notícia")

    # 5. Exportar para Postgres (OPCIONAL - comentado por padrão)
    print("\n" + "="*80)
    print("5. EXPORTAR PARA POSTGRES (OPCIONAL)")
    print("="*80 + "\n")

    print("Para exportar para Postgres, descomente o código abaixo e configure a connection string:\n")
    print("# postgres_exporter = PostgresExporter(")
    print("#     connection_string='postgresql://user:password@localhost:5432/dbname'")
    print("# )")
    print("# postgres_exporter.export_to_postgres(")
    print("#     df=sample_enriched,")
    print("#     table_name='news_enriched',")
    print("#     if_exists='append'")
    print("# )")

    # 6. Próximos passos
    print("\n" + "="*80)
    print("6. PRÓXIMOS PASSOS")
    print("="*80 + "\n")

    print("Validação concluída com sucesso!")
    print("\nPara processar o dataset completo (300k+ notícias):")
    print("1. Verifique a qualidade dos temas e resumos acima")
    print("2. Estime custos: ~$150-200 para 300k notícias")
    print("3. Tempo estimado: ~3-4 horas (batch processing)")
    print("\nDescomente o código abaixo no script:\n")
    print("# full_enriched = enricher.enrich_full()")
    print(f"# enricher.save_enriched(full_enriched, '{DATA_DIR / 'govbrnews_enriched_full.parquet'}')")
    print("# postgres_exporter.export_to_postgres(full_enriched, 'news_enriched', if_exists='append')")

    print("\n" + "="*80)
    print("TESTE COMPLETO!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
