# Corpus Quality  -  Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Command:** `bash scripts/prove_corpus_quality.sh`
- **Final status:** **PASS**

## Provenance completeness
- **0** rows missing source_url (legislation, acas_guidance, official_guidance, corpus_chunks).
- **0** rows missing jurisdiction_code (all legal tables).
- **0** corpus_chunks missing chunk_hash.
- **0** corpus_chunks missing embedding (247/247 embedded, model `bge-small-en-v1.5`).
- **0** duplicate chunk_hash (idempotent ingestion).
- **0** active chunks with non-open licence.
- **0** stale rows (>120 days).

## corpus_quality_report (grouped by source_type / jurisdiction_code)
| source_type | jurisdiction | total_chunks | with_embedding | without_source_url | avg_quality | dup_hash |
|---|---|---|---|---|---|---|
| primary_legislation | GB | 188 | 188 | 0 | 1.000 | 0 |
| statutory_instrument | GB | 6 | 6 | 0 | 1.000 | 0 |
| official_guidance | GB | 53 | 53 | 0 | 1.000 | 0 |

(247 chunks total across legislation + UKSI + ACAS + GOV.UK.)

## Required sources present in legal_sources
legislation_gov_uk, find_case_law, acas, govuk_et_decisions, govuk_eat_decisions,
parliament_bills, govuk_courts_tribunals_publishing (+ ni_employment_law placeholder).

## Find Case Law
application_status = **pending**; case_law_documents = **0** rows → no illegal bulk ingestion.
