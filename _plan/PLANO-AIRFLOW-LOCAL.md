# Plano: Ambiente Airflow Local para Testar DAG enrich_news_llm

## Contexto

A DAG `enrich_news_llm` foi implementada na branch `feat/enrich-news-llm-dag` do repo `data-science`. Antes de fazer deploy no Cloud Composer, precisamos validar a DAG localmente usando Astro CLI (mesmo padrão do `activitypub-server/airflow/`). O LLM (Bedrock) será mockado para testar o fluxo completo sem custos AWS.

---

## Estrutura Alvo

```
data-science/
├── airflow/                          ← NOVO (Astro CLI project)
│   ├── Dockerfile                    # FROM astrocrpublic.azurecr.io/runtime:3.0-14
│   ├── requirements.txt              # boto3, psycopg2-binary
│   ├── packages.txt                  # vazio
│   ├── .env                          # Connections (gitignored)
│   ├── .env.example                  # Template das env vars
│   ├── .airflowignore                # Ignora __pycache__, .git, tests
│   ├── .dockerignore                 # Ignora .git, .env, logs
│   ├── .astro/
│   │   └── config.yaml               # project-name: data-science
│   ├── dags -> ../dags               # Symlink para dags/ na raiz
│   ├── plugins/
│   │   └── news_enrichment -> ../../src/news_enrichment  # Symlink para plugin
│   ├── include/                      # vazio (.gitkeep)
│   └── tests/                        # vazio
├── dags/
│   └── enrich_news_llm.py           # DAG existente
├── src/news_enrichment/              # Plugin existente
└── ...
```

---

## Verificação

1. `cd airflow/ && astro dev start --no-browser --settings-file ""`
2. Abrir http://localhost:8080 — verificar DAG `enrich_news_llm` aparece
3. Trigger manual da DAG — verificar que executa com mock (sem chamar Bedrock)
4. Verificar logs: estatísticas de enriquecimento mock
5. `astro dev stop`
