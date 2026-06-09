# Employment-Law Corpus Ingestion Report

**Date:** 2026-06-05  **Domain:** employment_uk  **Status:** DONE AND PROVEN
**Proof:** `scripts/prove_employment_law_corpus.sh` (now chains
`scripts/prove_uk_legal_dataset.sh` first) → **PASSED (exit 0)**

## Ingestion method
- **Legislation:** legislation.gov.uk CLML XML, rate-limited (1 req/s), parsed by
  `ingestion/legislation/clml_parser.py`, stored via `upsert_legislation` (now writes
  `content_hash` + full provenance). Targets are **pack-driven** from
  `domains/employment_uk/sources.yaml` (`ingestion/domain_loader.py`).
- **ACAS / GOV.UK:** official HTML guidance via `ingestion/acas` / `ingestion/govuk`.
- **Embeddings:** `BAAI/bge-small-en-v1.5` (384-dim, local, no external key).
- **Find Case Law:** prepared, **fail-closed** (no rows). See `fcl-licence-gate-report.md`.

## Row counts
| Table | Rows | Embedded | Provenance complete | content_hash |
|---|---|---|---|---|
| legislation | 188 | 188/188 | yes (0 missing) | 188/188 |
| acas_guidance | 12 | yes | yes (0 missing) | 12/12 |
| official_guidance (GOV.UK) | 7 | yes | yes (0 missing) | 7/7 |
| rules | 19 | n/a | yes (full field set) | n/a |
| legal_sources | 4 | n/a | n/a | n/a |
| case_law_documents | 0 | n/a | n/a | n/a (licence-gated) |

## Sections present (52 distinct refs)
ERA 1996: 1, 13, 23, 43A-43L (whistleblowing), 47B, 94, 95, 97, 98, 99, 100, 103A,
104, 108, 111, 112, 113, 114, 115, 118, 119, 120, 122, 123, 124, 126, 207B, 221-229.
ETA 1996: 18A. TULRCA 1992: 207A, 156. ERA 2025: 25, 152, 159 (prospective).

**Missing / excluded:** ERA 1996 **s.127** (repealed 1999 — would 404, intentionally
not ingested).

## ACAS / GOV.UK guidance present
- ACAS: Code of Practice on Disciplinary and Grievance Procedures (12 chunks, cited).
- GOV.UK: Dismissing staff; Making staff redundant; Redundancy: your rights;
  Calculate statutory redundancy pay; Make a claim to an employment tribunal;
  Holiday entitlement; Pay & work rights helpline (7 chunks, cited).

## Rules present (cited + effective-dated)
unfair_dismissal: time_limit_months, qualifying_period, weeks_pay_cap_amount,
compensatory_cap_amount, compensatory_cap_weeks_pay, basic_award_formula,
basic_award_min_automatic, early_conciliation_required, ec_max_duration_weeks.
unlawful_deduction_wages: qualifying_period_years, remedy_basis, time_limit_months,
worker_status, series_deductions_note.

## Citation resolution proof
Hybrid RAG returns grounded results and cites **ERA 1996 s.98** which resolves to a
real `legislation` row. `insufficient_grounding=false`.

## Freshness proof
0 rows older than 120 days; `source_freshness` reporting 6 source rows. See
`source-freshness-report.md`.

## FCL licence status
**BLOCKED BY OWNER** — fail-closed, 0 case-law rows, no fakes.

## Gaps / next corpus expansion targets
- ACAS guidance breadth (standalone disciplinary/grievance/dismissal/EC/settlement/
  redundancy guides) — IMPLEMENTED BUT PARTIAL.
- GOV.UK tribunal-procedure depth — PARTIAL.
- Increase of Limits Orders (uksi) for backdated cases — NOT STARTED.
- Equality Act 2010 — PREPARED, INACTIVE (active:false until discrimination workflow).
- Case law — BLOCKED BY OWNER.
