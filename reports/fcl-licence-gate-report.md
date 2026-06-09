# Find Case Law (FCL) Licence Gate Report

**Date:** 2026-06-05  **Status:** BLOCKED BY OWNER / LICENCE-GATED (by design, fail-closed)

## Summary
Find Case Law bulk ingestion and computational analysis are **disabled by default**
and **fail closed**. No case-law rows exist; none are faked.

| Item | State |
|---|---|
| `case_law_documents` rows | **0** |
| Gate env flag | `FCL_BULK_LICENCE_GRANTED=false` (default) |
| `legal_sources` status | `find_case_law = BLOCKED_BY_OWNER` |
| Licence type | Open Justice Licence (bulk/computational analysis need extra National Archives permission) |
| Fake/placeholder cases | **none** (forbidden) |

## Enforcement points
1. **Domain pack** `domains/employment_uk/licence_policy.yaml`:
   `find_case_law` → `bulk_allowed:false`, `computational_analysis_allowed:false`,
   `requires_owner_approval:true`, `gate_env_var:FCL_BULK_LICENCE_GRANTED`,
   `licence_status:BLOCKED_BY_OWNER`.
2. **AIA** `corpus_ingestion_aia.fcl_bulk_allowed()` returns `true` only when
   `FCL_BULK_LICENCE_GRANTED=true`. `validate_corpus`/`validate_dataset` FAIL if
   `case_law_documents` is non-empty without the flag.
3. **Registry** `legal_sources` records `licence_status=BLOCKED_BY_OWNER` and the
   dataset proof asserts it.
4. **Proof** `scripts/prove_uk_legal_dataset.sh` §7: PASS only if case_law is empty
   (or the licence flag is genuinely set).

## Prepared but NOT run (awaiting owner licence)
- EAT ingestion pipeline
- Employment Tribunal ingestion pipeline
- `content_hash` comparison + change-detection refresh for case law

These remain code-only and dormant behind the flag. **Do not enable** until
computational-analysis permission is granted and recorded in `legal_sources`.

## To enable (owner action only)
1. Obtain National Archives computational-analysis permission for the intended use.
2. Record the licence basis in `legal_sources` (status → GRANTED, set licence notes).
3. Set `FCL_BULK_LICENCE_GRANTED=true` in the environment.
4. Re-run ingestion; the gates will then permit licence-safe case-law rows.

## Status line
**BLOCKED BY OWNER** — fail-closed, no fake data, pipeline prepared.
