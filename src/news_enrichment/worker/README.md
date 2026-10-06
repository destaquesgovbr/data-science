# Enrichment Worker

Serviço Cloud Run (`destaquesgovbr-enrichment-worker`) que recebe push do Pub/Sub
`dgb.news.scraped`, enriquece a notícia e publica `dgb.news.enriched`.

Código: `app.py` (FastAPI, endpoint `/process`) e `handler.py` (regras). Imagem:
`docker/enrichment-worker/Dockerfile`. Deploy: push em `src/news_enrichment/**`
na `main` (`.github/workflows/enrichment-worker-deploy.yaml`). As env vars são
geridas pelo Terraform no repo `infra/` (`terraform/enrichment-worker.tf`); o CI
só troca a imagem.

## Fluxo de `enrich_article(uid)`

1. **Idempotência:** se `news.most_specific_theme_id` já está preenchido → `skipped`.
2. `fetch_article` → `not_found` se não existe.
3. **Chamada combinada** (tema + resumo + sentimento) no modelo `ENRICHMENT_MODEL_ID`.
4. **Falha combinada** (`_error` no resultado ou todos os códigos de tema nulos):
   loga `enrichment_combined_failed`, roda o NER só se ainda não rodou para o uid,
   **não** atualiza tema/resumo, **não** publica e devolve `classification_failed`.
5. Sucesso: NER (no máximo 1x por uid) → `update_news_enrichment` (tema + resumo)
   → upsert de `sentiment`/`entities` em `news_features` → publica
   `dgb.news.enriched` → `enriched`. Se o UPDATE não grava nada → `update_failed`
   (sem publicar).

O `/process` responde **200 (ACK)** em todos esses status, inclusive em exceção não
tratada (evita retry infinito do Pub/Sub). Só payload inválido dá 400.

| Status | Significado | Publica `enriched`? |
|---|---|---|
| `enriched` | tema, resumo e sentimento gravados | sim |
| `skipped` | já tinha tema (republicação do scraper) | não |
| `not_found` | uid inexistente em `news` | não |
| `classification_failed` | chamada combinada falhou (campos `error` e `ner` no corpo) | não |
| `update_failed` | classificou, mas os códigos de tema não mapearam para `themes` | não |

## Configuração por env

| Env | Uso |
|---|---|
| `ENRICHMENT_MODEL_ID` | Modelo da chamada combinada. **Defina sempre.** Em produção: `us.anthropic.claude-haiku-4-5-20251001-v1:0` (Terraform `var.enrichment_model_id`, infra#215). Trocar de modelo = trocar só essa variável, com smoke antes. |
| `BEDROCK_MODEL_ID` | Nome legado, lido se `ENRICHMENT_MODEL_ID` faltar. |
| *(nenhuma das duas)* | Cai em `DEFAULT_ENRICHMENT_MODEL_ID` (Claude 3 Haiku, **EOL no Bedrock**) e loga ERROR `enrichment_model_env_missing`. O default não é trocado aqui de propósito (colide com o data-science#38). |
| `NER_MODEL_ID` | Modelo do NER dedicado (Sonnet 4.6 em produção). Sem ela, usa o modelo combinado. |
| `DATABASE_URL` | Postgres `govbrnews` (secret `govbrnews-postgres-connection-string`). |
| `AWS_BEDROCK_CONNECTION_URI` ou `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` | Credenciais do Bedrock (`AWS_REGION`, default `us-east-1`). |
| `PUBSUB_TOPIC_NEWS_ENRICHED` | Tópico de saída. Sem ela, não publica. |

O corpo da requisição é o formato Anthropic-on-Bedrock (`invoke_model` com
`anthropic_version`), então só modelos Anthropic funcionam sem mudança de código.
O Haiku 4.5 responde o JSON dentro de cercas `` ```json ``; o `_parse_response`
já tolera isso.

## Linhas de log estáveis

Formato fixo, pensado para métricas e alertas baseados em log. Não mude o prefixo
nem as chaves; campos novos entram no fim.

| Nível | Linha | Quando |
|---|---|---|
| ERROR | `enrichment_combined_failed uid=<uid> model=<id> error=<ErrorCode>: <msg>` | Toda falha da chamada combinada. `error` vem de `_error`; sem `_error` (temas todos nulos) é `AllThemeFieldsNull: …`. |
| CRITICAL | `enrichment_model_unavailable model=<id> error_code=<ErrorCode>` | Falha combinada por modelo indisponível: `ResourceNotFoundException` (fim de vida, id inexistente) ou `ValidationException`/`AccessDeniedException` que falam do modelo. **Alerta: troque `ENRICHMENT_MODEL_ID`.** |
| ERROR | `enrichment_update_failed uid=<uid> model=<id> stats=<stats>` | Classificou, mas nenhum código de tema mapeou para `themes`. |
| ERROR | `enrichment_model_env_missing default=<id> (...)` | No cold start, sem `ENRICHMENT_MODEL_ID`/`BEDROCK_MODEL_ID`. |
| INFO | `enrichment_ner uid=<uid> status=<ran\|failed\|skipped_already_done> model=<id> [entities=<n>]` | Uma por evento que chega à etapa de NER (métrica de NER por uid). |

Outras linhas úteis: `Cliente Bedrock inicializado: enrichment=<id> ner=<id>` (cold
start) e `Result for <uid>: <status>` (`app.py`, por evento).

Consulta de leitura (projeto `inspire-7-finep`):

```bash
gcloud logging read 'resource.type="cloud_run_revision"
  AND resource.labels.service_name="destaquesgovbr-enrichment-worker"
  AND (textPayload:"enrichment_model_unavailable" OR textPayload:"enrichment_combined_failed")' \
  --project=inspire-7-finep --freshness=1d --limit=20 --format='value(timestamp,textPayload)'
```

Contexto: o Claude 3 Haiku teve EOL no Bedrock e a chamada combinada falhou em
silêncio de 25/09 a 06/10/2026 (sem env, o worker usava o default legado). Essas
linhas existem para que a próxima falha desse tipo vire alerta no mesmo dia.

## NER no máximo uma vez por uid

O scraper republica `dgb.news.scraped` a cada re-scrape (~13x/dia por artigo).
Enquanto o tema não é gravado, a idempotência não segura essas republicações. Antes,
cada uma rodava o NER (Sonnet 4.6) de novo: ~US$33–46/dia a mais no incidente de
set–out/2026.

Agora o handler só chama `extract_entities` se `ner_already_done(uid)` for falso:

```sql
features ? 'entities'  -- em news_features
OR EXISTS (news_llm_raw WHERE task = 'ner')  -- NER respondeu, mesmo sem entidades
```

A guarda vale nos dois caminhos (falha e sucesso) e também protege entidades já
canonicalizadas, que o merge `features || {"entities": …}` sobrescreveria. Se a
consulta falhar, o NER é pulado (fail-closed) com WARNING; o
`scripts/backfill_ner_corpus.py` recupera os artigos sem NER.

## Re-enriquecimento sem NER (`scripts/reenrich_combined_window.py`)

Refaz só a chamada combinada numa janela de dias BRT (`--date-to` exclusivo).
Nunca chama o NER e nunca publica evento. Respeita o governador de cota por modelo.

```bash
ENRICHMENT_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
BEDROCK_DAILY_TOKEN_QUOTA='{"us.anthropic.claude-haiku-4-5-20251001-v1:0": <cota AWS real>}' \
PYTHONPATH=src .venv/bin/python scripts/reenrich_combined_window.py \
    --select null-theme --date-from 2026-09-25 --dry-run   # depois --limit 10, depois completo
```

- `--select null-theme`: `most_specific_theme_id IS NULL` na janela (B2).
- `--select mock`: `summary LIKE '[MOCK]%'` na janela (B5).
- `ENRICHMENT_MODEL_ID` é obrigatória (sem fallback). Modelo indisponível aborta com
  código 1. `budget_exhausted` encerra com 0 e o run é retomável.
- Use a cota **real** da AWS em `BEDROCK_DAILY_TOKEN_QUOTA`. A fração
  (`BACKFILL_QUOTA_FRACTION`, default 0.8) é aplicada uma única vez.
- Depois do backfill, o Typesense só reflete os temas após o `incremental-sync`.

## Testes

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests -q -p no:cacheprovider
```

Relevantes: `tests/test_enrichment_worker.py`, `tests/test_ner_handler.py`,
`tests/test_enrichment.py` e `tests/test_reenrich_combined_window.py`. O Postgres é
simulado por `tests/fakedb.py`.
