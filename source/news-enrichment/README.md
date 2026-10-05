# source/news-enrichment - Legacy Development Code

⚠️ **ATENÇÃO:** Este diretório contém código legacy de desenvolvimento e documentação histórica.

## Status

**Código de produção:** `src/news_enrichment/` (raiz do repositório)  
**Este diretório:** Código experimental, notebooks e documentação de desenvolvimento

## Estrutura

- `benchmarks/` - Benchmarks antigos de performance
- `docs/` - Documentação histórica do desenvolvimento
- `examples/` - Exemplos de uso (pode estar desatualizado)
- `*.md`, `*.qmd`, `*.ipynb` - Notebooks e documentação de pesquisa

## Diferenças vs src/news_enrichment/

### Este diretório (source/) contém:
- Código experimental de desenvolvimento
- Documentação de decisões técnicas (CLASSIFIER_README.md, DOCUMENTACAO_PROMPTS.md)
- Benchmarks históricos
- Classes antigas: `NewsEnricher`, `BedrockLLMClientOptimized`, `LocalLLMClient`

### Produção (src/) contém:
- Código canônico em produção
- Classes atuais: `NewsClassifier`, `enrichment_job`, `canonicalization`
- Sem documentação inline (documentação em docs/ na raiz)

## Por que mantemos ambos?

1. **Histórico de desenvolvimento:** Documentação de como chegamos à solução atual
2. **Referência técnica:** Decisões de prompt engineering, benchmarks
3. **Notebooks de pesquisa:** Análises exploratórias que geraram as issues

## Quando usar cada um?

- **Para produção/deploys:** USE `src/news_enrichment/` (SEMPRE)
- **Para pesquisa histórica:** Consulte `source/news-enrichment/` (LEITURA)
- **Para novos desenvolvimentos:** Crie em `src/` e documente em `docs/`

## Manutenção

Este diretório **NÃO** é mantido ativamente. Se você:
- Fizer mudanças em `src/news_enrichment/` → NÃO replique aqui
- Encontrar bugs aqui → Ignore (código não está em produção)
- Precisar de documentação → Migre para `docs/` na raiz

## Decisão (Code Review #38)

Mantido como arquivo histórico após code review de @miguellsfilho.  
Alternativa considerada: remover completamente (rejeitada para preservar histórico).

---

**Última atualização:** 2026-07-07  
**Responsável:** Luis Felipe de Moraes
