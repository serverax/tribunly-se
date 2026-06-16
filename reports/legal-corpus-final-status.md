# lawapp  -  Legal Data Spine Final Status

Project: **lawapp**  -  UK employment-law AI assistant. First claim: ordinary unfair
dismissal. Default jurisdiction: GB. NI fails closed.

Note on vocabulary: this order's §12 listed `verified_live`; the project's CANONICAL
verification_status set is `verified, case_law_verified, prospective, unverified`
(established earlier; migration 036). The proofs treat `verified` as the live status.
No `verified_live` rows exist.

## Tables (case_law added this pass)
legal_jurisdictions, legal_sources, corpus_ingestion_runs, legislation, case_law,
acas_guidance, rules, legal_taxonomy, legal_chunk_labels, corpus_chunks,
legal_retrieval_audit, legal_assessments, deadline_calculation_audit, users, cases,
documents, referrals  -  all present (migration-created).

## Row counts (live DB)
- rules = 34 (verified 29, case_law_verified 2, prospective 3; verified_live 0)
- legislation = 194
- acas_guidance = 36
- corpus_chunks = 247
- legal_sources = 9
- legal_jurisdictions = 5 (GB, EW, S, NI, UK)
- case_law = 0  (BLOCKED  -  see below)

## Views / matview
- source_freshness ✓
- corpus_quality_report ✓
- mv_current_employment_legal_chunks ✓ (excludes NI / missing source_url / missing chunk_hash)

## BLOCKED (recorded, not faked)
- **Find Case Law bulk ingestion**  -  application_status != granted. `case_law` table
  created EMPTY (migration 040); blocker recorded in `corpus_ingestion_runs`
  (source_id='find_case_law', status='blocked'). No bulk crawl performed. No fake rows.
- **Northern Ireland**  -  no verified NI rules; NI fails closed (jurisdiction_supported('NI')=False).

## Proof scripts  -  ALL PASS (exit 0)
- prove_legal_data_spine.sh ......... PASS
- prove_jurisdiction_model.sh ....... PASS
- prove_rules_integrity.sh .......... PASS
- prove_corpus_quality.sh ........... PASS
- prove_legal_db_performance.sh ..... PASS
- prove_ingestion_runs.sh ........... PASS
- prove_retrieval_pipeline.sh ....... PASS

## Required tests  -  10/10 files present, 46 passed
`pytest test_jurisdiction_fail_closed test_rules_integrity
 test_retrieval_jurisdiction_and_provenance test_deadline_rules_audit
 test_corpus_quality_views test_legal_db_indexes test_ingestion_run_tracking
 test_legal_sources_integrity test_materialized_current_chunks
 test_no_hardcoded_legal_values` → **46 passed**.

## Source fix this pass (no hardcoded legal values)
- `backend/domains/employment/assess_logic.py` hardcoded `123543` (compensatory cap)
  and `751` (week's-pay cap) as fallbacks. REMOVED  -  now fail-closed (raises if the
  cap rule is missing). Proven by `test_no_hardcoded_legal_values` (was FAIL, now PASS).

## Regression
- assess pipeline + documents + orchestrator after fail-closed change: **87 passed**.

## Final status: PASS (with recorded BLOCKERS)
- Spine, jurisdiction model, rules integrity, corpus quality, performance, ingestion
  tracking, retrieval pipeline, jurisdiction fail-closed, no-hardcoded-values: **PASS**.
- case_law content + NI rules: **BLOCKED** (licence / not-ingested), recorded with evidence.
