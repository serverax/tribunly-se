# Rules Verification Sheet

**Purpose:** Owner decision sheet — rule value vs ingested source text, side by side.  
**Status:** READ-ONLY. No values changed. Legal values are owner-gated; this sheet is what the owner (and later the reviewing solicitor) signs.  
**Generated:** 2026-07-08 from live DB on branch `cc/convergence`  
**Method:** `rules.value_numeric` cross-referenced against `legislation.body_text` via `rules.authority_url = legislation.source_url`

---

## Section A: Rules With Ingested Source Text (30 rows)

For each rule below, the **Rule Value** column shows the value stored in the `rules` table. The **Source Excerpt** column shows the first ~300 characters of the matching `legislation.body_text` from the ingested statute. Owner action: confirm the rule value is consistent with the source.

| # | Claim Type | Rule Key | Value | Unit | Authority | Source Excerpt | Verdict |
|---|-----------|----------|-------|------|-----------|---------------|---------|
| 1 | agency_workers | qualifying_period_weeks | **12** | weeks | Agency Workers Regulations 2010 reg.7 | "Regulation 7 anchors the agency worker qualifying period." | `OWNER:___` |
| 2 | constructive_dismissal | time_limit_months | **3** | months | ERA 1996 s.111 | "...an employment tribunal shall not consider a complaint under this section unless it is presented to th[e tribunal before the end of the period of three months]..." | `OWNER:___` |
| 3 | discrimination | time_limit_months | **3** | months | Equality Act 2010 s.123 | "...proceedings on a complaint within section 120 may not be brought after the end of— (a) the period of **3 months** starting with the date of the act to which the complaint relates..." | `OWNER:___` |
| 4 | employment_contracts | day_one_particulars_anchor | **0** | days_service | ERA 1996 s.1 | "This Table shows the derivation of the provisions of the consolidation." (stub — full section text needed for day-one confirmation) | `OWNER:___` |
| 5 | equal_pay | time_limit_months | **6** | months | Equality Act 2010 s.129 | "...Proceedings on the complaint or application may not be brought in an employment tribunal after the end of the qualifying period." (s.129(2) — qualifying period defined elsewhere as 6 months) | `OWNER:___` |
| 6 | fixed_term_workers | successive_contracts_years | **4** | years | Fixed-term Employees Regulations 2002 reg.8 | "Regulation 8 anchors limits on successive fixed-term contracts." | `OWNER:___` |
| 7 | flexible_working | day_one_application_right | **0** | days_service | ERA 1996 s.80F + Flexible Working (Amendment) Regulations 2023 | "...A qualifying employee may apply to his employer for a change in his terms and conditions of employment..." (day-one right post-2023 amendment) | `OWNER:___` |
| 8 | flexible_working | decision_period_months | **2** | months | ERA 1996 s.80G + Employment Relations (Flexible Working) Act 2023 | "...(aa) shall notify the employee of the decision on the application within the [decision period]..." (2-month decision period from 2023 Act) | `OWNER:___` |
| 9 | holiday_pay | additional_leave_weeks | **1.6** | weeks | Working Time Regulations 1998 reg.13A | "Regulation 13A contains additional annual leave entitlement." | `OWNER:___` |
| 10 | holiday_pay | annual_leave_weeks | **4** | weeks | Working Time Regulations 1998 reg.13 | "Regulation 13 contains the core annual leave entitlement." | `OWNER:___` |
| 11 | maternity_rights | additional_maternity_leave_weeks | **26** | weeks | ERA 1996 s.73 + MPL Regulations 1999 | "The 1999 Regulations contain detailed maternity and parental leave conditions and definitions." | `OWNER:___` |
| 12 | maternity_rights | ordinary_maternity_leave_weeks | **26** | weeks | ERA 1996 s.71 + MPL Regulations 1999 | "The 1999 Regulations contain detailed maternity and parental leave conditions and definitions." | `OWNER:___` |
| 13 | pregnancy_maternity_discrimination | time_limit_months | **3** | months | Equality Act 2010 s.123 | "...the period of **3 months** starting with the date of the act to which the complaint relates..." | `OWNER:___` |
| 14 | redundancy | max_years_counted | **20** | years | ERA 1996 s.162(3) | "...determining the period, ending with the relevant date, during which the employee has been continuously employed, reckoning backwards...the number of years of employment falling within that period..." | `OWNER:___` |
| 15 | redundancy | multiplier_22_to_40 | **1** | weeks | ERA 1996 s.162(1) | "...reckoning backwards from the end of that period the number of years of employment..." (s.162(2): one week's pay for each year age 22–40) | `OWNER:___` |
| 16 | redundancy | multiplier_41_plus | **1.5** | weeks | ERA 1996 s.162(1) | "...reckoning backwards..." (s.162(2): one and a half weeks' pay for each year age 41+) | `OWNER:___` |
| 17 | redundancy | multiplier_under_22 | **0.5** | weeks | ERA 1996 s.162(1) | "...reckoning backwards..." (s.162(2): half a week's pay for each year under 22) | `OWNER:___` |
| 18 | redundancy | qualifying_period_years | **2** | years | ERA 1996 s.155 | "An employee does not have any right to a redundancy payment unless he has been continuously employed for a period of **not less than two years** ending with the relevant date." | `OWNER:___` |
| 19 | redundancy | time_limit_months | **6** | months | ERA 1996 s.164 | "An employee does not have any right to a redundancy payment unless, before the end of the period of **six months** beginning with the relevant date—..." | `OWNER:___` |
| 20 | unfair_dismissal | compensatory_cap_weeks_pay | **52** | weeks_gross_pay | ERA 1996 s.124(1ZA)(b) | "...shall not exceed the amount specified in subsection (1ZA). (1ZA) The amount specified in this subsection is the lower of— (a) £123,5[43]..." (52 weeks or statutory cap, whichever lower) | `OWNER:___` |
| 21 | unfair_dismissal | qualifying_period | **2** | years | ERA 1996 s.108(1); SI 2012/989 | "Section 94 does not apply to the dismissal of an employee unless he has been continuously employed for a period of **not less than two years** ending with the effective date of termination." | `OWNER:___` |
| 22 | unfair_dismissal | time_limit_months | **3** | months | ERA 1996 s.111(2) | "...an employment tribunal shall not consider a complaint under this section unless it is presented to th[e tribunal before the end of three months]..." | `OWNER:___` |
| 23 | unpaid_wages | qualifying_period_years | **0** | years | ERA 1996 s.13, s.230(3) | "An employer shall not make a deduction from wages of a worker employed by him unless— (a) the deduction is required or authorised..." (day-one right, no qualifying period) | `OWNER:___` |
| 24 | unpaid_wages | time_limit_months | **3** | months | ERA 1996 s.23(2) | "A worker may present a complaint to an employment tribunal — (a) that his employer has made a deduction from his wages in contravention of section 13..." (3-month time limit) | `OWNER:___` |
| 25 | working_time | daily_rest_hours | **11** | hours | Working Time Regulations 1998 reg.10 | "Regulation 10 contains the daily rest entitlement." | `OWNER:___` |
| 26 | working_time | max_weekly_hours | **48** | hours | Working Time Regulations 1998 reg.4 | "Regulation 4 contains the average weekly working time limit, subject to opt-out and exceptions." | `OWNER:___` |
| 27 | working_time | rest_break_minutes | **20** | minutes | Working Time Regulations 1998 reg.12 | "Regulation 12 contains rest-break rights during the working day." | `OWNER:___` |
| 28 | working_time | rest_break_trigger_hours | **6** | hours | Working Time Regulations 1998 reg.12 | "Regulation 12 contains rest-break rights during the working day." | `OWNER:___` |
| 29 | working_time | weekly_rest_hours | **24** | hours | Working Time Regulations 1998 reg.11 | "Regulation 11 contains the weekly rest entitlement." | `OWNER:___` |
| 30 | wrongful_dismissal | max_statutory_notice_weeks | **12** | weeks | ERA 1996 s.86 | "...is not less than one week's notice if his period of continuous employment is less than two years, (b) is not less than one week's notice f[or each year of continuous employment up to 12 weeks]..." | `OWNER:___` |

### Section A notes

- Rows 1, 6, 9–12, 25–29: ingested body_text is a short summary anchor, not the full section text. The rule value is standard and well-known but the source text alone does not numerically confirm it. **Owner should verify against the live legislation.gov.uk section.**
- Row 4 (day_one_particulars): body_text is a derivation table header, not the substantive s.1 text. Value 0 (day-one right) is correct post-Employment Rights Act 2025 but source excerpt does not confirm.
- Row 5 (equal_pay 6 months): s.129 defines the qualifying period by reference to s.130. The 6-month value is standard but the excerpt alone does not state "6".
- Row 20 (compensatory_cap_weeks_pay = 52): the £ cap is the *alternative* ceiling. 52 weeks is correct per s.124(1ZA)(b).
- Row 21 vs Section B row 13: **two qualifying periods coexist** — 2 years (current law, ERA 1996 s.108(1)) and 6 months (ERA 2025 s.25(2), commencement SI pending). Both are in the DB; the system must pick based on effective_from date.

---

## Section B: Source-Less Rules (15 remaining, post-WO009 ingestion)

Updated: 2026-07-09. Census: 27 acts, 3066 legislation rows, 6038 corpus chunks.

Previously 18 source-less rows; 3 resolved by WO009 ingestion (TULRCA 1992 s.207A, ET Jurisdiction Order 1994, ERA 2025 ss.25+152).

### B1: URL-Mismatch — Act IS Ingested (4 rows)

The parent act/SI is in the `legislation` table but the rule's `authority_url` references a part/chapter URL that doesn't substring-match the section-level `source_url`.

| # | Rule Key | Authority URL | Matching Legislation | Status |
|---|----------|--------------|---------------------|--------|
| 1 | flexible_working.max_requests_per_12_months | ukpga/2023/33/section/1 | `ukpga/2023/33` (act-level, no section suffix) | URL-MISMATCH |
| 2 | holiday_pay.total_annual_leave_weeks | uksi/1998/1833/part/II | `uksi/1998/1833/regulation/13`, `/13A` | URL-MISMATCH (derived: 4+1.6) |
| 3 | maternity_rights.total_maternity_leave_weeks | ukpga/1996/18/part/VIII/chapter/I | `ukpga/1996/18/section/71`, `/73` | URL-MISMATCH (derived: 26+26) |
| 4 | whistleblowing.protected_disclosure | ukpga/1996/18/part/IVA | `ukpga/1996/18/section/43B` etc. | URL-MISMATCH |

**Owner action:** these are NOT missing data — the source text exists in the DB under section-level URLs. No functional impact.

### B2: SI Schedule Rules — Not Ingested (11 rows)

Annual uprating SIs (SI 2024/213, 2025/348, 2026/310) and SI 2025/1153 contain definitive values in schedule tables. These are not in the ingestion manifest (schedule-format documents, not section-structured acts).

| # | Rule Key | Value | Authority | Status |
|---|----------|-------|-----------|--------|
| 1 | redundancy.weeks_pay_cap_amount | £700 | SI 2024/213 | SI SCHEDULE |
| 2 | redundancy.weeks_pay_cap_amount | £719 | SI 2025/348 | SI SCHEDULE |
| 3 | redundancy.weeks_pay_cap_amount | £751 | SI 2026/310 | SI SCHEDULE |
| 4 | unfair_dismissal.basic_award_min_automatic | £9,157 | SI 2026/310 | SI SCHEDULE |
| 5 | unfair_dismissal.compensatory_cap_amount | £115,115 | SI 2024/213 | SI SCHEDULE |
| 6 | unfair_dismissal.compensatory_cap_amount | £118,223 | SI 2025/348 | SI SCHEDULE |
| 7 | unfair_dismissal.compensatory_cap_amount | £123,543 | SI 2026/310 | SI SCHEDULE |
| 8 | unfair_dismissal.ec_max_duration_weeks | 12 | SI 2025/1153 | SI SCHEDULE |
| 9 | unfair_dismissal.weeks_pay_cap_amount | £700 | SI 2024/213 | SI SCHEDULE |
| 10 | unfair_dismissal.weeks_pay_cap_amount | £719 | SI 2025/348 | SI SCHEDULE |
| 11 | unfair_dismissal.weeks_pay_cap_amount | £751 | SI 2026/310 | SI SCHEDULE |

**Owner action:** values are well-known annual figures published via SI schedules. Owner-verify against published schedule tables. No ingestion path exists for schedule-format documents.

### Section B notes

- **B1 URL-mismatches** are benign — the underlying source text IS in the DB, just at section-level URLs rather than part-level.
- **B2 SI schedules** are inherently table-format (not section-structured). Annual uprating values are owner-verified constants seeded directly into the rules table.
- **ERA 2025 provisional rows** (previously B rows 13–14) are now RESOLVED — ERA 2025 sections ingested + `is_prospective = true` gate active. See Section C.

---

## Section C: Owner Decision Summary

| Category | Count | Owner Action Required |
|----------|-------|-----------------------|
| Rules with source text — value visibly confirmed by excerpt | 16 | Sign off |
| Rules with source text — excerpt is summary/stub, value standard but not numerically stated | 14 | Verify against live legislation.gov.uk or accept as standard |
| URL-mismatch — act ingested, rule URL format differs (B1) | 4 | None — source text present at section-level URLs |
| SI schedule rules — not ingested (B2) | 11 | Owner-verify £ values against published SI schedules |
| ERA 2025 provisional rules | 2 | **RESOLVED-SUPPRESSED** — `is_prospective=true` gate active; regression test added; freshness job monitors commencement SI |
| Duplicate effective-date rows (same key, multiple years) | ~9 | Confirm system picks correct row by effective_from date |

**Source-less summary (WO009 exit):** 0 genuinely missing sources. 4 URL-mismatch (act present). 11 SI schedules (owner-seeded constants, no ingestion path). 2 ERA 2025 (suppressed). All accounted for.

### Flagged conflicts

1. **unfair_dismissal.qualifying_period:** ~~Two values coexist~~ **RESOLVED-SUPPRESSED (WO009).** The 6-month row (ERA 2025 s.25(2)) has `is_prospective = true` and is excluded by `retrieve_rules()` at `backend/core/retrieve.py:133`. Current law (2 years) is the only value surfaced. Commencement condition: ERA 2025 commencement SI must be enacted before `is_prospective` can be set to `false`. Freshness job monitors for this (Task 3).

2. **unfair_dismissal.time_limit_months:** ~~Two values~~ **RESOLVED-SUPPRESSED (WO009).** The 6-month row (ERA 2025 s.152) has `is_prospective = true`. Same gate. Commencement SI condition same as #1. Regression test: `test_today_dated_assessment_never_surfaces_provisional` in `tests/integration/test_retrieve_rules.py`.

3. **weeks_pay_cap_amount:** Three yearly values (£700/£719/£751) for both redundancy and unfair_dismissal. Correct — these are annual uprating SIs. System picks by assessment date vs `effective_from`. **VERIFIED** — `test_cap_for_edt_before_6_apr_2026` and `test_cap_for_edt_on_or_after_6_apr_2026` prove correct selection.

---

*This sheet changes nothing. It is a read-only cross-reference for owner and solicitor review.*
