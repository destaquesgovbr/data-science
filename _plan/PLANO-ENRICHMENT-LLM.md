# Plano: Migrar Enriquecimento do Cogfy para LLM via Bedrock

## Contexto

**Issue**: data-platform#56 + data-platform#65 — Substituir Cogfy por LLM via AWS Bedrock para enriquecimento de notícias (classificação temática 3 níveis + geração de summary), orquestrado por DAG Airflow.

**Problema**: O Cogfy é um serviço externo pago que introduz latência (20min de espera no pipeline diário) e dependência. O Luis Felipe já criou o pacote `news_enrichment` (v0.3.0) no repo `data-science/source/news-enrichment/` com suporte a Bedrock (Claude Haiku), classificação hierárquica e batch processing.

**Objetivo**: Criar uma DAG Airflow no repo `data-science`, seguindo o padrão dos demais repos de DAGs (`embeddings`, `data-publishing`), usando o código do Luis como plugin Composer.

---

## Repo: `data-science` — Reestruturação

O repo `data-science` atualmente não segue o padrão de DAGs. Precisa ganhar a estrutura padrão:

### Estrutura Atual
```
data-science/
├── source/
│   └── news-enrichment/
│       └── news_enrichment/    ← pacote do Luis
├── data/
├── pyproject.toml
└── poetry.lock
```

### Estrutura Alvo (seguindo padrão embeddings/data-publishing)
```
data-science/
├── src/
│   └── news_enrichment/        ← plugin Composer (mover de source/news-enrichment/)
│       ├── __init__.py
│       ├── classifier.py
│       ├── llm_client.py
│       ├── llm_client_optimized.py
│       ├── local_llm_client.py
│       ├── enricher.py
│       ├── dataset_manager.py
│       ├── postgres_exporter.py
│       └── taxonomy.py          ← NOVO: carrega taxonomia do PostgreSQL
├── dags/
│   ├── enrich_news_llm.py       ← NOVO: DAG Airflow
│   └── requirements.txt         ← documentação de deps (NÃO instalado pelo Composer)
├── tests/                        ← NOVO
│   └── test_enrichment.py
├── .github/
│   └── workflows/
│       └── composer-deploy-dags.yaml  ← NOVO: deploy via reusable workflow
├── _plan/                        ← Este diretório
├── source/
│   └── news-enrichment/         ← manter como referência/docs (ou remover)
├── data/
├── pyproject.toml
└── README.md
```

**Padrão seguido**: Mesmo de `embeddings` e `data-publishing`:
- `src/{plugin}/` → deployado para `{bucket}/plugins/{plugin}/`
- `dags/` → deployado para `{bucket}/dags/{repo_name}/`
- `.github/workflows/composer-deploy-dags.yaml` → reusable workflow

---

## Implementação Detalhada

### 1. Mover `news_enrichment` para `src/`

Mover o pacote Python de `source/news-enrichment/news_enrichment/` para `src/news_enrichment/`. O código do Luis já está funcional — a maioria dos módulos vai sem alteração.

### 2. `src/news_enrichment/taxonomy.py` — NOVO

Carrega a taxonomia de temas do PostgreSQL (tabela `themes`) em vez de depender de arquivo local:

```python
def load_taxonomy_from_postgres(database_url: str) -> dict:
    """Carrega árvore de temas do PostgreSQL para o formato esperado pelo classifier."""
    # Query: SELECT code, label, level, parent_code FROM themes ORDER BY code
    # Retorna dict hierárquico {code: {label, children: {...}}}
```

Alternativa: carregar do arquivo YAML existente (que o Luis já usa). Decidir baseado no que é mais prático no Composer.

### 3. Adaptar `src/news_enrichment/llm_client.py`

Ajustes mínimos para funcionar no Composer:
- Credenciais AWS via Airflow connection `aws_bedrock` (Secret Manager) em vez de env vars diretas
- Logging via `logging` padrão (Airflow captura)
- Sem alteração na lógica de retry/batch (já está boa)

### 4. `dags/enrich_news_llm.py` — DAG Airflow

```python
@dag(
    dag_id="enrich_news_llm",
    description="Enriquece notícias via LLM (Bedrock) — classificação temática + summary",
    schedule="*/10 * * * *",  # A cada 10 minutos
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["llm", "enrichment", "bedrock"],
    default_args={
        "owner": "data-science",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
)
```

**Task única `enrich`**:
1. Obtém connection `postgres_default` e `aws_bedrock` do Airflow
2. Query PostgreSQL: notícias com `theme_l1_id IS NULL` (sem filtro de data — processa tudo pendente)
3. Carrega taxonomia da tabela `themes`
4. Instancia `NewsClassifier` com credenciais Bedrock
5. Classifica em batches
6. Mapeia theme codes → theme IDs (join com tabela `themes`)
7. UPDATE no PostgreSQL: `theme_l1_id`, `theme_l2_id`, `theme_l3_id`, `most_specific_theme_id`, `summary`
8. Retorna estatísticas

### 5. Dependência `boto3` — Instalar via Terraform

O `dags/requirements.txt` **NÃO** é instalado pelo Composer. Pacotes extras devem ser adicionados via Terraform no repo `infra` (variável `pypi_packages` do `google_composer_environment`).

**Ação necessária**: PR no repo `infra` adicionando `boto3>=1.35.0` ao Terraform.

Manter `dags/requirements.txt` apenas como documentação.

### 6. `.github/workflows/composer-deploy-dags.yaml`

```yaml
name: Deploy Data Science DAGs to Composer

on:
  push:
    branches: [main]
    paths:
      - 'dags/**'
      - 'src/news_enrichment/**'
  workflow_dispatch:

permissions:
  contents: read
  id-token: write

jobs:
  deploy:
    uses: destaquesgovbr/reusable-workflows/.github/workflows/composer-deploy-dags.yml@v1
    with:
      dags_local_path: dags
      dags_bucket_subdir: data-science
      plugins_local_path: src/news_enrichment
      check_imports: true
      rsync_exclude: 'requirements\.txt$'
```

### 7. Testes

- Mock do boto3/Bedrock
- Testar parsing de respostas LLM (JSON extraction)
- Testar mapeamento de theme codes → IDs
- Testar lógica de retry

---

## Infra Necessária

### 1. Airflow Connection: `aws_bedrock`
```bash
echo "aws://:@/?aws_access_key_id=XXX&aws_secret_access_key=YYY&region_name=us-east-1" | \
  gcloud secrets create airflow-connections-aws_bedrock \
    --data-file=- --replication-policy=automatic \
    --project=inspire-7-finep

gcloud secrets add-iam-policy-binding airflow-connections-aws_bedrock \
  --member="serviceAccount:destaquesgovbr-composer@inspire-7-finep.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=inspire-7-finep
```

### 2. WIF para repo `data-science`
Verificar se já existe binding no Terraform. Se não:
- Adicionar `data-science` no `infra/terraform/workload-identity.tf`
- PR + merge + terraform apply

### 3. AWS Bedrock
- Modelo `anthropic.claude-3-5-haiku-20241022-v1:0` habilitado em `us-east-1`
- IAM policy com `bedrock:InvokeModel`

### 4. boto3 no Composer
- Adicionar `boto3>=1.35.0` em `pypi_packages` no Terraform do Composer
- PR no repo `infra` + merge + terraform apply

---

## Pipeline: Antes vs Depois

### Antes (Cogfy — GitHub Actions, main-workflow.yaml)
```
4AM: upload-to-cogfy → wait 20min → enrich-themes → typesense-sync → portal-cache
```

### Depois (LLM — Airflow)
```
*/10: enrich_news_llm (Bedrock, a cada 10min — processa notícias novas sem classificação)
5AM:  generate_embeddings (já existe)
→ typesense-sync (ajustar trigger)
```

- Roda a cada 10 minutos, classificando notícias novas assim que chegam
- Elimina 20min de espera do Cogfy
- Classificação síncrona via Bedrock
- O `main-workflow.yaml` do data-platform pode ter os steps Cogfy removidos (etapa futura)

---

## Verificação

1. **Testes unitários**: `pytest tests/test_enrichment.py`
2. **Deploy**: Push para branch → PR → merge → workflow deploya DAG + plugin
3. **Airflow UI**: Verificar DAG `enrich_news_llm` aparece sem import errors
4. **Trigger manual**: Executar, verificar classificação no PostgreSQL
5. **Validação de qualidade**: Comparar amostra LLM vs Cogfy
6. **Custos**: ~$0.25/1000 notícias (Claude Haiku)

---

## Fora de Escopo

- RAG para classificação (data-platform#74)
- Backfill completo da base (data-platform#67)
- Desativação do Cogfy / remoção do main-workflow.yaml
- Remoção do código Cogfy do data-platform
