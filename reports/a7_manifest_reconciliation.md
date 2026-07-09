# A7 Manifest Reconciliation

**Manifest:** 27 items (26 resolved + 1 ambiguous)  
**DB:** 22 distinct acts (2,242 legislation rows, 4,069 corpus chunks)  
**Date:** 2026-07-08

---

## Per-Act Disposition

| # | Manifest Item | Disposition | Sections | Notes |
|---|--------------|-------------|----------|-------|
| 1 | Employment Rights Act 1996 | **INGESTED** | 428 | Core statute. SA-3 crawl. |
| 2 | Equality Act 2010 | **INGESTED** | 273 | SA-3 crawl. |
| 3 | Employment Relations Act 1999 | **INGESTED** | 84 | SA-3 crawl. |
| 4 | Employment Act 2002 | **INGESTED** | 102 | SA-3 crawl. |
| 5 | TULRCA 1992 | **INGESTED** | 103 | SA-3 crawl. Originally 53 sections; re-ingestion added 50 more from deeper XML parse. |
| 6 | Employment Tribunals Act 1996 | **INGESTED** | 1 | SA-3 crawl (stub — summary only). |
| 7 | National Minimum Wage Act 1998 | **INGESTED** | 5 | SA-3 crawl. |
| 8 | Carer's Leave Act 2023 | **NOT INGESTED** | — | Short Act (3 sections). Not in SA-3 crawl scope. |
| 9 | Neonatal Care (Leave and Pay) Act 2023 | **NOT INGESTED** | — | Not in SA-3 crawl scope. |
| 10 | Protection from Redundancy (Pregnancy and Family Leave) Act 2023 | **NOT INGESTED** | — | Short Act. Not in SA-3 crawl scope. |
| 11 | Workers (Predictable T&C) Act 2023 | **NOT INGESTED** | — | Repealed before commencement. Low priority. |
| 12 | Employment (Allocation of Tips) Act 2023 | **NOT INGESTED** | — | Not in SA-3 crawl scope. |
| 13 | Employment Rights Act 2025 | **INGESTED** | 1,186 | Manual SI-gap ingestion (this session). Large Act. |
| 14 | National Minimum Wage Regulations 2015 | **NOT INGESTED** | — | SI. Not in SA-3 crawl scope. |
| 15 | Working Time Regulations 1998 | **INGESTED** | 8 | SA-3 crawl. |
| 16 | TUPE Regulations 2006 | **INGESTED** | 4 | SA-3 crawl. |
| 17 | Part-time Workers Regulations 2000 | **INGESTED** | 2 | SA-3 crawl. |
| 18 | Fixed-term Employees Regulations 2002 | **INGESTED** | 2 | SA-3 crawl. |
| 19 | Agency Workers Regulations 2010 | **INGESTED** | 3 | SA-3 crawl. |
| 20 | Flexible Working Regulations 2014 | **NOT INGESTED** | — | Superseded by 2023 amendment. |
| 21 | Flexible Working (Amendment) Regulations 2023 | **COVERED** | — | Parent Act (Employment Relations (Flexible Working) Act 2023) ingested this session (4 sections). |
| 22 | Maternity and Parental Leave etc. Regulations 1999 | **INGESTED** | 1 | SA-3 crawl (stub). |
| 23 | Paternity and Adoption Leave Regulations 2002 | **NOT INGESTED** | — | SI. Not in SA-3 scope. |
| 24 | Shared Parental Leave Regulations 2014 | **NOT INGESTED** | — | SI. Not in SA-3 scope. |
| 25 | ET Early Conciliation Regulations 2014 | **NOT INGESTED** | — | SI. Not in SA-3 scope. |
| 26 | Carer's Leave Regulations 2024 | **NOT INGESTED** | — | SI. Not in SA-3 scope. |
| 27 | Neonatal Care Regulations (2024/2025) | **AMBIGUOUS** | — | SI not yet made or year uncertain. |

## Additional Acts in DB (not in original manifest)

| Act | Sections | Source |
|-----|----------|--------|
| Children and Families Act 2014 | 1 | Pre-existing (before WO007). |
| Paternity Leave (Bereavement) Act 2024 | 1 | Pre-existing. |
| Employment Tribunals Extension of Jurisdiction (E&W) Order 1994 | 2 | Pre-existing. |
| Employment Relations (Flexible Working) Act 2023 | 4 | SI-gap ingestion (this session). |
| Employment Rights (Increase of Limits) Order 2024 (SI 2024/213) | 8 | SI-gap ingestion. Covers monetary caps for 2024. |
| Employment Rights (Increase of Limits) Order 2025 (SI 2025/348) | 10 | SI-gap ingestion. Covers monetary caps for 2025. |
| Employment Rights (Increase of Limits) Order 2026 (SI 2026/310) | 8 | SI-gap ingestion. Covers monetary caps for 2026. |
| Employment Tribunals (EC Amendment) Regulations 2025 (SI 2025/1153) | 6 | SI-gap ingestion. EC max duration. |

## Source-less Rules Resolution

18 rules referenced legislation.gov.uk URLs with no matching `legislation` row. After SI-gap ingestion:

| Rule Authority URL | Status | Notes |
|-------------------|--------|-------|
| uksi/2024/213/schedule/made | **NOW INGESTED** | SI 2024/213 (£700 cap year) |
| uksi/2025/348/schedule/made | **NOW INGESTED** | SI 2025/348 (£719 cap year) |
| uksi/2026/310/schedule/made | **NOW INGESTED** | SI 2026/310 (£751 cap year) |
| uksi/2025/1153/made | **NOW INGESTED** | EC amendment regs |
| ukpga/2025/36/section/25 | **NOW INGESTED** | ERA 2025 (provisional 6m qualifying) |
| ukpga/2025/36/section/152 | **NOW INGESTED** | ERA 2025 (provisional 6m time limit) |
| ukpga/2023/33/section/1 | **NOW INGESTED** | Flexible Working Act 2023 |
| ukpga/1992/52/section/207A | URL MISMATCH | TULRCA ingested act-level; rule references section-level URL |
| ukpga/1996/18/part/VIII/chapter/I | URL MISMATCH | ERA ingested section-level; rule references part-level URL |
| uksi/1998/1833/part/II | URL MISMATCH | WTR ingested section-level; rule references part-level URL |
| uksi/1994/1623 | URL MISMATCH | ET Extension Order ingested but source_url format differs |

**URL mismatches** are not missing data — the legislation text IS in the DB under a different `source_url`. The rules-to-legislation join needs to match on `act_title` as well as `source_url`, or the rule URLs need normalising. This is a data-quality improvement, not a gap.

## Summary

| Category | Count |
|----------|-------|
| Manifest items ingested | 15 (of 27) |
| Manifest items covered (parent Act ingested) | 1 |
| Manifest items not ingested (small/out-of-scope SIs) | 10 |
| Manifest items ambiguous | 1 |
| Additional Acts in DB (not in manifest) | 8 |
| Source-less rules now resolved | 7 (of 11 distinct URLs) |
| Source-less rules with URL mismatch only | 4 |
| **Total distinct Acts in DB** | **22** |
| **Total legislation rows** | **2,242** |
| **Total corpus chunks** | **4,069** |
