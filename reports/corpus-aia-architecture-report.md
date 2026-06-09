# Corpus Ingestion AIA — Architecture Report

**Date:** 2026-06-05  **Status:** DONE AND PROVEN (employment_uk)

## What it is
The **Corpus Ingestion AIA** (`backend/core/agents/corpus_ingestion_aia.py`) builds and
maintains the local legal DB. It is **not** a user-facing reasoning agent — Workflow C
reasons *only* from the DB this AIA populates. It is the only component allowed to
fetch / parse / store legal sources.

## Config-driven (domains plug in, no core rewrite)
- Source of truth = the **domain pack** `domains/<domain>/`, loaded by
  `ingestion/domain_loader.py` (`load_domain_pack`, `check_pack`).
- Required manifests (fail-closed if any missing): `domain_config.json`,
  `sources.yaml`, `rules_manifest.yaml`, `citation_policy.yaml`, `licence_policy.yaml`,
  `workflows.yaml`.
- Ingestion pipeline registry: `_DOMAIN_PIPELINES["employment_uk"]` →
  legislation → acas → govuk → embeddings.

## Gates (all fail-closed)
| Function | Gate |
|---|---|
| `validate_domain_pack(domain)` | pack + all manifests present; sources/rules declared; FCL licence-consistent |
| `register_legal_sources(domain)` | upsert pack's authorised sources into `legal_sources` |
| `validate_corpus(conn)` | row hygiene — reject rows missing source_url/content_hash/last_verified_at/section_ref/authority_ref; reject case_law without FCL flag |
| `validate_dataset(domain)` | every declared section present+cited+dated; every required rule present+cited+dated; registry populated; FCL fail-closed; + row hygiene |
| `fcl_bulk_allowed()` | `FCL_BULK_LICENCE_GRANTED=true` required for any case_law |

## Acceptance behaviour
The AIA / proof **FAILS** if: domain pack missing, any manifest missing, a required
source not declared, a declared section absent from the DB, a rule uncited/undated,
the `legal_sources` registry empty, or case_law populated without the licence flag.

## Proof
`scripts/prove_uk_legal_dataset.sh` exercises every gate above and exits non-zero on
any failure. Currently **PASSED**.

## Data flow
```
domain pack (YAML/JSON)
   |  domain_loader.load_domain_pack()
   v
Corpus Ingestion AIA -- legislation.gov.uk (CLML XML) --+
                     -- ACAS (HTML) -------------------+--> Postgres (cited, hashed, dated)
                     -- GOV.UK (HTML) -----------------+--> embeddings (bge-small, 384d)
                     -- Find Case Law -- FAIL-CLOSED ---+    legal_sources / corpus_ingestion_runs
   |  validate_dataset() gate
   v
Workflow C reasons ONLY from DB rows (citations must resolve to a row)
```

## Gaps / next
- Persist a `corpus_ingestion_runs` row per *ingestor* (today the proof records one
  `full` run; per-source rows are the next refinement).
- Wire ACAS/GOV.UK ingestors to also consult the pack's `guidance:` manifest for URLs
  (legislation already pack-driven).
