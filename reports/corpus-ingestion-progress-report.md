# Corpus Ingestion Progress Report

**Date:** 2026-06-05  **Domain:** employment_uk
**Proof:** `scripts/prove_uk_legal_dataset.sh` → PASSED (exit 0)

Chunked, resumable, idempotent ingestion via
`scripts/ingest_uk_legal_dataset_chunked.sh`. Each source is a batch; every batch
writes a checkpoint to `corpus_ingestion_runs` (status, rows_ingested, failures).

## Batch status (latest run)

| Batch (source_id) | Module | Status | Idempotent re-run delta |
|---|---|---|---|
| legislation | `ingestion.legislation.ingest` | passed | 0 |
| limits_orders (uksi) | `ingestion.rules.seed_limits_orders` | passed | 0 |
| acas | `ingestion.acas.ingest` | passed | 0 |
| govuk | `ingestion.govuk.ingest` | passed | 0 |
| embeddings | `ingestion.embeddings.embedder` | passed | 0 |

All batches re-run with delta 0 → **idempotent** (no duplicate rows). Duplicate
prevention enforced by UNIQUE constraints: legislation `(source_url,chunk_index)`,
acas_guidance `(source_url,chunk_index)` (migration 030), official_guidance `source_url`.

## Current row counts

| Table | Rows | Distinct docs/sections | Embedded | content_hash |
|---|---|---|---|---|
| legislation (ukpga) | 188 | ERA/ETA/TULRCA/ERA2025 | — | 188/188 |
| legislation (uksi Increase-of-Limits) | 6 | 6 Orders | — | 6/6 |
| legislation total | 194 | 53 distinct section_refs | 194/194 | 194/194 |
| acas_guidance | 36 | 9 documents | 36/36 | 36/36 |
| official_guidance (GOV.UK) | 17 | 17 documents | 17/17 | 17/17 |
| rules | 32 | 19 tied to UKSI Orders | — | — |
| legal_sources | 4 | — | — | — |
| case_law_documents | 0 | — (BLOCKED BY OWNER) | — | — |

## Rate limiting / safety
- legislation.gov.uk: ~1 req/s (client throttle), no API key, `/data.xml`.
- ACAS / GOV.UK: bounded URL/path lists, single fetch each, thin/404 pages skipped.
- 404 sections (e.g. `/prospective` variants of s.108/111/124; repealed s.127) are
  skipped and documented — never faked.
- One source failing marks only that batch FAILED AND NEEDS FIX; other batches apply.

## Resume
- `bash scripts/ingest_uk_legal_dataset_chunked.sh --only <source>` re-runs one batch.
- Re-running is safe (upserts dedupe). Checkpoints in `corpus_ingestion_runs`
  (12 rows recorded) show what ran and when.

## Source strategy (confirmed)
- **legislation** ← legislation.gov.uk API (statutes + UKSI + prospective). Spine. [OK]
- **acas_guidance** ← ACAS static official pages. [OK]
- **official_guidance** ← GOV.UK content API. [OK]
- **rules** ← derived from legislation + Increase-of-Limits UKSI, cited URLs. [OK]
- **case_law** ← Find Case Law API (+ GOV.UK ET pages fallback) — BLOCKED BY OWNER. [GATED]
- **reform watch** ← UK Parliament Bills API + prospective legislation — monitoring
  only, NOT legal authority (`bills` table present, 0 rows; ERA 2025 prospective rows
  marked prospective). [MONITOR-ONLY]
