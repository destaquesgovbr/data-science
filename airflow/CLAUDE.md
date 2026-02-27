# Airflow Local Dev (Astro CLI)

## Quick Start

```bash
cd airflow/

# Criar .env a partir do template
cp .env.example .env
# Editar .env com credenciais reais do PostgreSQL

# Subir (sem TTY, usa .env)
astro dev start --no-browser --settings-file ""

# Com TTY (Claude Code)
script -q /dev/null astro dev start --no-browser --wait 5m

# Airflow UI
open http://localhost:8080

# Parar
astro dev stop
```

## Versões

| Componente | Versão |
|-----------|--------|
| Astro CLI | 1.39.0 |
| Astro Runtime | 3.0-14 (Airflow 3.0.6) |
| Docker image | `astrocrpublic.azurecr.io/runtime:3.0-14` |

## Estrutura

```
airflow/
├── Dockerfile              # FROM astrocrpublic.azurecr.io/runtime:3.0-14
├── requirements.txt        # Python deps (boto3, psycopg2)
├── packages.txt            # OS deps (vazio)
├── .env                    # Connections + variables (gitignored)
├── .env.example            # Template das env vars
├── .airflowignore          # Ignora __pycache__, .git, tests
├── .dockerignore           # Ignora .git, .env, logs
├── dags -> ../dags         # Symlink para dags/ na raiz
├── plugins/
│   └── news_enrichment -> ../../src/news_enrichment  # Plugin
├── include/                # Assets compartilhados (vazio)
└── tests/                  # Testes DAG (vazio)
```

## Mock LLM

Para testar sem chamar AWS Bedrock, definir no `.env`:

```
MOCK_LLM=true
```

Isso ativa classificações sintéticas — o pipeline completo roda (fetch PG → classify → update PG) mas sem custo AWS.

## Connections

| Connection | Host | Descrição |
|-----------|------|-----------|
| `postgres_default` | `34.39.145.55` (Cloud SQL) | govbrnews — notícias |
| `aws_bedrock` | N/A | Credenciais AWS para Bedrock (opcional com mock) |

## Comandos úteis

```bash
astro dev ps                    # Ver containers
astro dev logs --follow         # Logs
astro dev run dags list         # Listar DAGs
astro dev run dags trigger enrich_news_llm  # Trigger manual
astro dev restart               # Rebuild após mudar requirements.txt
astro dev kill                  # Parar + remover volumes
```

## TTY no Claude Code

O `astro dev start` precisa de TTY para importar `airflow_settings.yaml`. No Claude Code:

```bash
script -q /dev/null astro dev start --no-browser --wait 5m
```
