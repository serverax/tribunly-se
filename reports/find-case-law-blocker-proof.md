# Find Case Law  -  Blocker Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Command:** `bash scripts/prove_case_law_blocker_or_ingestion.sh`
- **Final status:** **PASS (BLOCKED BY OWNER / LICENCE)**

## Module  -  fully built, fail-closed
`ingestion/sources/find_case_law.py` implements the complete pipeline, dormant
behind the licence gate:
- `bulk_licence_granted()`  -  requires BOTH `FCL_BULK_LICENCE_GRANTED=true` AND
  `legal_sources.find_case_law.application_status='granted'`.
- `atom_discover()`  -  Atom feed discovery.
- `fetch_document_xml()`  -  per-document LegalDocML/Akoma Ntoso fetch.
- `parse_judgment()`  -  neutral citation / case name / court / body / content_hash.
- `changed_since()`  -  content_hash change detection vs `case_law_documents`.
- `_get_with_backoff()`  -  polite throttle (1 req/s) + exponential backoff on 429/5xx, retries.
- `_record_run()`  -  checkpoint into `corpus_ingestion_runs` (status, blocker_reason, proof_json).
- `fetch_single()`  -  licence-safe single-document spot check.

## Proven behaviour (current, licence NOT granted)
- `python -m ingestion.sources.find_case_law` → `{"status":"blocked", ...}`.
- `case_law_documents` = **0** rows (no fake/placeholder cases).
- `corpus_ingestion_runs` has a `find_case_law` row, `status='blocked'`, with a
  populated `blocker_reason` (computational-analysis licence required).
- `legal_sources.find_case_law.application_status='pending'`,
  `bulk_ingestion_allowed=false`, `licence_status='application_required'`.

## To enable (owner action only)
1. Obtain National Archives computational-analysis permission.
2. `UPDATE legal_sources SET application_status='granted' WHERE source_id='find_case_law';`
3. `export FCL_BULK_LICENCE_GRANTED=true` and run the module  -  it will then discover,
   fetch, parse, change-detect and persist licence-safe judgments.

## Status line
**BLOCKED BY OWNER / LICENCE**  -  pipeline complete, fail-closed, zero fake rows.
