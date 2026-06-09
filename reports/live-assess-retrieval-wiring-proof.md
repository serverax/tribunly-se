# Live /assess Retrieval Wiring — Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Command:** `bash scripts/prove_live_assess_retrieval_wiring.sh`
- **Final status:** **PASS**

The LIVE HTTP `/assess` endpoint (not a stub, not a proof-only script) is now
DB-first, retrieval-first, jurisdiction-filtered, cited, and audited.

## What was wired (code)
- `backend/core/retrieve.py`:
  - `juris_codes()` + `jurisdiction_supported()` — map user jurisdiction → controlled
    `jurisdiction_code` set; NI has no verified rules → unsupported.
  - `retrieve_rules`, `retrieve_keyword`, `retrieve_semantic` now filter
    **`jurisdiction_code = ANY(...)`** (legacy `jurisdiction='EW'` filter replaced).
  - `_write_retrieval_audit` now also writes **`legal_retrieval_audit`** (query_text,
    query_hash, domain, claim_type, **jurisdiction_code**, retrieved_bundle, exact_rules,
    grounding_score, embedding_model) for every retrieval.
- `backend/core/pipeline.py`:
  - Jurisdiction gate **before** retrieval: unsupported jurisdiction (NI) returns
    `not_supported`, `jurisdiction_supported=false`, `insufficient_grounding=true`,
    `recommended_next_step=human_review` — never reuses GB law.
  - `_write_deadline_audit` writes **`deadline_calculation_audit`** (edt, base/final
    limitation dates, EC dates, **rules_used**, jurisdiction_code, calculated_by=server)
    proving the deadline came from the `rules` table, not the model.
- Backend image rebuilt; `docker-compose.override.yml` aligns the dev DB password.

## Live HTTP evidence
**GB** (`POST /assess`, realistic unfair-dismissal facts, `use_model=false`):
- status=`ok`, has_viable_claim=`no`, **8 citations** (all with source_url resolving to
  legislation.gov.uk / ACAS), grounding_score=`1.0`, insufficient_grounding=`false`.
- deadline `2024-07-31`, source=`rules` (deterministic, from the rules table).
- jurisdiction=`EW`.

**NI** (`POST /assess`, jurisdiction=NI):
- status=`not_supported`, jurisdiction_supported=`false`, insufficient_grounding=`true`,
  **0 citations** — fails closed, no GB law reused.

**Audit writes** (proven to increment per request):
- `legal_retrieval_audit` grew (8 → 9), GB rows present.
- `deadline_calculation_audit` grew (6 → 7), `rules_used` contains `time_limit_months`.

## Acceptance (all met)
backend starts ✓ · DB connects ✓ · /assess accepts realistic facts ✓ · structured
assessment ✓ · citations ✓ · deadline from rules ✓ · jurisdiction_code present ✓ ·
legal_retrieval_audit written ✓ · NI fails closed ✓ · no uncited assertion ✓.

## Regression
`101 passed, 3 skipped` across jurisdiction/rules/indexes/retrieve/pipeline/deadline/
de-identification/retrieval test suites — no regression from the wiring changes.
