# Jurisdiction Hardcode Backlog

**Source:** A6 evidence pack (reports/a6_jurisdiction_evidence.md, 276 hits)  
**Trivial fixes applied:** `= "EW"` function parameter defaults → `DEFAULT_JURISDICTION` config constant (103 sites across ~30 files)  
**Remaining:** structural hits requiring design work, listed below with effort estimates.

---

## Structural — Logic Coercions (must become registry-backed + fail-closed)

| # | File:Line | Current Behaviour | Required Change | Effort |
|---|-----------|-------------------|-----------------|--------|
| 1 | backend/core/brain.py:601-602 | Unknown jurisdiction silently coerced to DEFAULT_JURISDICTION | Query `legal_jurisdictions` table; if code not in registry → fail closed with `jurisdiction_not_supported` | S (1h) |
| 2 | backend/core/orchestrator.py:70-72 | Same coercion duplicated | Same fix as #1; DRY with shared helper | S (30m) |
| 3 | backend/core/brain.py:228 | Response gate hardcodes `("EW", "SC", "NI")` | Read supported set from `legal_jurisdictions` (cache) | S (30m) |
| 4 | backend/core/retrieve.py:60-63 | `_GB_CODES` / `_JURISDICTION_CODE_MAP` hardcoded | Move map to `legal_jurisdictions` table (add `compatible_codes` column or join table) | M (2h) |
| 5 | backend/core/agentic/corpus_citation_guard.py:292 | Hardcoded UK jurisdiction whitelist in citation acceptance logic | Read from registry | S (30m) |
| 6 | backend/core/agentic/ingestion_critic.py:28 | `SUPPORTED_JURISDICTIONS` = hardcoded set | Read from `legal_jurisdictions` at init | S (15m) |
| 7 | backend/core/rag/graph_engine.py:122 | Neo4j query hardcodes `IN [$jurisdiction, 'GB', 'EW', 'UK']` | Parameterise from jurisdiction compatibility map | S (30m) |
| 8 | backend/language_engine/ar/phrasing.py:71 | Logic branch on `"EW"` | Needs jurisdiction-aware phrasing registry | M (1h) |

**Subtotal: ~6.5h**

---

## Structural — Unfiltered Query Sites (must add jurisdiction predicate)

| # | File:Line | Table | Risk | Effort |
|---|-----------|-------|------|--------|
| 1 | backend/services/lawapp-rag-service/main.py:211 | corpus_chunks (FTS) | Returns cross-jurisdiction chunks | S (30m) |
| 2 | backend/services/lawapp-rag-service/main.py:297 | corpus_chunks (vector) | Returns cross-jurisdiction chunks | S (30m) |
| 3 | backend/core/feature_spec_service.py:116 | corpus_chunks | Assumes UK corpus | S (30m) |
| 4 | backend/core/citations/linker.py:38 | legislation | act_title match only; assumes UK acts | S (30m) |
| 5 | backend/core/citation_verifier.py:85,92 | legislation | ILIKE match; assumes UK acts | S (30m) |
| 6 | backend/domains/employment/constructive_dismissal.py:60 | legislation | SQL hardcodes `act_title ILIKE '%Employment Rights Act 1996%'` | M (1h) |

**Subtotal: ~3.5h**

---

## Structural — UK-Statute Constants Embedded in Code (89 hits)

| File | Hit Count | Nature | Effort |
|------|-----------|--------|--------|
| backend/core/employment_assessment.py | 33 | Hardcoded authority strings + legislation.gov.uk URLs per claim type | L (4h) — move to rules table `authority_ref`/`authority_url` |
| backend/domains/employment/assess_logic.py | 22 | Same pattern | L (3h) |
| backend/core/classify.py | 12 | Fallback authority map (lines 120-129) | M (1.5h) — move to `employment_modules` table |
| backend/core/documents.py | 25 | ERA sections in document templates | L (4h) — needs jurisdiction-parameterised templates |
| backend/core/citation_verifier.py | 4 | UK-act abbreviation map | S (30m) |
| backend/core/citations/*.py | 4 | Citation parsing/normalisation | S (30m) |
| backend/core/tools.py | 4 | Hardcoded tool descriptions | S (15m) |
| Other (7 files) | 6 | Scattered constants | S (1h) |

**Subtotal: ~15h**

---

## Structural — Document Templates (30 prompt-level hits)

| File | Hits | Nature | Effort |
|------|------|--------|--------|
| backend/core/documents.py:290-532 | 25 | Tribunal letters embed ERA 1996 Part X sections | L (4h) — needs template-per-jurisdiction system |
| backend/core/bundle.py:288-497 | 5 | Case bundles embed UK legislation | M (2h) |

**Subtotal: ~6h**

---

## Total Backlog Estimate

| Category | Hits | Effort |
|----------|------|--------|
| Logic coercions → registry-backed | 8 | ~6.5h |
| Unfiltered queries → add jurisdiction predicate | 6 | ~3.5h |
| UK-statute constants → rules/corpus rows | 89 | ~15h |
| Document templates → parameterised | 30 | ~6h |
| **Total structural** | **133** | **~31h** |

The remaining 143 hits (of 276 total) are the `= "EW"` function defaults already fixed via `DEFAULT_JURISDICTION` config constant.

---

*This backlog is for planning only. No structural changes applied. All estimates assume single-developer pace with test updates.*
