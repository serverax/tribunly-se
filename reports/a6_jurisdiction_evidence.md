# A6 — Jurisdiction Modularity Evidence (Sweden-readiness)

SA-4 (Jurisdiction) under WO007. Evidence-gathering only; no fixes applied.
Date: 2026-07-08. DB: docker compose service `db` (pgvector/pg16), database `lawapp`.
Branch inspected: main-restored working tree at F:\lawapp-restore.

## Verdict summary

- **Data plane is jurisdiction-modular**: `rules`, `legislation`, `corpus_chunks` all carry
  jurisdiction columns with FKs to a `legal_jurisdictions` registry (5 rows: EW, GB, NI, S, UK).
  Adding SE = new registry row + new data rows.
- **Module catalog is registry-backed**: 24 topics live as rows in `employment_modules`
  (migration `db/migrations/058_employment_module_catalog.sql`), not hardcoded lists.
- **Code plane is NOT Sweden-ready**: 276 hardcoded hits in backend code (excluding tests).
  `"EW"` is the pervasive default parameter (103 sites); unknown jurisdictions are silently
  coerced to `"EW"` in `brain.py` and `orchestrator.py`; UK statutes (ERA 1996, Equality Act
  2010, WTR 1998) are embedded in engine constants, fallback authority maps, and document
  templates. Several query sites do not filter on jurisdiction at all.

---

## (a) Database queries

### a.1 `SELECT DISTINCT jurisdiction FROM rules;` (raw output)

```
 jurisdiction
--------------
 GB
 EW
(2 rows)
```

Distribution (supporting evidence):

```
-- rules:        GB=7, EW=118
-- legislation:  EW=84
-- corpus_chunks (jurisdiction_code): GB=13
```

### a.2 `legal_jurisdictions` registry (raw output)

```
                  id                  | jurisdiction_code | country_code |       label       |                                     legal_system                                      | applies_to_employment_law |                                                     notes
--------------------------------------+-------------------+--------------+-------------------+----------------------------------------------------------------------------------------+---------------------------+---------------------------------------------------------------------------------------------------------------
 0ac11f7a-adfa-4bca-9f45-8db319daa72e | EW                | EW           | England and Wales | England and Wales                                                                      | t                         |
 2414dac7-c354-4421-8766-bba5ae19e20b | GB                | GB           | Great Britain     | Employment law covering England, Wales and Scotland where legislation applies GB-wide  | t                         | Default for ordinary unfair dismissal MVP.
 5514fcff-1885-45a0-a734-61a855b593d9 | NI                | NIR          | Northern Ireland  | Northern Ireland employment law                                                        | t                         | Separate legislation (e.g. Employment Rights (NI) Order 1996). NOT yet ingested - unsupported / fail-closed.
 a71401d7-6c6a-4a51-a805-12ca7c4d1389 | S                 | SCT          | Scotland          | Scots law                                                                              | t                         | Shares GB employment-law values where source applies GB-wide.
 b63c7211-e2cf-4898-90da-f07bb98c24e6 | UK                | UK           | United Kingdom    | UK-wide source or institution                                                          | t                         | Only where the source is genuinely UK-wide.
(5 rows)
```

### a.3 Table schemas (raw `\d` output)

```
                                            Table "public.rules"
          Column          |           Type           | Collation | Nullable |            Default            
--------------------------+--------------------------+-----------+----------+-------------------------------
 id                       | uuid                     |           | not null | gen_random_uuid()
 rule_key                 | text                     |           | not null | 
 claim_type               | text                     |           | not null | 
 jurisdiction             | text                     |           | not null | 'EW'::text
 value_numeric            | numeric                  |           |          | 
 value_text               | text                     |           |          | 
 unit                     | text                     |           |          | 
 description              | text                     |           | not null | 
 authority_type           | text                     |           | not null | 
 authority_ref            | text                     |           | not null | 
 authority_url            | text                     |           | not null | 
 effective_from           | date                     |           | not null | 
 effective_to             | date                     |           |          | 
 is_prospective           | boolean                  |           | not null | false
 last_verified_at         | timestamp with time zone |           | not null | now()
 verification_status      | text                     |           |          | 'verification_required'::text
 verification_notes       | text                     |           |          | 
 domain                   | text                     |           |          | 
 country_code             | text                     |           |          | 
 jurisdiction_code        | text                     |           |          | 
 legal_system             | text                     |           |          | 
 applies_to_ni            | boolean                  |           |          | false
 applies_to_scotland      | boolean                  |           |          | false
 applies_to_england_wales | boolean                  |           |          | false
 applies_to_gb            | boolean                  |           |          | false
 is_current               | boolean                  |           |          | true
Indexes:
    "rules_pkey" PRIMARY KEY, btree (id)
    "rules_claim_juris_eff_idx" btree (claim_type, jurisdiction_code, effective_from, effective_to)
    "rules_claim_type_idx" btree (claim_type, jurisdiction)
    "rules_current_partial_idx" btree (rule_key, jurisdiction_code) WHERE is_current = true
    "rules_effective_idx" btree (effective_from, effective_to)
    "rules_juris_current_idx" btree (jurisdiction_code, is_current)
    "rules_key_idx" btree (rule_key)
    "rules_key_juris_eff_idx" btree (rule_key, jurisdiction_code, effective_from, effective_to)
    "rules_prospective_idx" btree (is_prospective)
    "rules_rule_key_jurisdiction_effective_from_key" UNIQUE CONSTRAINT, btree (rule_key, jurisdiction, effective_from)
    "rules_rulekey_trgm" gin (rule_key gin_trgm_ops)
    "rules_verif_idx" btree (verification_status)
    "rules_verification_idx" btree (verification_status, is_prospective)
Foreign-key constraints:
    "rules_jurisdiction_fk" FOREIGN KEY (jurisdiction_code) REFERENCES legal_jurisdictions(jurisdiction_code)

                                   Table "public.legislation"
          Column          |           Type           | Collation | Nullable |      Default      
--------------------------+--------------------------+-----------+----------+-------------------
 id                       | uuid                     |           | not null | gen_random_uuid()
 act_title                | text                     |           | not null | 
 leg_type                 | text                     |           | not null | 
 year                     | integer                  |           | not null | 
 chapter                  | text                     |           |          | 
 section_ref              | text                     |           |          | 
 jurisdiction             | text                     |           | not null | 'EW'::text
 heading                  | text                     |           |          | 
 body_text                | text                     |           | not null | 
 chunk_index              | integer                  |           | not null | 0
 embedding                | vector(384)              |           |          | 
 source_url               | text                     |           | not null | 
 version_date             | date                     |           |          | 
 effective_from           | date                     |           |          | 
 effective_to             | date                     |           |          | 
 is_prospective           | boolean                  |           | not null | false
 last_verified_at         | timestamp with time zone |           | not null | now()
 created_at               | timestamp with time zone |           | not null | now()
 content_hash             | text                     |           |          | 
 country_code             | text                     |           |          | 
 domain                   | text                     |           |          | 
 source_type              | text                     |           |          | 
 licence_status           | text                     |           |          | 
 parser_type              | text                     |           |          | 
 parent_source_id         | text                     |           |          | 
 jurisdiction_code        | text                     |           |          | 
 legal_system             | text                     |           |          | 
 applies_to_ni            | boolean                  |           |          | false
 applies_to_scotland      | boolean                  |           |          | false
 applies_to_england_wales | boolean                  |           |          | false
 applies_to_gb            | boolean                  |           |          | false
Indexes:
    "legislation_pkey" PRIMARY KEY, btree (id)
    "legislation_act_section_idx" btree (act_title, section_ref)
    "legislation_acttitle_trgm" gin (act_title gin_trgm_ops)
    "legislation_current_idx" btree (section_ref) WHERE is_prospective = false
    "legislation_emb_hnsw" hnsw (embedding vector_cosine_ops)
    "legislation_embedding_idx" ivfflat (embedding vector_cosine_ops) WITH (lists='10')
    "legislation_fts_idx" gin (to_tsvector('english'::regconfig, body_text))
    "legislation_in_force_idx" btree (effective_from, effective_to) WHERE effective_to IS NULL
    "legislation_jurisdiction_idx" btree (jurisdiction)
    "legislation_section_trgm" gin (section_ref gin_trgm_ops)
    "legislation_source_chunk_uq" UNIQUE, btree (source_url, chunk_index)
Foreign-key constraints:
    "legislation_jurisdiction_fk" FOREIGN KEY (jurisdiction_code) REFERENCES legal_jurisdictions(jurisdiction_code)

                                    Table "public.corpus_chunks"
        Column        |           Type           | Collation | Nullable |          Default          
----------------------+--------------------------+-----------+----------+---------------------------
 id                   | uuid                     |           | not null | gen_random_uuid()
 source_table         | text                     |           | not null | 
 source_row_id        | bigint                   |           |          | 
 source_row_uuid      | uuid                     |           |          | 
 source_id            | bigint                   |           |          | 
 domain               | text                     |           | not null | 'employment_uk'::text
 claim_type           | text                     |           |          | 
 jurisdiction_code    | text                     |           | not null | 
 country_code         | text                     |           |          | 
 authority_ref        | text                     |           |          | 
 source_url           | text                     |           | not null | 
 title                | text                     |           |          | 
 heading              | text                     |           |          | 
 body_text            | text                     |           | not null | 
 chunk_index          | integer                  |           | not null | 
 chunk_hash           | text                     |           | not null | 
 tokens_estimate      | integer                  |           |          | 
 embedding            | vector(1024)             |           |          | 
 embedding_model      | text                     |           |          | 'bge-large-en-v1.5'::text
 embedding_created_at | timestamp with time zone |           |          | 
 effective_from       | date                     |           |          | 
 effective_to         | date                     |           |          | 
 is_current           | boolean                  |           |          | true
 is_prospective       | boolean                  |           |          | false
 quality_score        | numeric                  |           |          | 
 legal_topics         | text[]                   |           |          | 
 source_type          | text                     |           |          | 
 authority_weight     | text                     |           |          | 
 licence_status       | text                     |           |          | 
 created_at           | timestamp with time zone |           | not null | now()
 updated_at           | timestamp with time zone |           | not null | now()
 ingestion_run_id     | uuid                     |           |          | 
 provision_id         | uuid                     |           |          | 
 embedding_dim        | integer                  |           |          | 
Indexes:
    "corpus_chunks_pkey" PRIMARY KEY, btree (id)
    "corpus_chunks_authref_trgm" gin (authority_ref gin_trgm_ops)
    "corpus_chunks_chunk_hash_key" UNIQUE CONSTRAINT, btree (chunk_hash)
    "corpus_chunks_current_idx" btree (is_current) WHERE is_current = true
    "corpus_chunks_current_partial_idx" btree (jurisdiction_code, claim_type) WHERE is_current = true
    "corpus_chunks_emb_hnsw" hnsw (embedding vector_cosine_ops)
    "corpus_chunks_fts_idx" gin (to_tsvector('english'::regconfig, body_text))
    "corpus_chunks_juris_idx" btree (jurisdiction_code, claim_type, domain)
    "corpus_chunks_provision_idx" btree (provision_id) WHERE provision_id IS NOT NULL
    "corpus_chunks_run_idx" btree (ingestion_run_id)
    "corpus_chunks_src_idx" btree (source_table, source_row_uuid)
    "corpus_chunks_title_trgm" gin (title gin_trgm_ops)
Foreign-key constraints:
    "corpus_chunks_jurisdiction_code_fkey" FOREIGN KEY (jurisdiction_code) REFERENCES legal_jurisdictions(jurisdiction_code)
    "corpus_chunks_provision_id_fkey" FOREIGN KEY (provision_id) REFERENCES knowledge.provision(id)
    "corpus_chunks_source_id_fkey" FOREIGN KEY (source_id) REFERENCES legal_sources(id)

```

### a.4 Query-path audit — does each rules/legislation/corpus query filter on jurisdiction?

Verified by reading each query site. "filters" = binds a jurisdiction parameter in the WHERE
clause; "assumes EW/UK-only" = no jurisdiction predicate, correctness depends on the corpus
containing only one regime.

| Query site (file:line) | Table | Jurisdiction handling |
|---|---|---|
| backend/core/retrieve.py:83 (`jurisdiction_supported`) | rules | FILTERS — `jurisdiction = ANY(%s)` via `juris_codes()`; fail-closed `("__none__",)` for unknown codes |
| backend/core/retrieve.py:129 (`retrieve_rules`) | rules | FILTERS — `jurisdiction = ANY(%s)` (GB code set) |
| backend/core/retrieve.py:182 (`retrieve_keyword`, legislation FTS) | legislation | FILTERS — `jurisdiction = ANY(%s)` |
| backend/core/retrieve.py:354 (`retrieve_semantic`) | corpus_chunks | FILTERS — `jurisdiction_code = ANY(%s)` |
| backend/api/main.py:514 (`get_rules`) | rules | FILTERS — `jurisdiction = %s` (exact match; default param `"EW"`) |
| backend/api/main.py:2802/2811/2874/2878 (admin/rule dumps) | rules | NO FILTER — full-table admin dumps (acceptable: admin surface) |
| backend/core/sovereign/answer.py:30 (`retrieve_cited_chunks`) | corpus_chunks | FILTERS — `jurisdiction_code = ANY(%s)` via `juris_codes()` |
| backend/core/semantic_cache.py:72 (source version) | legislation | FILTERS — `jurisdiction = %s` |
| backend/core/mcp_connectors.py:141 (`_legislation_lookup`) | legislation | FILTERS — `jurisdiction = %s` (default `"EW"`) |
| backend/core/mcp_connectors.py:253 (freshness) | rules/legislation | NO FILTER — freshness counts only (benign) |
| backend/services/lawapp-rag-service/main.py:211 (FTS) | corpus_chunks | **NO FILTER — assumes single-jurisdiction corpus** |
| backend/services/lawapp-rag-service/main.py:297 (vector) | corpus_chunks | **NO FILTER — assumes single-jurisdiction corpus** |
| backend/services/lawapp-citation-guard/main.py:130 (`_verify_citations`) | corpus_chunks | NO FILTER — existence check by chunk id (jurisdiction-neutral by design) |
| backend/core/feature_spec_service.py:116 (module provisions) | corpus_chunks | **NO FILTER — claim_type only; assumes UK corpus** |
| backend/core/citations/linker.py:38 (`_resolve_legislation`) | legislation | **NO FILTER — act_title/section match only; assumes UK acts** |
| backend/core/citation_verifier.py:85,92 | legislation | **NO FILTER — act_title ILIKE; assumes UK acts** |
| backend/domains/employment/constructive_dismissal.py:60 | legislation | **NO FILTER + hardcodes `act_title ILIKE '%Employment Rights Act 1996%'` in SQL** |
| backend/core/legal_truth_validator.py:89 | corpus_chunks | NO FILTER — existence check by id (jurisdiction-neutral) |
| backend/core/agentic/corpus_citation_guard.py:43 | corpus_chunks | NO FILTER — existence check by id; line 292 then accepts `EW/GB/UK` as always-compatible (**hardcoded UK jurisdiction whitelist in logic**) |
| backend/core/sovereign/graph_hydrator.py / rag/graphrag_traversal.py | graph | FILTERS — jurisdiction param threaded, but default `"EW"`; neo4j graph_engine.py:122 hardcodes `IN [$jurisdiction, 'GB', 'EW', 'UK']` |

Jurisdiction routing chokepoints (coercion, not fail-closed):

- backend/core/brain.py:601-602 — `if j not in ("EW", "SC", "NI"): j = "EW"` — an unknown
  jurisdiction (e.g. `SE`) is silently rewritten to England & Wales before retrieval.
- backend/core/orchestrator.py:70-72 — identical coercion.
- backend/core/brain.py:228 — response gate `resp_j in ("EW", "SC", "NI")` hardcodes the
  supported set in code rather than reading `legal_jurisdictions`.
- backend/core/retrieve.py:60-63 — `_GB_CODES = ("GB", "EW", "S", "UK")` and
  `_JURISDICTION_CODE_MAP` hardcode the jurisdiction universe; unknown codes DO fail closed
  here (`("__none__",)`), which is the correct pattern — but the map itself is code, not the
  `legal_jurisdictions` table.

---

## (b) Module catalog dump

Migration: `db/migrations/058_employment_module_catalog.sql` — creates table
**`employment_modules`** (module_key PK, label, status ∈ {production, partial, planned},
db_backed_required) plus view `employment_module_readiness` joining live `rules` counts.

### `SELECT * FROM employment_modules ORDER BY module_key;` (raw output — 24 rows)

```
             module_key             |                   label                    |   status   | db_backed_required |          created_at           |          updated_at           
------------------------------------+--------------------------------------------+------------+--------------------+-------------------------------+-------------------------------
 agency_workers                     | Agency worker rights                       | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.085536+00
 constructive_dismissal             | Constructive dismissal                     | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.030707+00
 discrimination                     | Discrimination                             | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:25.99501+00
 employment_contracts               | Employment contracts / written particulars | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.085536+00
 equal_pay                          | Equal pay                                  | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:25.99501+00
 fixed_term_workers                 | Fixed-term worker rights                   | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.085536+00
 flexible_working                   | Flexible working                           | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.074704+00
 health_and_safety                  | Health and safety detriment/dismissal      | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.030707+00
 holiday_pay                        | Holiday pay and annual leave               | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.074704+00
 maternity_rights                   | Maternity rights                           | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.015682+00
 national_minimum_wage              | National Minimum Wage                      | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:25.976654+00
 parental_leave                     | Parental leave                             | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.015682+00
 part_time_workers                  | Part-time worker rights                    | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.085536+00
 paternity_rights                   | Paternity rights                           | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.015682+00
 pregnancy_maternity_discrimination | Pregnancy and maternity discrimination     | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:25.99501+00
 redundancy                         | Redundancy rights and pay                  | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.05118+00
 shared_parental_leave              | Shared parental leave                      | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.015682+00
 trade_union_rights                 | Trade union rights                         | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.030707+00
 tupe                               | TUPE transfers                             | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.030707+00
 unfair_dismissal                   | Unfair dismissal                           | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:06:54.148682+00
 unpaid_wages                       | Unpaid wages / unlawful deduction          | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:06:54.148682+00
 whistleblowing                     | Whistleblowing detriment/dismissal         | partial    | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:25.99501+00
 working_time                       | Working time and rest breaks               | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.074704+00
 wrongful_dismissal                 | Wrongful dismissal / notice pay            | production | t                  | 2026-07-07 18:06:54.148682+00 | 2026-07-07 18:07:26.05118+00
(24 rows)

 count 
-------
    24
(1 row)

```

Note: DB statuses differ from the migration seed (e.g. `agency_workers` is now `production`,
`discrimination` is `partial`) — the catalog is live registry data updated after seeding
(updated_at 2026-07-07 18:07), proving topics are DB rows, not hardcoded lists. Note also
that `backend/domains/employment/modules.py` and `backend/core/classify.py` still carry
code-side module/topic structures alongside the DB registry.

---

## (c) Hardcode grep — jurisdiction/statute literals embedded in backend CODE

Scope: `backend/**/*.py`, excluding paths matching `tests?/`, `_test.py`, `test_*`.
Migrations/seed SQL (`db/migrations`) excluded as data. Raw grep output listed in full below.

### c.1 Hit counts by classification

`'EW'` / `"EW"` literals — **140 hits**:

| classification | count | typical shape |
|---|---|---|
| default  | 103 | `jurisdiction: str = "EW"` function/Pydantic defaults |
| constant | 29  | `"jurisdiction": "EW"` baked into returned dicts (employment_assessment.py x12, schemas) |
| logic    | 8   | membership tests / coercions (`brain.py:601`, `orchestrator.py:71`, `retrieve.py:60-62`, `corpus_citation_guard.py:292`, `ingestion_critic.py:28`) |

UK-statute references (`Employment Rights Act`, `ERA 1996`, `s.94/98/13/86`, `Equality Act`,
`WTR`, `NMW`) — **136 hits**:

| classification | count | typical shape |
|---|---|---|
| constant | 89 | hardcoded authority strings + legislation.gov.uk URLs in engine code (employment_assessment.py x33, domains/employment/assess_logic.py x22, classify.py x12 fallback-authority map, tools.py, models.py, deadline.py) |
| prompt   | 30 | document/letter templates with ERA sections baked in (core/documents.py x25, core/bundle.py x5) |
| logic    | 12 | citation parsing/normalisation/verification (citation_verifier.py abbreviation map, citations/extract-linker-normalize, retrieval/rrf.py, constructive_dismissal.py SQL) |
| comment  | 5  | docstrings/comments |

**Total: 276 hits.** Classification method: pattern-based bucketing verified by sampling;
per-hit labels below.

### c.2 Five most load-bearing hardcode hits

1. **backend/core/brain.py:601-602** (logic) — `if j not in ("EW", "SC", "NI"): j = "EW"`.
   Any unsupported jurisdiction (SE included) is silently coerced to England & Wales inside
   the Brain. Sweden would receive UK law unless this becomes a registry lookup + fail-closed.
2. **backend/core/orchestrator.py:70-72** (logic) — the same coercion duplicated in the
   orchestrator classify path.
3. **backend/core/retrieve.py:60-63** (logic) — `_GB_CODES`/`_JURISDICTION_CODE_MAP` hardcode
   the jurisdiction-compatibility universe in code instead of `legal_jurisdictions`; every
   retrieval query resolves through it.
4. **backend/core/classify.py:120-129** (constant) — per-module fallback authority map of
   ERA 1996 / Equality Act 2010 / WTR 1998 citations with legislation.gov.uk URLs, attached to
   assessments from code rather than rules/corpus rows.
5. **backend/core/documents.py:290-532** (prompt) — generated tribunal/letter documents embed
   ERA 1996 Part X, ss.94/98/111(2)/119/123/207B etc. directly in templates; document
   generation is UK-statute-specific in code.

(Close runners-up: backend/domains/employment/constructive_dismissal.py:60 — SQL with
`act_title ILIKE '%Employment Rights Act 1996%'` hardcoded; backend/services/lawapp-rag-service/main.py:211,297 —
corpus retrieval with no jurisdiction predicate at all.)

### c.3 Full hit list — `'EW'` literals (classification  file:line)

```
default   backend/api/login_gate_routes.py:47
default   backend/api/main.py:495
default   backend/api/main.py:553
default   backend/api/main.py:905
default   backend/api/main.py:940
default   backend/api/main.py:1322
constant  backend/api/main.py:1519
default   backend/api/main.py:3303
default   backend/api/main.py:3506
default   backend/api/main.py:3535
default   backend/api/main.py:3592
default   backend/api/main.py:3692
constant  backend/api/main.py:4326
default   backend/api/main.py:4400
default   backend/api/main.py:4412
default   backend/api/reasoning_routes.py:38
default   backend/api/sovereign_routes.py:24
default   backend/api/sovereign_routes.py:29
default   backend/api/tools_routes.py:47
default   backend/api/tools_routes.py:53
constant  backend/chatbot/authority_builder.py:41
constant  backend/chatbot/authority_builder.py:53
constant  backend/chatbot/authority_builder.py:62
default   backend/chatbot/schemas.py:17
logic     backend/core/agentic/corpus_citation_guard.py:292
logic     backend/core/agentic/ingestion_critic.py:28
constant  backend/core/agentic/schemas.py:38
default   backend/core/agents/base.py:65
default   backend/core/agents/registry.py:30
default   backend/core/agents/registry.py:83
default   backend/core/agents/registry.py:151
default   backend/core/agents/registry.py:174
default   backend/core/agents/registry.py:200
default   backend/core/agents/registry.py:239
default   backend/core/agents/registry.py:265
default   backend/core/agents/registry.py:281
default   backend/core/agents/registry.py:303
default   backend/core/agents/registry.py:340
default   backend/core/agents/swarm_agents.py:22
default   backend/core/agents/swarm_agents.py:47
default   backend/core/agents/swarm_agents.py:71
default   backend/core/agents/swarm_agents.py:91
default   backend/core/agents/swarm_agents.py:110
default   backend/core/agents/swarm_agents.py:135
default   backend/core/agents/swarm_agents.py:168
default   backend/core/brain.py:227
logic     backend/core/brain.py:228
default   backend/core/brain.py:270
default   backend/core/brain.py:291
default   backend/core/brain.py:351
default   backend/core/brain.py:364
default   backend/core/brain.py:374
default   backend/core/brain.py:520
constant  backend/core/brain.py:532
logic     backend/core/brain.py:601
constant  backend/core/brain.py:602
default   backend/core/control_plane/graph_controller.py:18
default   backend/core/control_plane/graph_controller.py:28
default   backend/core/control_plane/graph_controller.py:37
default   backend/core/control_plane/mother_controller.py:33
default   backend/core/control_plane/reasoning_router.py:28
default   backend/core/control_plane/reasoning_router.py:138
default   backend/core/control_plane/reasoning_router.py:197
constant  backend/core/employment_assessment.py:169
constant  backend/core/employment_assessment.py:218
constant  backend/core/employment_assessment.py:285
constant  backend/core/employment_assessment.py:361
constant  backend/core/employment_assessment.py:393
constant  backend/core/employment_assessment.py:465
constant  backend/core/employment_assessment.py:530
constant  backend/core/employment_assessment.py:610
constant  backend/core/employment_assessment.py:675
constant  backend/core/employment_assessment.py:732
constant  backend/core/employment_assessment.py:772
constant  backend/core/employment_assessment.py:822
default   backend/core/evaluator.py:114
default   backend/core/evaluator.py:115
constant  backend/core/feature_spec_service.py:447
constant  backend/core/feature_spec_service.py:500
default   backend/core/legal_graph.py:43
default   backend/core/legal_graph.py:77
default   backend/core/legal_graph.py:239
default   backend/core/mcp_connectors.py:130
default   backend/core/mcp_connectors.py:166
default   backend/core/mcp_connectors.py:194
default   backend/core/models.py:108
constant  backend/core/models.py:188
default   backend/core/models.py:252
default   backend/core/models.py:372
default   backend/core/models.py:508
default   backend/core/orchestrator.py:66
default   backend/core/orchestrator.py:70
logic     backend/core/orchestrator.py:71
constant  backend/core/orchestrator.py:72
default   backend/core/orchestrator.py:115
default   backend/core/orchestrator.py:166
default   backend/core/orchestrator.py:212
default   backend/core/pipeline.py:155
default   backend/core/rag/graphrag_traversal.py:42
default   backend/core/rag/graphrag_traversal.py:239
default   backend/core/rag/graphrag_traversal.py:283
default   backend/core/rag/graphrag_traversal.py:323
default   backend/core/rag/graphrag_traversal.py:412
default   backend/core/rag/graphrag_traversal.py:470
default   backend/core/rag/graphrag_traversal.py:474
default   backend/core/rag/graphrag_traversal.py:506
default   backend/core/rag/graphrag_traversal.py:531
default   backend/core/rag/graph_cache.py:36
default   backend/core/rag/graph_cache.py:56
constant  backend/core/rag/graph_engine.py:122
default   backend/core/rag/graph_engine.py:251
default   backend/core/rag/graph_engine.py:285
default   backend/core/rag/graph_rag_chain.py:17
default   backend/core/rag/graph_rag_chain.py:54
default   backend/core/rag/neo4j_traversal.py:94
default   backend/core/rag/neo4j_traversal.py:179
constant  backend/core/rag/neo4j_traversal.py:286
logic     backend/core/retrieve.py:60
logic     backend/core/retrieve.py:62
default   backend/core/retrieve.py:147
default   backend/core/retrieve.py:286
default   backend/core/retrieve.py:428
default   backend/core/semantic_cache.py:89
default   backend/core/semantic_cache.py:150
default   backend/core/sovereign/answer.py:18
default   backend/core/sovereign/extract.py:87
default   backend/core/sovereign/graph_hydrator.py:100
constant  backend/core/tools.py:51
default   backend/core/tools.py:170
default   backend/core/tools.py:224
default   backend/core/tool_registry/deadline.py:15
constant  backend/domains/shared/types.py:34
logic     backend/language_engine/ar/phrasing.py:71
default   backend/language_engine/shared/types.py:49
default   backend/services/lawapp-graph-rag-service/main.py:59
default   backend/services/lawapp-graph-rag-service/main.py:120
default   backend/services/lawapp-graph-rag-service/main.py:346
default   backend/services/lawapp-graph-rag-service/main.py:405
default   backend/services/lawapp-graph-rag-service/main.py:448
constant  backend/services/lawapp-rules-service/main.py:207
```

### c.4 Full hit list — UK-statute references (classification  file:line)

```
constant  backend/api/main.py:4338
logic     backend/core/agentic/ingestion_critic.py:32
constant  backend/core/agents/registry.py:25
constant  backend/core/agents/registry.py:119
prompt    backend/core/bundle.py:288
prompt    backend/core/bundle.py:328
prompt    backend/core/bundle.py:378
prompt    backend/core/bundle.py:456
prompt    backend/core/bundle.py:497
logic     backend/core/citations/extract.py:20
comment   backend/core/citations/extract.py:77
logic     backend/core/citations/linker.py:28
logic     backend/core/citations/normalize.py:6
logic     backend/core/citation_verifier.py:24
logic     backend/core/citation_verifier.py:38
logic     backend/core/citation_verifier.py:40
logic     backend/core/citation_verifier.py:45
constant  backend/core/classify.py:120
constant  backend/core/classify.py:121
constant  backend/core/classify.py:122
constant  backend/core/classify.py:123
constant  backend/core/classify.py:124
constant  backend/core/classify.py:125
constant  backend/core/classify.py:126
constant  backend/core/classify.py:127
constant  backend/core/classify.py:128
constant  backend/core/classify.py:129
constant  backend/core/classify.py:267
constant  backend/core/classify.py:437
prompt    backend/core/documents.py:210
prompt    backend/core/documents.py:263
prompt    backend/core/documents.py:290
prompt    backend/core/documents.py:318
prompt    backend/core/documents.py:321
prompt    backend/core/documents.py:322
prompt    backend/core/documents.py:333
prompt    backend/core/documents.py:349
prompt    backend/core/documents.py:351
prompt    backend/core/documents.py:352
prompt    backend/core/documents.py:401
prompt    backend/core/documents.py:416
prompt    backend/core/documents.py:435
prompt    backend/core/documents.py:438
prompt    backend/core/documents.py:443
prompt    backend/core/documents.py:462
prompt    backend/core/documents.py:503
prompt    backend/core/documents.py:532
prompt    backend/core/documents.py:562
prompt    backend/core/documents.py:598
prompt    backend/core/documents.py:614
prompt    backend/core/documents.py:623
prompt    backend/core/documents.py:666
prompt    backend/core/documents.py:709
prompt    backend/core/documents.py:745
constant  backend/core/employment_assessment.py:139
constant  backend/core/employment_assessment.py:155
constant  backend/core/employment_assessment.py:156
constant  backend/core/employment_assessment.py:182
constant  backend/core/employment_assessment.py:183
constant  backend/core/employment_assessment.py:184
constant  backend/core/employment_assessment.py:185
constant  backend/core/employment_assessment.py:226
constant  backend/core/employment_assessment.py:227
constant  backend/core/employment_assessment.py:309
constant  backend/core/employment_assessment.py:355
constant  backend/core/employment_assessment.py:372
constant  backend/core/employment_assessment.py:373
constant  backend/core/employment_assessment.py:409
constant  backend/core/employment_assessment.py:410
constant  backend/core/employment_assessment.py:411
constant  backend/core/employment_assessment.py:412
constant  backend/core/employment_assessment.py:413
constant  backend/core/employment_assessment.py:480
constant  backend/core/employment_assessment.py:481
constant  backend/core/employment_assessment.py:484
constant  backend/core/employment_assessment.py:485
constant  backend/core/employment_assessment.py:486
constant  backend/core/employment_assessment.py:487
constant  backend/core/employment_assessment.py:548
constant  backend/core/employment_assessment.py:549
constant  backend/core/employment_assessment.py:550
constant  backend/core/employment_assessment.py:551
constant  backend/core/employment_assessment.py:627
constant  backend/core/employment_assessment.py:628
constant  backend/core/employment_assessment.py:629
constant  backend/core/employment_assessment.py:688
constant  backend/core/employment_assessment.py:689
constant  backend/core/mcp_connectors.py:13
constant  backend/core/models.py:90
constant  backend/core/models.py:257
constant  backend/core/models.py:381
constant  backend/core/models.py:515
constant  backend/core/pipeline.py:431
constant  backend/core/retrieval/rrf.py:22
comment   backend/core/retrieval/rrf.py:55
comment   backend/core/retrieval/rrf.py:56
constant  backend/core/tools.py:231
comment   backend/core/tools.py:251
constant  backend/core/tools.py:257
constant  backend/core/tools.py:273
constant  backend/domains/employment/assess_logic.py:51
constant  backend/domains/employment/assess_logic.py:54
constant  backend/domains/employment/assess_logic.py:58
constant  backend/domains/employment/assess_logic.py:64
constant  backend/domains/employment/assess_logic.py:116
constant  backend/domains/employment/assess_logic.py:117
comment   backend/domains/employment/assess_logic.py:163
constant  backend/domains/employment/assess_logic.py:235
constant  backend/domains/employment/assess_logic.py:243
constant  backend/domains/employment/assess_logic.py:249
constant  backend/domains/employment/assess_logic.py:292
constant  backend/domains/employment/assess_logic.py:298
constant  backend/domains/employment/assess_logic.py:304
constant  backend/domains/employment/assess_logic.py:393
constant  backend/domains/employment/assess_logic.py:416
constant  backend/domains/employment/assess_logic.py:422
constant  backend/domains/employment/assess_logic.py:431
constant  backend/domains/employment/assess_logic.py:461
constant  backend/domains/employment/assess_logic.py:463
constant  backend/domains/employment/assess_logic.py:464
constant  backend/domains/employment/assess_logic.py:505
constant  backend/domains/employment/assess_logic.py:546
constant  backend/domains/employment/checklists/tribunal_elements.py:10
constant  backend/domains/employment/checklists/tribunal_elements.py:11
logic     backend/domains/employment/constructive_dismissal.py:12
logic     backend/domains/employment/constructive_dismissal.py:46
logic     backend/domains/employment/constructive_dismissal.py:61
logic     backend/domains/employment/constructive_dismissal.py:106
constant  backend/domains/employment/deadline.py:8
constant  backend/domains/employment/deadline.py:59
constant  backend/domains/employment/deadline.py:76
constant  backend/domains/employment/deadline.py:99
constant  backend/domains/employment/modules.py:39
constant  backend/domains/employment/timeline.py:186
constant  backend/domains/employment/timeline.py:201
constant  backend/services/lawapp-rules-service/main.py:209
```

---

## Sweden-readiness conclusion (evidence only)

- **Schema: READY.** Jurisdiction is a first-class, FK-enforced column on rules,
  legislation, and corpus_chunks; the jurisdiction list itself is a table
  (`legal_jurisdictions`), and topics are registry rows (`employment_modules`, 24 rows).
- **Query paths: MOSTLY parameterised**, but 6+ sites query corpus/legislation with no
  jurisdiction predicate (rag-service FTS/vector, feature_spec_service, citations/linker,
  citation_verifier, constructive_dismissal) — safe only while the corpus is single-regime.
- **Engine code: NOT READY.** 276 UK-specific literals in non-test backend code: `"EW"` as
  the universal default (103), silent EW coercion at both routing chokepoints, UK statutes in
  constants (89), document templates (30), and citation-parsing logic (12). A Swedish module
  requires: registry-driven jurisdiction validation (fail closed, no coercion), moving the
  classify.py fallback-authority map and employment_assessment.py citation constants into
  rules/corpus rows, jurisdiction-parameterised document templates, and jurisdiction
  predicates on the unfiltered query sites.

No fixes were applied. No data was changed. Evidence gathered read-only against the running
`db` container (queries executed with the container's own credentials; no secrets printed).
