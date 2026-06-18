# Canonicalization: 4 Correções de Qualidade (TDD + Subagentes)

## Contexto

Job local revelou 4 problemas na qualidade da canonicalização. Todos os changes em:
- `data-science/src/news_enrichment/canonicalization.py`
- `data-science/src/news_enrichment/canonicalization_job.py`
- `data-science/tests/fakedb.py` (extensões para novos SQL patterns)
- `data-science/tests/test_canonicalization.py`
- `data-science/tests/test_canonicalization_job.py`

Metodologia: **TDD estrito** — cada subagente escreve testes que falham (red) → implementa (green) → confirma suite completa passa. Subagentes sequenciais (mesmos arquivos, sem conflito).

---

## Problema 1: `"ira"` NULL entity_id — NÃO É BUG

`action="drop"` + `status='resolved'` + `entity_id=NULL` é o caminho `not_an_entity=True` em `apply_gates:555` → `_persist_decision:344`. "Ira" = raiva em PT, NER misclassificou. Nenhuma mudança de código.

---

## Subagente 1 — `merge_entities` + FakeDB

**Arquivo alvo:** `canonicalization.py` (nova função antes de `add_alias:851`)

**Contrato:**
```python
def merge_entities(conn, source_id: str, target_id: str) -> int:
    """Merge source_id → target_id: migra aliases, herda metadata, deleta source.
    Returns: número de alias rows migradas.
    """
```

**SQL emitido (para o FakeDB reconhecer):**
1. `UPDATE entity_registry AS t SET wikidata_id=... FROM entity_registry s WHERE t.entity_id=... AND s.entity_id=...` — herda wikidata_id + merge aliases JSONB
2. `UPDATE entity_alias SET entity_id=%s WHERE entity_id=%s AND NOT EXISTS (...)` — redireciona sem criar conflito de PK
3. `DELETE FROM entity_alias WHERE entity_id=%s` — limpa aliases restantes do source
4. `DELETE FROM entity_registry WHERE entity_id=%s` — remove source

**FakeDB** (`tests/fakedb.py`): adicionar handlers para os 4 SQL acima em `FakeCursor.execute`. A lógica em memória:
- UPDATE entity_registry JOIN: copia `wikidata_id` do source para target se target não tem; merge `aliases` JSONB (union de listas)
- UPDATE entity_alias WHERE NOT EXISTS: percorre `db.alias` — para cada `(alias_norm, atype)` apontando para source, muda para target SE ainda não existe `(alias_norm, atype) → target`; rastrear rowcount
- DELETE entity_alias WHERE entity_id: remove todas as entradas de `db.alias` com valor = source_id
- DELETE entity_registry WHERE entity_id: remove `db.registry[source_id]`

**Testes (TDD — escrever ANTES de implementar):**

```python
class TestMergeEntities:
    def test_aliases_migrated_to_target(self):
        # db.alias: ("ministerio saude", "ORG") → "dgb_ms"
        #           ("ms", "ORG") → "dgb_ms"
        # Merge dgb_ms → Q12345 → aliases devem apontar para Q12345
        ...

    def test_source_removed_from_registry(self):
        # Após merge, db.registry não contém source_id
        ...

    def test_wikidata_id_inherited_by_target(self):
        # source tem wikidata_id="Q999"; target não tem → target deve ter wikidata_id="Q999"
        ...

    def test_conflicting_alias_not_migrated_but_source_cleaned(self):
        # ("nome", "ORG") já aponta para target (conflito PK) → alias NÃO migra
        # mas source é limpo de entity_alias e entity_registry
        ...

    def test_returns_migrated_count(self):
        # 2 aliases migrados → retorna 2
        ...
```

---

## Subagente 2 — `add_alias` Wikidata-wins

**Arquivo alvo:** `canonicalization.py` (modificar `add_alias:851`)

**Regra:** quando existing começa com `dgb_` E novo entity_id NÃO começa com `dgb_` → chamar `merge_entities(source=existing, target=new_entity_id)` + reescrever alias com `INSERT ... ON CONFLICT DO UPDATE SET entity_id = EXCLUDED.entity_id`.

**FakeDB**: o `INSERT INTO entity_alias ... ON CONFLICT ... DO UPDATE` deve fazer UPDATE quando existe conflito (atual `setdefault` não sobrescreve). Substituir por assign direto quando for `DO UPDATE`.

**Testes:**

```python
class TestAddAliasWikidataWins:
    def test_dgb_vs_qid_triggers_merge_and_promotes_alias(self):
        # alias "ans" → "dgb_ans" já existe
        # add_alias("ans", "ORG", "Q9592631", ...) →
        #   merge executado (dgb_ans removido, alias migrado), alias aponta para Q9592631
        ...

    def test_two_dgb_still_first_write_wins(self):
        # alias "xx" → "dgb_a"; add_alias com "dgb_b" → ambiguous, sem merge
        ...

    def test_two_qids_still_first_write_wins(self):
        # alias "xx" → "Q1"; add_alias com "Q2" → ambiguous, sem merge
        ...

    def test_dgb_vs_qid_returns_merged_true(self):
        # result["merged"] is True
        ...

    def test_existing_entity_registry_wikidata_id_updated_after_merge(self):
        # dgb_ans no registry sem wikidata_id; após merge com Q9592631,
        # Q9592631 no registry herdou algum metadata do dgb_ans
        ...
```

---

## Subagente 3 — `find_existing_entity_by_name` + reuso LAW/outros

**Arquivo alvo:** `canonicalization.py` (nova função + constante) + `canonicalization_job.py` (`_persist_decision`)

**Constante nova (canonicalization.py):**
```python
_ENTITY_REUSE_THRESHOLDS: dict[str, float] = {
    "ORG":     0.62,
    "LAW":     0.75,
    "POLICY":  0.70,
    "PROGRAM": 0.70,
    "EVENT":   0.80,
}
```

**Nova função (ou renomear/generalizar `find_existing_org_by_name`):**
```python
def find_existing_entity_by_name(
    conn, canonical_name: str, entity_type: str,
    threshold: float = 0.70
) -> Optional[str]:
    """Reuso por nome para qualquer tipo (pg_trgm + Jaccard fallback).
    Igual a find_existing_org_by_name mas parametrizado por tipo.
    """
```

**FakeDB**: estender o handler `"select entity_id, canonical_name from entity_registry where type"` para aceitar qualquer type além de 'org'.

**Alteração em `_persist_decision`** (`canonicalization_job.py:379`): expandir de `ORG + is_br_gov_org` para todos os tipos com threshold definido:
```python
else:
    threshold = _ENTITY_REUSE_THRESHOLDS.get(resolved_type)
    if threshold is not None:
        existing = find_existing_entity_by_name(conn, canonical_name, resolved_type, threshold)
        if existing is not None:
            entity_id = existing
    if entity_id is None:
        entity_id = mint_internal_id(canonical_name)
```

**Testes:**

```python
class TestFindExistingEntityByName:
    def test_law_near_duplicate_reuses_existing(self):
        # registry tem "Lei nº 14.967/2024" → dgb_lei-14-967
        # find_existing_entity_by_name("Lei 14.967, de 9 de setembro de 2024", "LAW", 0.75)
        # → retorna dgb_lei-14-967 (Jaccard > 0.75)
        ...

    def test_law_different_number_not_reused(self):
        # "Lei nº 14.100/2022" não reusa "Lei nº 14.967/2024"
        ...

    def test_org_still_works_as_before(self):
        # backward compat: ORG com threshold 0.62 funciona igual ao anterior
        ...

class TestPersistDecisionLawReuse:
    def test_law_near_duplicate_does_not_mint_new_entity(self):
        # Duas resoluções da mesma lei com nomes ligeiramente diferentes
        # → segunda reusa entity_id da primeira, nenhuma mint nova
        ...
```

---

## Subagente 4 — PER Short-Circuit

**Arquivo alvo:** `canonicalization_job.py` (`resolve_form:293`)

**Regra:** para `type == "PER"`, após gazetteer miss (linha ~283) e ANTES de `llm_canonicalize` (linha ~295): pesquisar Wikidata com `form_norm` bruto. Se lista vazia → `needs_review` imediato, zero tokens.

```python
# 1.5) PER fast-path: pre-check Wikidata sem Bedrock.
if type == "PER" and wikidata_client is not None:
    pre_candidates = wikidata_client.search(form_norm)
    if not pre_candidates:
        if not dry_run:
            _update_seen(conn, form_norm, type, "needs_review", None, attempts + 1)
        return {"action": "needs_review", "status": "needs_review",
                "entity_id": None, "usage": _zero_usage()}
```

**Testes:**

```python
class TestPERShortCircuit:
    def test_per_with_no_wikidata_skips_bedrock(self):
        # FakeWikidata retorna [] para form_norm
        # → Bedrock NÃO é chamado; seen status = needs_review
        ...

    def test_per_with_wikidata_candidates_proceeds_to_llm(self):
        # FakeWikidata retorna [Candidate(qid="Q37181", ...)] para "lula"
        # → Bedrock É chamado (escalada normal)
        ...

    def test_per_short_circuit_dry_run_does_not_write_seen(self):
        # dry_run=True: seen NÃO é atualizado mesmo sem candidatos Wikidata
        ...

    def test_org_type_not_short_circuited(self):
        # ORG com Wikidata vazio NÃO entra no short-circuit
        # → continua para LLM normalmente
        ...
```

---

## Subagente 5 — `--dedup` CLI

**Arquivo alvo:** `canonicalization_job.py` (argparse + nova função `run_dedup`)

**Interface:**
```bash
python -m news_enrichment.canonicalization_job --dedup [--type LAW] [--dry-run]
```

**Lógica `run_dedup(conn, entity_type, dry_run, threshold)`:**
1. `SELECT entity_id, canonical_name FROM entity_registry WHERE type = %s`
2. Comparar pares por Jaccard de tokens (fallback Python sem pg_trgm)
3. Para pares com score > threshold: no dry-run, logar merge proposto; no apply, chamar `merge_entities(source, target)` onde source = menor número de aliases
4. Retornar contagem de merges executados/propostos

**Testes:**

```python
class TestDedup:
    def test_dry_run_does_not_merge(self):
        # registry com duas leis near-duplicate → dry_run=True → nenhum merge executado
        ...

    def test_apply_merges_near_duplicates(self):
        # registry com duas leis near-duplicate → dry_run=False → merge executado,
        # sobra apenas uma entidade no registry
        ...

    def test_dissimilar_entities_not_merged(self):
        # "Lei 14.967/2024" e "Lei 14.100/2022" → não merged
        ...
```

---

## Ordem de Execução dos Subagentes

```
Subagente 1: merge_entities + FakeDB  (bloqueante — base dos outros)
    ↓
Subagente 2: add_alias Wikidata-wins  (usa merge_entities)
    ↓
Subagente 3: find_existing_entity + _persist_decision  (independente de 2, mas aguarda 1)
    ↓
Subagente 4: PER short-circuit  (independente — poderia ser paralelo com 2-3, mas mesmo arquivo)
    ↓
Subagente 5: --dedup CLI  (usa merge_entities — aguarda 1)
```

Cada subagente ao terminar DEVE rodar `pytest tests/test_canonicalization.py tests/test_canonicalization_job.py -v` e confirmar 0 falhas antes de encerrar.

## PR Final

Após todos os subagentes: um único PR `data-science` com todas as mudanças, sem Co-Authored-By (regra do repo).
