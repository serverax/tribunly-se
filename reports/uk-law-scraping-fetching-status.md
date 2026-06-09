# UK Law Scraping / Fetching — Status Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Proof:** `scripts/prove_uk_law_scraping_fetching.sh`
- **STATUS: `PARTIAL - CORE SOURCES FETCHED BUT DEPTH REMAINS`**

Core GB sources (legislation, UKSI, ACAS, GOV.UK) are genuinely **live-fetched from
official sources**. Find Case Law is **owner-blocked**. Northern Ireland and Bills/
reform-watch are **not started**. ACAS/GOV.UK depth and pre-2021 UKSI remain.

## Source-by-source classification

| Source | Classification | Module | Rows | Official URL? | parser | content_hash |
|---|---|---|---|---|---|---|
| legislation.gov.uk (ukpga) | **LIVE FETCHED FROM OFFICIAL SOURCE** | `ingestion/legislation/ingest.py` + `clml_parser.py` | 188 (52 sections, ERA 1996/2025, ETA 1996, TULRCA 1992) | yes (`legislation.gov.uk`) | clml_xml | yes |
| UKSI Increase of Limits Orders | **LIVE FETCHED FROM OFFICIAL SOURCE** | `ingestion/rules/seed_limits_orders.py` | 6 (2021–2026, `/uksi/{yr}/{no}/made`) | yes | clml_xml | yes (e.g. `c22099f1…`) |
| ACAS | **LIVE FETCHED FROM OFFICIAL SOURCE** | `ingestion/acas/ingest.py` | 36 (9 documents) | yes (`acas.org.uk`) | html | yes |
| GOV.UK | **LIVE FETCHED FROM OFFICIAL SOURCE** | `ingestion/govuk/ingest.py` | 17 (incl. employment-tribunals, dismissal, redundancy, grievance, whistleblowing) | yes (`gov.uk`) | html | yes |
| Find Case Law / National Archives | **BLOCKED BY LICENCE** (not complete) | `ingestion/sources/find_case_law.py` | **0** | n/a | akn (ready) | n/a |
| Northern Ireland employment law | **NOT STARTED** (fail-closed only) | — | 0 NI chunks / 0 NI rules | n/a | n/a | n/a |
| UK Parliament Bills / reform-watch | **NOT STARTED** (monitoring-only by design) | `ingestion/bills/` (present) | 0 | n/a | n/a | n/a |

## Legislation proof (live)
ERA 1996: 46 sections / 171 rows · ERA 2025: 3 sections (prospective) · ETA 1996 s.18A ·
TULRCA 1992: 2 sections · UKSI 2021–2026: 6 orders. All `jurisdiction_code=GB`, all
embedded, all with `legislation.gov.uk` source_url + content_hash + parser `clml_xml`.
Sample UKSI URLs: `https://www.legislation.gov.uk/uksi/2024/213/made` (hash `c22099f1…`),
`/uksi/2025/348/made` (`994f799e…`), `/uksi/2026/310/made` (`deddc56a…`).

## ACAS proof (live)
9 documents from `acas.org.uk` (Code of Practice + disciplinary/grievance step-by-step,
dismissals, notice periods, early conciliation, settlement agreements, managing
redundancies, unfair dismissal). parser=html, jurisdiction_code=GB.

## GOV.UK proof (live)
17 documents from `gov.uk` including **Make a claim to an employment tribunal**
(`/employment-tribunals`), Dismissal: your rights, Making staff redundant, Calculate
statutory redundancy pay, Raise a grievance, Disciplinary procedures, Whistleblowing,
Continuous employment, Employment status, etc.

## Find Case Law proof (BLOCKED)
- `case_law_documents` = **0 rows**.
- `corpus_ingestion_runs`: 2 rows `source_id=find_case_law`, `status=blocked`,
  blocker_reason populated (computational-analysis licence required).
- Module implemented: Atom discovery, LegalDocML/Akoma Ntoso XML fetch, content_hash
  change detection, checkpointing, throttle/backoff. **CASE LAW BULK INGESTION IS
  BLOCKED, NOT COMPLETE.**

## Northern Ireland proof (NOT STARTED)
`corpus_chunks` by jurisdiction: all **GB**; **NI = 0** chunks, **NI = 0** rules.
**NI SOURCE INGESTION IS NOT STARTED. NI FAIL-CLOSED ONLY.**

## Bills / reform-watch (NOT STARTED)
`bills` table present, 0 rows. Monitoring-only by design (UK Parliament Bills API /
prospective legislation) — NOT legal authority, NOT claimed as fetched corpus.

## Chunks / embeddings / provenance (corpus_chunks = 247, all GB)
| source_type | chunks | embedded | sourced |
|---|---|---|---|
| primary_legislation | 188 | 188 | 188 |
| official_guidance (ACAS+GOV.UK) | 53 | 53 | 53 |
| statutory_instrument (UKSI) | 6 | 6 | 6 |

0 missing source_url / chunk_hash / jurisdiction_code / embedding.

## What remains (depth)
- Find Case Law — owner licence (BLOCKED).
- Northern Ireland source mapping + ingestion (NOT STARTED).
- Bills/reform-watch population (NOT STARTED, monitoring-only).
- Pre-2021 Increase of Limits Orders; deeper multi-page ACAS guides; GOV.UK ET1/ET3 detail.
