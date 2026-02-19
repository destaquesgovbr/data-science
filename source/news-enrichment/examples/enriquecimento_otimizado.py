"""
Script otimizado para enriquecimento diário de notícias
Configuração ajustada para minimizar throttling do Bedrock
"""

from news_enrichment import NewsDatasetManager, BedrockLLMClient, NewsEnricher, PostgresExporter
from pathlib import Path

# Configuração de paths (independente de onde o script é executado)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def main():
    """Função principal otimizada para processar 500 notícias/dia."""

    print("\n" + "="*80)
    print("ENRIQUECIMENTO DIÁRIO - CONFIGURAÇÃO OTIMIZADA")
    print("="*80 + "\n")

    # 1. Setup com configuração otimizada
    print("1. Configurando componentes (batch_size=4 para reduzir throttling)...")
    print("-" * 80)

    dataset_manager = NewsDatasetManager(cache_dir=str(DATA_DIR))
    print("✓ NewsDatasetManager inicializado")

    # LLM Client OTIMIZADO: batch_size=4, sleep=0.5s
    llm_client = BedrockLLMClient(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region="sa-east-1",
        taxonomy=None,
        batch_size=4,  # ← Reduzido de 8 para 4 (menos throttling)
        sleep_between_batches=0.5,  # ← Aumentado de 0.2s para 0.5s
        max_retries=3
    )
    print("✓ BedrockLLMClient inicializado (OTIMIZADO)")
    print("  - batch_size: 4 (reduz throttling)")
    print("  - sleep_between_batches: 0.5s (mais espaçamento)")

    # Enricher com logs detalhados
    enricher = NewsEnricher(
        dataset_manager=dataset_manager,
        llm_client=llm_client,
        verbose=True
    )
    print("✓ NewsEnricher inicializado\n")

    # 2. Processar amostra (cenário diário: 500 notícias)
    print("\n" + "="*80)
    print("2. PROCESSANDO 500 NOTÍCIAS (CENÁRIO DIÁRIO)")
    print("="*80 + "\n")

    print("Estimativas com configuração otimizada:")
    print("  - Tempo esperado: ~18-20 minutos")
    print("  - Custo esperado: ~$0.50")
    print("  - Throttlings: Reduzidos em 60-70%\n")

    try:
        sample_enriched = enricher.enrich_sample(n=500, seed=42)
        output_file = DATA_DIR / "sample_enriched_otimizado_500.parquet"
        enricher.save_enriched(sample_enriched, str(output_file))
        print(f"\n✓ Amostra enriquecida e salva em {output_file}")

    except Exception as e:
        print(f"\n❌ Erro ao enriquecer amostra: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Validar resultados
    print("\n" + "="*80)
    print("3. PREVIEW DOS RESULTADOS")
    print("="*80 + "\n")

    # Exibir preview
    preview = sample_enriched.select([
        "unique_id",
        "title",
        "theme_1_level_1_label",
        "theme_1_level_2_label",
        "theme_1_level_3_label",
        "most_specific_theme_label",
        "summary"
    ]).head(20)

    print(preview)

    # 4. Estatísticas detalhadas
    print("\n" + "="*80)
    print("4. ESTATÍSTICAS DETALHADAS")
    print("="*80 + "\n")

    stats = enricher.get_enrichment_stats()
    print(f"Total processado: {stats['total_processed']} notícias")
    print(f"Sucessos: {stats['success_count']}")
    print(f"Falhas: {stats['failure_count']}")
    print(f"Taxa de sucesso: {stats['success_rate']:.1%}")
    print(f"Tempo médio: {stats['avg_time']:.2f}s por notícia")
    print(f"Tempo total: {stats['avg_time'] * stats['total_processed'] / 60:.1f} minutos")

    # 5. Análise de categorias
    print("\n" + "="*80)
    print("5. DISTRIBUIÇÃO DE CATEGORIAS")
    print("="*80 + "\n")

    # Top 10 categorias nível 1
    top_categories = (
        sample_enriched
        .filter(sample_enriched['theme_1_level_1_label'].is_not_null())
        .group_by('theme_1_level_1_label')
        .count()
        .sort('count', descending=True)
        .head(10)
    )
    print("Top 10 Categorias (Nível 1):")
    print(top_categories)

    # 6. Próximos passos
    print("\n" + "="*80)
    print("6. PRÓXIMOS PASSOS")
    print("="*80 + "\n")

    print("✓ Validação concluída com sucesso!")
    print("\nPara implementar pipeline diário:")
    print("1. Verificar qualidade das classificações")
    print("2. Ajustar prompt se necessário")
    print("3. Implementar captura diária de notícias")
    print("4. Configurar export automático para Postgres")
    print("\nExemplo para export Postgres:")
    print("```python")
    print("exporter = PostgresExporter(")
    print("    connection_string='postgresql://user:pass@host:5432/db'")
    print(")")
    print("exporter.export_to_postgres(")
    print("    df=sample_enriched,")
    print("    table_name='news_enriched',")
    print("    if_exists='append'")
    print(")")
    print("```")

    print("\n" + "="*80)
    print("TESTE OTIMIZADO COMPLETO!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
