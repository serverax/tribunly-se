# Ingestion Runs — Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Command:** `bash scripts/prove_ingestion_runs.sh`
- **Final status:** **PASS**

## Tracking
`corpus_ingestion_runs` carries run_kind, status, records_inserted, records_failed,
blocker_reason, ingestion_mode, chunks_created, embeddings_created, config_json, proof_json.
Per-source checkpoints recorded for legislation, limits_orders, acas, govuk, embeddings
(via `scripts/ingest_uk_legal_dataset_chunked.sh`). Re-runs are idempotent (delta 0).

## Fail-closed
- No partial/blocked run lacks blocker_reason.
- Find Case Law: application_status=pending → **no** bulk ingestion run with rows.
  case_law_documents stays empty (recorded as data, not an excuse).

## Recorded blockers (data, not stop)
- find_case_law: BLOCKED BY OWNER (computational-analysis application pending).
- ni_employment_law: NOT IMPLEMENTED (no NI source ingested; NI fails closed).
- govuk_et_decisions / govuk_eat_decisions: restricted (fallback only; FCL XML preferred).
