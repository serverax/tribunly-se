# Legal Jurisdiction Model  -  Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Command:** `bash scripts/prove_jurisdiction_model.sh`
- **Final status:** **PASS**

## Model
`legal_jurisdictions` (controlled table) seeds GB, EW, S, NI, UK. Every legal row,
rule, chunk, retrieval audit and deadline audit carries `jurisdiction_code` (FK).
The UK is **not** treated as one flat jurisdiction.

## Proven (checks A–R)
- legal_jurisdictions exists; GB/EW/S/NI/UK rows present and fully specified.
- jurisdiction_code present on legislation, case_law_documents, acas_guidance, rules,
  corpus_chunks, legal_retrieval_audit, legal_assessments, deadline_calculation_audit.
- **0 NULL** jurisdiction_code in legislation/acas_guidance/rules/corpus_chunks.
- **0 NI rules** (NI unsupported → fail-closed).
- GB unfair-dismissal rules retrievable; GB query returns **0** NI rows; GB chunk
  retrieval returns **0** NI chunks.
- NI unfair dismissal has **0** verified rules → assessment must return unsupported /
  insufficient_grounding / human_review.
- source_freshness and corpus_quality_report both expose `jurisdiction_code`.

## Row counts by jurisdiction_code
| table | GB | NI |
|---|---|---|
| rules | 34 | 0 |
| legislation | 194 | 0 |
| corpus_chunks | 247 | 0 |

## NI fail-closed evidence
- `legal_sources.ni_employment_law` recorded (application_status=unknown, not implemented).
- `mv_current_employment_legal_chunks` excludes NI (proven: 0 NI rows).
- Any NI unfair-dismissal retrieval bundle is empty → governance must fail closed.

## Backend wiring status
- Data layer + retrieval-contract proof: **DONE AND PROVEN** (`scripts/prove_retrieval_pipeline.sh`).
- Application-code enforcement of jurisdiction filter in the live `/assess` path:
  **IMPLEMENTED BUT PARTIAL**  -  the DB enforces it (FK + NI empty); wiring the explicit
  jurisdiction_code filter into every backend retrieval call is the next code step.
