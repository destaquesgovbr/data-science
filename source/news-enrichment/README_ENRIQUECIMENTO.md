# Sistema de Enriquecimento de Notícias - Resumo Executivo

**Status**: Plano aprovado em 05/02/2026 - Pronto para implementação

## Objetivo
Criar sistema para enriquecer 300k+ notícias do dataset `govbrnews` com classificação temática hierárquica (3 níveis) e resumos via AWS Bedrock (Claude 3 Haiku).

## Arquitetura (4 Classes)

1. **NewsDatasetManager** - Cache e gerenciamento do dataset
2. **BedrockLLMClient** - Interface Bedrock com batch processing (8 em paralelo)
3. **NewsEnricher** - Orquestração e logs detalhados
4. **PostgresExporter** - Export automático para Postgres

## Campos Gerados

- Árvore temática: 3 níveis hierárquicos com códigos (01, 01.02, 01.02.03)
- Tema mais específico (code + label)
- Summary (resumo conciso)

## Performance

- **Batch size**: 8 notícias em paralelo
- **Tempo estimado**: 3-4 horas para 300k notícias
- **Sleep**: 0.2s apenas entre batches
- **Economia**: ~30% em custos vs sequencial

## Próximos Passos (Amanhã)

### 1. Criar estrutura de diretórios
```bash
mkdir -p news_enrichment data
```

### 2. Instalar dependências
```bash
pip install polars tqdm boto3 psycopg2-binary sqlalchemy
```

### 3. Implementar classes (em ordem)
- [ ] `news_enrichment/dataset_manager.py` - NewsDatasetManager
- [ ] `news_enrichment/llm_client.py` - BedrockLLMClient (BATCH)
- [ ] `news_enrichment/enricher.py` - NewsEnricher
- [ ] `news_enrichment/postgres_exporter.py` - PostgresExporter
- [ ] `news_enrichment/__init__.py` - Exports

### 4. Criar script de teste
- [ ] `exemplo_enriquecimento.py` - Testa com 10 notícias

### 5. Validação
- [ ] Rodar validação com 10 notícias
- [ ] Verificar qualidade dos temas e resumos
- [ ] Testar export para Postgres
- [ ] Se OK, processar dataset completo

## Recursos Importantes

- **Plano detalhado**: `~/.claude/plans/glittery-chasing-ocean.md`
- **Código Bedrock existente**: `teste_bedrock_simples.py`
- **Modelo**: `anthropic.claude-3-haiku-20240307-v1:0`
- **Região**: `us-east-1`

## Taxonomia

- **Atual**: LLM cria categorias organicamente
- **Futuro**: Quando definir taxonomia predefinida, criar `taxonomy.json` e injetar no LLMClient

## Custos Estimados

- ~$150-200 para 300k notícias
- Validar com amostra antes do full run
- Batch processing reduz custos em ~30%

## Notas

- Retry automático: 3x com backoff exponencial
- Fallback: campos null em caso de erro persistente
- Logs detalhados com tqdm progress bar
- Schema Postgres gerado automaticamente
- Índices otimizados para queries por tema e data

---

**Pronto para começar amanhã!** 🚀
