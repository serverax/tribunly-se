# UK Legal Dataset Build Report

**Domain:** `employment_uk`  **Country:** GB  **Jurisdiction:** EW (default)
**Date:** 2026-06-05
**Proof:** `scripts/prove_uk_legal_dataset.sh` → **PASSED (exit 0)**
**Status:** DONE AND PROVEN (employment-law foundation) — see Gaps for next expansion.

> Principle enforced: **LEGAL DB FIRST → CORPUS FIRST → RULES FIRST → CITATIONS FIRST → AI SECOND → FAIL-CLOSED ALWAYS.**

---

## 1. Architecture — domain-pack driven (reusable for future law areas / countries)

The source list is **not** hardcoded in Python. It lives in the domain pack and is
loaded by `ingestion/domain_loader.py`:

```
domains/employment_uk/
  domain_config.json     identity, jurisdictions, active claim types, manifest paths
  sources.yaml           official source manifest (legislation sections, ACAS/GOV.UK, FCL)
  rules_manifest.yaml    required deterministic rules + statutory authority
  citation_policy.yaml   RAG citation acceptance + source trust order
  licence_policy.yaml    per-source licence; Find Case Law bulk fail-closed
  workflows.yaml         workflows this domain enables + their table/rule/source deps
  README.md
```

`ingestion/legislation/ingest.py` now resolves its targets from the pack
(`load_domain_pack().legislation_targets()`), falling back to `config.LEGISLATION_TARGETS`
only if the pack is absent. The Corpus Ingestion AIA
(`backend/core/agents/corpus_ingestion_aia.py`) fails closed if the pack or any
manifest is missing (`validate_domain_pack`, `validate_dataset`).

To add a new domain/country: copy `domains/employment_uk/`, edit the manifests.
No core platform change required.

## 2. Database — organised, cited, versioned, reusable

Tables verified/added:

| Table | Purpose | Rows |
|---|---|---|
| `legal_sources` | provenance registry (one row per authorised source) | 4 |
| `legislation` | primary legislation chunks (CLML XML) | 188 |
| `acas_guidance` | ACAS official guidance chunks | 12 |
| `official_guidance` | GOV.UK guidance chunks | 7 |
| `case_law_documents` | tribunal/EAT (licence-gated) | 0 (fail-closed) |
| `rules` | deterministic cited rules | 19 |
| `source_freshness` | freshness reporting | 6 |
| `corpus_ingestion_runs` | ingestion audit (run kind, counts, pass/fail) | 2 |

**Every legal row carries** (migrations 026/028/029): `country_code`, `jurisdiction`,
`domain`, `source_type`, `source_url`, `section_ref`/citation, `content_hash`,
`last_verified_at`, `licence_status`, `parser_type`, `parent_source_id`.
Provenance completeness: **legislation 0 missing, acas 0 missing, official 0 missing.**
content_hash coverage: **188/188 legislation**.

**Every rule row carries:** `rule_key`, `domain`, `country_code`, `jurisdiction`,
`claim_type`, `authority_ref`, `authority_url`, `effective_from`, `value_numeric`/`value_text`,
`last_verified_at`. All 19 rules pass the full-field gate.

## 3. Source list + licence status

| source_id | source_type | licence | status |
|---|---|---|---|
| legislation_gov_uk | primary_legislation | Open Government Licence v3.0 | GRANTED |
| acas | official_guidance | ACAS public guidance | GRANTED |
| govuk | official_guidance | Open Government Licence v3.0 | GRANTED |
| find_case_law | case_law | Open Justice Licence | **BLOCKED_BY_OWNER** (bulk fail-closed) |

## 4. Legislation corpus — sections present

**52 distinct section_refs** across 4 Acts (expanded from the initial 13).

- **Employment Rights Act 1996 (ukpga/1996/18):** s.1, s.13, s.23, s.43A, s.43B,
  s.43C, s.43D, s.43E, s.43F, s.43G, s.43H, s.43J, s.43K, s.43L (whistleblowing),
  s.47B, s.94, s.95, s.97, s.98, s.99, s.100, s.103A, s.104, s.108, s.111, s.112,
  s.113, s.114, s.115, s.118, s.119, s.120, s.122, s.123, s.124, s.126, s.207B,
  s.221-s.229 (week's pay).
- **Employment Tribunals Act 1996 (ukpga/1996/17):** s.18A (early conciliation).
- **TULRCA 1992 (ukpga/1992/52):** s.207A (ACAS Code uplift), s.156.
- **Employment Rights Act 2025 (ukpga/2025/36):** s.25, s.152, s.159 — **marked
  prospective, effective-dated, NOT treated as current** until commencement proven.

**Intentionally excluded:** ERA 1996 **s.127** (special award) — repealed by the
Employment Relations Act 1999; fetching would 404. Recorded, not faked.

## 5. Rules present (deterministic, cited, effective-dated)

unfair_dismissal: time_limit_months, qualifying_period, weeks_pay_cap_amount,
compensatory_cap_amount, compensatory_cap_weeks_pay, basic_award_formula,
basic_award_min_automatic, early_conciliation_required, ec_max_duration_weeks.
unlawful_deduction_wages: qualifying_period_years, remedy_basis, time_limit_months,
worker_status, series_deductions_note.

## 6. Embeddings / freshness / RAG / citation proof

- Embeddings: **188/188** legislation chunks embedded (`bge-small-en-v1.5`, 384-dim, local).
- Freshness: 0 rows older than 120 days; `source_freshness` reporting 6 rows.
- Hybrid RAG: grounded (`insufficient_grounding:false`) and **cites ERA 1996 s.98
  which resolves to a real DB row** (citation→DB resolution proven).

## 7. Find Case Law — licence gate

`case_law_documents` = **0 rows**, fail-closed behind `FCL_BULK_LICENCE_GRANTED=false`.
Registry status `BLOCKED_BY_OWNER`. No fake/placeholder cases. See
`reports/fcl-licence-gate-report.md`.

## 8. Gaps / next corpus expansion targets

- **ACAS guidance breadth — IMPLEMENTED BUT PARTIAL:** currently the ACAS Code of
  Practice on Disciplinary & Grievance (12 chunks). Next: standalone ACAS
  disciplinary/grievance/dismissal/early-conciliation/settlement/redundancy guides.
- **GOV.UK breadth — PARTIAL:** 7 guides present (dismissal, redundancy, tribunal
  claim, holiday, helpline). Next: tribunal procedure detail, ACAS EC certificate flow.
- **Increase of Limits Orders — NOT STARTED:** week's-pay cap / comp-award values are
  held as cited `rules` rows today; ingesting the SIs (uksi) as legislation for
  historical/backdated cases is the next target (different parser path).
- **Equality Act 2010 — PREPARED, INACTIVE:** declared in `sources.yaml` (`active:false`);
  ingest when the discrimination workflow is built.
- **Case law — BLOCKED BY OWNER:** pipeline prepared, fail-closed (licence).

## 9. Reproduce

```
docker compose exec -T db psql -U lawapp -d lawapp < db/migrations/028_legal_sources_registry.sql
docker compose exec -T db psql -U lawapp -d lawapp < db/migrations/029_legal_provenance_columns.sql
docker compose run --rm ingestion python -m ingestion.legislation.ingest
docker compose run --rm ingestion python -m ingestion.embeddings.embedder
docker compose run --rm ingestion python -c "from backend.core.agents.corpus_ingestion_aia import register_legal_sources; print(register_legal_sources('employment_uk'))"
bash scripts/prove_uk_legal_dataset.sh    # exits 0
```
