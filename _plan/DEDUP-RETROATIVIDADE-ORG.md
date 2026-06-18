# Retroatividade do dedup de entidades (ORG + cauda) — plano

> **STATUS: 🟡 PLANEJADO (2026-06-18).** Pré-requisito mergeado: PR #32 (acronym-aware
> dedup + threshold 0.85) e PR #33 (hotfix remoção do path-b). Falta o fix das 2 lacunas
> abaixo (1 PR) + aplicar.

## Contexto

O `--dedup` retroativo nunca rodou contra prod (só dry-run). Com o código corrigido
(#32 + #33), um dry-run de `--dedup --dedup-type ORG` contra **produção** propôs
**35 merges, todos legítimos** ("X" vs "X (SIGLA)" + duplicatas exatas) — zero
falsos-positivos após a remoção do path-b.

**Mas a inspeção do impacto revelou 2 lacunas no código de merge que precisam ser
corrigidas ANTES de aplicar.** Sem elas, o apply degrada os dados.

### Medição (dry-run ORG vs prod, 2026-06-18)
- 581 ORGs no registry; **35 pares** propostos para merge.
- Tocam **4.606 menções** (`news_features.features.entities[].canonical_id`) e
  **2.696 linhas** em `news_entities` (grafo).
- Outros tipos: LAW=0, POLICY=0, PROGRAM=0, **EVENT=2** (1 clara "Copa do Mundo FIFA
  de 2026" vs "2026"; 1 limítrofe "ENGP" vs "ENGP 2026" = distinção de edição → decisão
  do usuário).
- Órfãos atuais no banco: **0** (o LAW dedup anterior não orfanou por acaso — seu source
  não tinha menções).

## Lacuna 1 — `merge_entities` não reescreve `canonical_id` nas menções

`merge_entities` migra `entity_alias`, herda metadata e deleta o source de
`entity_registry`, mas **não** reescreve `news_features.features.entities[].canonical_id`
que apontam para o source. Consequência se aplicar como está:
- **4.606 menções ficam órfãs** (canonical_id → linha inexistente no registry).
- `news_entities.entity_id` tem FK `ON DELETE CASCADE` → as 2.696 linhas do source são
  apagadas; o rebuild da DAG `project_entity_graph` lê o JSONB ainda apontando para o
  source deletado → ou viola a FK no insert, ou descarta silenciosamente as menções →
  **grafo perde co-menções**.
- Não se auto-cura barato: re-canonicalizar exigiria re-tocar os 4.606 artigos (pulados
  por `news_llm_raw`).

**Fix:** adicionar ao `merge_entities` um passo set-based que reescreve o JSONB:
`UPDATE news_features SET features = jsonb_set(...)` trocando `canonical_id` source→target
em cada elemento de `features->'entities'`. Idempotente, na mesma transação dos demais
passos. (Não precisa tocar `news_entities`/`entity_edges` diretamente — a DAG
`project_entity_graph` reconstrói ambos a partir do JSONB corrigido.)

## Lacuna 2 — seleção source/target ignora Wikidata-wins

`run_dedup` escolhe target = "mais aliases" (desempate: menor id lexicográfico). Isso
**ignora a regra de identidade do projeto** (QID Wikidata > id interno `dgb_`). No
dry-run, ~18 dos 35 merges **deletam o QID e mantêm o `dgb_`** como chave canônica:
- `ANS (Q9592631)` → `dgb_ans`, `Anac (Q4314917)` → `dgb_anac`, `Ancine (Q9592643)` →
  `dgb_ancine`, `Inep (Q6041403)` → `dgb_inep`, `Iphan (Q391537)` → `dgb_iphan`,
  `MGI (Q115977947)` → `dgb_gestao`, `PRF (Q1158853)` → `dgb_prf`, etc.
- Perde a âncora linked-data como PK (o `wikidata_id` sobrevive na coluna via COALESCE,
  mas o **entity_id canônico** — usado em menções e como nó do grafo / SAME_AS — vira
  `dgb_`).

**Fix:** na seleção de target em `run_dedup`, **preferir o QID** (`entity_id ~ '^Q\d+$'`)
quando o par é QID×dgb_; só cair na heurística de alias-count quando ambos são do mesmo
tipo de id. Alinha com o Wikidata-wins já existente em `add_alias`.

## Plano de execução

### Fase 1 — fix das 2 lacunas (1 PR data-science, TDD)
- `merge_entities`: + passo de rewrite de `canonical_id` em `news_features` (source→target).
- `run_dedup`: seleção de target com Wikidata-wins (QID > dgb_), fallback alias-count.
- Testes (FakeDB): rewrite de menções no merge; QID escolhido como target em par QID×dgb_;
  par dgb_×dgb_ mantém heurística; idempotência.
- Estender FakeDB se preciso (handler do `jsonb_set` em news_features já existe p/ backfill).

### Fase 2 — aplicar (após Fase 1 mergeada + deployada)
1. Re-rodar `--dedup --dedup-type ORG --dry-run` → confirmar que as direções viraram
   (QID vira target nos ~18 casos) e contagem segue 35.
2. Aplicar: `python -m news_enrichment.canonicalization_job --dedup --dedup-type ORG`
   (local contra prod, padrão do LAW dedup) **ou** via Cloud Run Job
   (`gcloud run jobs execute destaquesgovbr-canon-backfill --args=--dedup,--dedup-type,ORG`).
3. Verificar pós-apply: `entity_registry` ORG cai ~35; **órfãos = 0** (query de
   validação); QIDs preservados como PK nos casos esperados.

### Fase 3 — downstream
4. Disparar `project_entity_graph` (ou aguardar run de 6h) → grafo reflete os merges
   (nós ORG↓, co-menções consolidadas).
5. `typesense-maintenance-sync` (incremental) → facets `entity_canonical` deduplicados.

### Fase 4 — cauda (decisão do usuário)
6. EVENT: aplicar "Copa do Mundo FIFA de 2026" (claro). "ENGP" vs "ENGP 2026" → decidir
   se editions devem fundir (provavelmente **não** — manter granularidade de edição).
   LAW/POLICY/PROGRAM: nada a fazer (0 propostas).

## Riscos & gates
- **Destrutivo / difícil reverter**: `merge_entities` deleta rows. Sempre dry-run antes;
  o apply só após Fase 1. Snapshot/backup do `entity_registry`+`entity_alias` antes do
  apply é recomendável (export rápido das ~581 ORGs + aliases).
- **Consistência eventual do grafo**: entre o apply e o próximo rebuild da DAG o grafo
  fica defasado (aceitável; rebuild é completo).
- **Nunca** rodar o apply sem o fix da Lacuna 1 (orfanaria 4.606 menções).
- Python sempre em venv; sem terraform/gcloud infra local.
