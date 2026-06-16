# Corpus Quality  -  Report (SQL evidence)

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Proof scripts:** `scripts/prove_corpus_quality.sh`, `scripts/prove_uk_law_scraping_fetching.sh`

## legal_sources registry (by source_type / jurisdiction / domain)
```
SELECT source_type, jurisdiction, domain, COUNT(*) AS rows FROM legal_sources
GROUP BY source_type, jurisdiction, domain ORDER BY source_type, jurisdiction;

     source_type     | jurisdiction |    domain     | rows
---------------------+--------------+---------------+------
 case_law            | UK           | employment_uk |    1   (Find Case Law  -  OWNER_BLOCKED)
 govuk               | UK           | employment_uk |    1
 legislation         | NI           | employment_uk |    1   (NI placeholder  -  NOT_STARTED)
 official_guidance   | EW           | employment_uk |    1
 official_guidance   | GB           | employment_uk |    1
 parliament          | UK           | employment_uk |    1   (Bills  -  monitoring only)
 primary_legislation | GB           | employment_uk |    1
 tribunal            | GB           | employment_uk |    2   (GOV.UK ET/EAT  -  fallback)
```

## legislation by Act (live-fetched legislation.gov.uk)
```
SELECT act_title, jurisdiction_code, count(DISTINCT section_ref) sections, count(*) rows, max(last_verified_at)::date
FROM legislation GROUP BY act_title, jurisdiction_code ORDER BY act_title;

 Employment Rights Act 1996                                | GB | 46 | 171 | 2026-06-05
 Employment Rights Act 2025                                | GB |  3 |   7 | 2026-06-04  (prospective)
 Employment Tribunals Act 1996                             | GB |  1 |   6 | 2026-06-05
 The Employment Rights (Increase of Limits) Order 2021..2026 (UKSI) | GB | 1 each | 6 total
 Trade Union and Labour Relations (Consolidation) Act 1992 | GB |  2 |   4 | 2026-06-05
```
**Required UD sections present:** 94, 95, 97, 98, 108, 111, 119, 120, 122, 123, 124, 207B, 227 (all 13).

## rules verification_status (canonical vocabulary ONLY)
```
SELECT verification_status, COUNT(*) FROM rules GROUP BY verification_status ORDER BY 1;

 case_law_verified |  2
 prospective       |  3
 verified          | 29
```
**Zero `verified_live`. Zero `unverified`.** Canonical set = {verified, case_law_verified, prospective, unverified}.

## corpus_chunks quality (corpus_quality_report view)
```
 source_type          | jurisdiction | total_chunks | chunks_with_embedding | chunks_without_source_url | dup_hash
 primary_legislation  | GB           | 188          | 188                   | 0                         | 0
 statutory_instrument | GB           | 6            | 6                     | 0                         | 0
 official_guidance    | GB           | 53           | 53                    | 0                         | 0
```
247 chunks total · 247 embedded (`bge-small-en-v1.5`, vector(384)) · 0 missing
source_url/chunk_hash/jurisdiction_code · 0 duplicate hashes.

## case_law
```
SELECT count(*) FROM case_law_documents;  -- 0
```
Find Case Law bulk = **OWNER_BLOCKED** (computational-analysis licence pending); 2 `blocked`
runs recorded in `corpus_ingestion_runs` with blocker_reason; zero fake rows.

## Jurisdiction integrity
All employment corpus rows = **GB** (apply GB-wide: E&W + Scotland). **NI = 0** corpus rows
and **0** NI rules  -  NI is **NOT_STARTED / fail-closed**, never mapped to EW.

**Status: corpus quality PROVEN**  -  populated, organised by source_type/jurisdiction/
domain/effective-date, embedded, hashed, canonical verification statuses, no fake data.
