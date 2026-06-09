# Legal Data Spine — Proof Report

- **Timestamp:** 2026-06-05
- **Git branch:** main
- **Git commit:** a0968b0
- **Command:** `bash scripts/prove_legal_data_spine.sh`
- **DB target:** postgres://lawapp:***@db:5432/lawapp
- **Final status:** **PASS**

## What was built (migrations 031–035)
- `legal_jurisdictions` (5 rows: GB/EW/S/NI/UK), `legal_taxonomy` (20), `legal_chunk_labels`.
- `legal_sources` extended + 9 sources seeded (7 required + GOV.UK CTP + NI placeholder).
- `corpus_ingestion_runs` extended (run_key, ingestion_mode, records_*, blocker_reason, config/proof_json).
- `jurisdiction_code` + `legal_system` + `applies_to_*` on legislation/acas_guidance/official_guidance/rules/case_law_documents (FK → legal_jurisdictions).
- `corpus_chunks` unified retrieval table (247 rows, deterministic `chunk_hash`, vector(384)).
- `legal_retrieval_audit`, `legal_assessments`, `deadline_calculation_audit` (jurisdiction-aware).
- Views: `source_freshness`, `corpus_quality_report`; materialized view `mv_current_employment_legal_chunks`.
- Performance: HNSW vector indexes, full-text GIN, trigram, rules composite/partial, BRIN, JSONB GIN.

## Row counts
| object | count |
|---|---|
| legislation (incl. 6 UKSI) | 194 |
| acas_guidance | 36 |
| official_guidance (GOV.UK) | 17 |
| rules | 34 |
| corpus_chunks | 247 |
| legal_sources | 9 |
| legal_jurisdictions | 5 |
| legal_taxonomy | 20 |
| mv_current_employment_legal_chunks | 247 |

## Proof output (key lines)
```
LEGAL DATA SPINE PROOF: PASS
```
All required tables (18), views (2), materialized view (1), extensions (vector/pgcrypto/pg_trgm),
vector/full-text/trigram indexes, and all 10 required GB unfair-dismissal rule keys present;
`source_freshness` and `corpus_quality_report` execute.

## Note on embedding dimension
Embeddings are **vector(384)** (local `BAAI/bge-small-en-v1.5`), not the spec's
vector(1536) which assumed OpenAI. lawapp runs the local model — 384 is correct and
consistent across all tables. Documented, not a defect.

## Blocked / partial
- Find Case Law: BLOCKED BY OWNER (application_status=pending); case_law empty, fail-closed.
- Northern Ireland: NOT IMPLEMENTED (source placeholder recorded); NI fails closed.
