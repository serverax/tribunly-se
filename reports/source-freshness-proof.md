# Source Freshness  -  Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Proof script:** `scripts/prove_source_freshness.sh`

## Command
```
docker compose exec -T db psql -U lawapp -d lawapp -c \
"SELECT source_name, source_type, jurisdiction_code, rows_count, stale_rows_count, last_ingestion_status FROM source_freshness ORDER BY source_name;"
```

## Exact output
```
    source_name    | source_type | jurisdiction_code | rows_count | stale_rows_count | last_ingestion_status
-------------------+-------------+-------------------+------------+------------------+-----------------------
 acas_guidance     | acas        | GB                |         36 |                0 | passed
 legislation       | legislation | GB                |        194 |                0 | passed
 official_guidance | govuk       | GB                |         17 |                0 | passed
 rules             | rules       | GB                |         34 |                0 | passed
```

## Interpretation
- Every active legal source has rows, a `jurisdiction_code`, and **0 stale rows** (none
  older than the freshness window, default 120 days).
- `last_ingestion_status = passed` for every source (per-source checkpoints in
  `corpus_ingestion_runs`).
- `case_law` does not appear because it is empty (Find Case Law OWNER_BLOCKED)  -  by
  design, not hidden: see `reports/find-case-law-blocker-proof.md`.

## Provenance completeness (corpus_chunks = 247, all GB)
0 rows missing `source_url`, `content_hash`/`chunk_hash`, `jurisdiction_code`, or
`embedding`. Verified by `scripts/prove_corpus_quality.sh`.

**Status: source freshness PROVEN (rows present, jurisdiction-coded, fresh, per-source
ingestion status recorded).**
