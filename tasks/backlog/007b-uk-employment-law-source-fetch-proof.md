# 007b  -  UK Employment-Law Source Fetch Proof

**Owner agent:** uk-employment-law-scraper-agent
**Stage:** 1 of legal-data chain (execution) · **State:** backlog · **Depends on:** 007a

## Goal
Execute the 007a plan: fetch real sources and PROVE each fetch. No parsing, no rules, no corpus_chunks.

## Required proof (per source)
1. Exact source URL.
2. Exact fetch command/script.
3. HTTP status.
4. Content length (bytes).
5. Content hash (sha256).
6. Raw storage location (path / `raw_source_records` id).
7. Sample raw content excerpt.
8. `fetched_at` (ISO-8601 UTC).
9. Licence/access note.

## Deliverables
- Raw files on disk + `raw_source_records` rows.
- Source manifest (machine-readable) + fetch logs.

## Acceptance
Every fetched source has all 9 proofs; manifest complete; licence posture honoured (Find Case Law single/sample only unless licence documented). Hands raw manifest to 007c.

## Hard rules
No fake/placeholder source bytes. No invented citations. No claim of ingestion completeness on fetch success.
