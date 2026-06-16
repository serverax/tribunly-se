# Source Freshness Report

**Date:** 2026-06-05  **Domain:** employment_uk  **Status:** DONE AND PROVEN

Freshness is tracked per source table via `source_freshness` (columns: `source`,
`rows`, `oldest_verified`) and enforced by `scripts/prove_uk_legal_dataset.sh`
(fails if any legislation row is older than `CORPUS_FRESH_DAYS`, default 120).
Every row also carries `content_hash` (SHA-256 of body_text) for change detection.

## Current freshness (verified 2026-06-04/05)

| source | rows | oldest_verified |
|---|---|---|
| legislation | 188 | 2026-06-04 |
| acas_guidance | 12 | 2026-06-04 |
| official_guidance (GOV.UK) | 7 | 2026-06-04 |
| rules | 19 | 2026-06-04 |
| bills | 0 |  -  |
| case_law | 0 |  -  (licence-gated) |

- **Staleness gate:** 0 rows older than 120 days → PASS.
- **Hash coverage:** legislation 188/188; ACAS 12/12; GOV.UK 7/7 (`content_hash` set).
- **Change detection:** re-ingestion recomputes `content_hash` and updates
  `last_verified_at = now()`; a changed source produces a different hash, surfacing
  the delta. Ingestor writers (`upsert_legislation`) now set `content_hash` at write
  time so freshly-ingested rows are covered without a backfill step.

## Mechanism
- Writers stamp `last_verified_at = now()` on every insert/update.
- `source_freshness` aggregates per table for at-a-glance reporting
  (`ingestion/freshness/report.py`).
- A `source-freshness-cronjob` manifest exists under infra for scheduled refresh
  (not run in local dev).

## Gaps / next
- Add a scheduled refresh job (cron) in the running environment to keep
  `oldest_verified` rolling; today refresh is manual via the ingestors.
- Per-source `corpus_ingestion_runs` rows to chart freshness over time.
