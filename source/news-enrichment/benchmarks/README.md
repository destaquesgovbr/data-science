# Benchmarks

Scripts para análise de performance e comparação de modelos/prompts.

## Scripts Disponíveis

### benchmark_modelos.py
Compara diferentes modelos LLM (Claude Haiku, Sonnet, GPT-4, etc.) em termos de:
- Tempo de resposta
- Custo por notícia
- Qualidade da classificação

### benchmark_prompts.py
Testa diferentes estratégias de prompting:
- Single-shot vs Sequential
- Com/sem exemplos
- Diferentes formatos de saída

## Como Executar

```bash
# Benchmark de modelos
python benchmark_modelos.py

# Benchmark de prompts
python benchmark_prompts.py
```

## Resultados

Os resultados são salvos em:
- Arquivos CSV na pasta `output/`
- Logs detalhados no terminal
- Visualizações (se matplotlib estiver instalado)

Consulte `../docs/DOCUMENTACAO_PROMPTS.qmd` para análise completa dos resultados.
