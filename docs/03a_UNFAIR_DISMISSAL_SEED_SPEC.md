# 03a - Unfair Dismissal `rules` Seed Spec (England, Wales & Scotland)

**Pairs with:** `03_DATABASE_DESIGN.md` (the `rules` table), `05_WASM_SPEC.md` (deadline logic), `01a_PHASE1_API_APPENDIX.md` (how to fetch from legislation.gov.uk).
**Purpose:** Tell the Phase 1 ingestion agent exactly which legislation to fetch, which `rules` rows to seed, and how the deadline arithmetic works - so it does not improvise legal values. This is the artefact most likely to be got wrong if left to the agent's memory.

**Read this first:** Every numeric value and section number below is a *starting pointer for live verification*, not a value to hardcode. The agent fetches and confirms each from the live API at ingest, stores `source_url` + version + `last_verified_at`, and flags any mismatch rather than proceeding. Guardrail 3 (determinism) means these live in the `rules` table, queried by code; the model never recalls or re-derives them.

---

## 0. CRITICAL CONTEXT - the law is mid-transition (this shapes the whole seed)

The Employment Rights Act 2025 (ERA 2025) received Royal Assent on 18 December 2025 and is being commenced in phases. Three core unfair-dismissal values change on a known timetable. The seed MUST be effective-dated across these regimes, not a single undated snapshot.

| Concept | Current law (in force now, 29 May 2026) | Changes to | When (verify - dates are soft) |
|---|---|---|---|
| Tribunal time limit | 3 months less 1 day | 6 months | "No earlier than October 2026" - treat as provisional, confirm by commencement SI |
| Qualifying period | 2 years' continuous service | 6 months | Dismissals with EDT on/after 1 January 2027 |
| Compensatory award cap | Capped (£ figure or 52 weeks' pay, lower) | Cap removed (uncapped) | Dismissals with EDT on/after 1 January 2027 |

**Design rule that follows from this:** seed one row *per value per regime*, each with `effective_from` / `effective_to` and `is_prospective` where enacted-but-not-commenced. The deadline/value logic reads the row whose effective window covers the relevant date (normally the EDT), so a future commencement is a data change, never a code change. Do NOT collapse this into "current values only".

**Jurisdiction note:** ERA 1996 extends to England, Wales AND Scotland (Great Britain). For unfair dismissal the substantive figures are GB-wide - seed rows for `EW` and `S` with the same values (or treat `EW` as covering GB and document it). Northern Ireland is a *separate statute* (Employment Rights (NI) Order 1996) with *different figures* - do not reuse GB values for NI. If you see £123,785 / £783 quoted, that is NI, not GB.

---

## 1. Legislation to fetch (legislation.gov.uk)

Resolve chapter numbers via the title-resolution endpoint (`/id?title=`) before fetching - do not trust the chapter numbers in this table. Fetch both the **current in-force** version and the **`/prospective`** version for any section ERA 2025 amends (s.108, s.111, s.124), so the agent can store the incoming text with `is_prospective = true`.

| Concept | Act (verify chapter) | Section | Governs | Verify |
|---|---|---|---|---|
| Right not to be unfairly dismissed | ERA 1996 (ukpga 1996 c.18) | s.94 | The basic right | Confirm c.18 via title API |
| Meaning of dismissal (incl. constructive) | ERA 1996 | s.95 | What counts as dismissal | |
| Effective date of termination (EDT) | ERA 1996 | s.97 | The date the deadline runs from | Critical for deadline calc |
| Fairness / reasons | ERA 1996 | s.98 | Potentially fair reasons + reasonableness (band of reasonable responses) | The core merits test |
| Qualifying period | ERA 1996 | s.108 | Currently 2 years; ERA 2025 reduces to 6 months | Fetch current AND `/prospective` |
| Time limit | ERA 1996 | s.111(2) | "Before the end of 3 months beginning with the EDT" + "not reasonably practicable" extension | Fetch current AND `/prospective` |
| Basic award | ERA 1996 | s.119 | Age-banded formula | |
| Basic award - minimum (certain automatically unfair) | ERA 1996 | s.120 | Statutory minimum basic award | |
| Basic award - reductions | ERA 1996 | s.122 | Contributory fault etc. | |
| Compensatory award | ERA 1996 | s.123 | "Just and equitable" loss | |
| Limit on compensatory award (the cap) | ERA 1996 | s.124 | The £ cap and the 52-week alternative | Fetch current AND `/prospective` (cap removed) |
| Extension of time for Early Conciliation | ERA 1996 | s.207B | "Stop the clock" mechanics | Drives EC deadline logic |
| Limit on a week's pay | ERA 1996 | s.227 | The week's-pay cap used in basic award + redundancy | Uprated annually by SI |
| ACAS Code uplift/reduction | TULRCA 1992 (ukpga 1992 c.52) | s.207A | Up to 25% adjustment for unreasonable failure to follow the Code | Confirm c.52 |
| Requirement to contact ACAS before claim | Employment Tribunals Act 1996 (ukpga 1996 c.17) | s.18A | Early Conciliation requirement | Confirm c.17 |
| Amending provisions | Employment Rights Act 2025 (ukpga 2025 c.?) | (qualifying period, cap, time limit) | The reforms above | Resolve chapter; commencement is by SI - find the SIs |
| Annual uprating | The Employment Rights (Increase of Limits) Order 2026 (uksi) | n/a | Sets the April 2026 figures | Find the SI number; it is the authority for the £751 / £123,543 figures |

**Not needed for unfair dismissal:** Equality Act 2010 is discrimination (Phase 5), not unfair dismissal. Do not pull it into this seed.

---

## 2. The `rules` rows to seed

Values below are the *current verified figures* (England, Wales & Scotland) plus the *known forthcoming changes*. Confirm each against the cited authority at ingest. Schema fields per `03_DATABASE_DESIGN.md` §2.4.

### 2.1 Qualifying period
```
rule_key:        unfair_dismissal.qualifying_period
value_numeric:   2          unit: years
authority_ref:   ERA 1996 s.108      authority_type: legislation
effective_from:  2012-04-06          effective_to: 2026-12-31
description:     "Ordinary unfair dismissal requires 2 years' continuous service (EDT up to 31 Dec 2026)."
```
```
rule_key:        unfair_dismissal.qualifying_period
value_numeric:   6          unit: months
authority_ref:   ERA 1996 s.108 as amended by ERA 2025      is_prospective: true (until commencement SI confirmed)
effective_from:  2027-01-01          effective_to: NULL
description:     "Reduced to 6 months for dismissals with EDT on/after 1 Jan 2027. Applies to existing employees, no transitional carve-out."
```
> Day-one exceptions are unchanged by this: discrimination and automatically-unfair grounds (whistleblowing, health & safety, etc.) need no qualifying period. Seed those as separate `qualifying_period = 0` rows keyed by reason if/when the engine handles automatically-unfair claims - flag as a follow-up, not in scope for the ordinary-unfair MVP.

### 2.2 Time limit
```
rule_key:        unfair_dismissal.time_limit_months
value_numeric:   3          unit: months
authority_ref:   ERA 1996 s.111(2)
effective_from:  <last change date - verify>   effective_to: 2026-09-30   (soft - tie to ET time-limit commencement SI)
description:     "3 months 'beginning with' the EDT (i.e. less one day). 'Not reasonably practicable' extension may apply - merits judgement, not deterministic."
```
```
rule_key:        unfair_dismissal.time_limit_months
value_numeric:   6          unit: months
authority_ref:   ERA 1996 s.111(2) as amended by ERA 2025      is_prospective: true
effective_from:  2026-10-01          effective_to: NULL    (soft - "no earlier than Oct 2026")
description:     "Extended to 6 months. Same 'beginning with' convention. Confirm exact commencement before relying on it."
```
> The "less one day" is a *consequence* of the statutory "beginning with" wording, not a separate rule. It belongs in the deadline LOGIC (§3), not as a value here.

### 2.3 Early Conciliation
```
rule_key:        unfair_dismissal.early_conciliation_required
value_text:      "true"
authority_ref:   Employment Tribunals Act 1996 s.18A
effective_from:  2014-05-06   effective_to: NULL
description:     "Claimant must notify ACAS for Early Conciliation before issuing. EC pauses the limitation clock - see s.207B logic."
```

### 2.4 Compensatory award cap
```
rule_key:        unfair_dismissal.compensatory_cap_amount
value_numeric:   123543     unit: GBP
authority_ref:   ERA 1996 s.124 + Employment Rights (Increase of Limits) Order 2026
effective_from:  2026-04-06   effective_to: 2026-12-31
description:     "Statutory max compensatory award, OR 52 weeks' gross actual pay if lower."
```
```
rule_key:        unfair_dismissal.compensatory_cap_amount
value_numeric:   118223     unit: GBP
authority_ref:   ERA 1996 s.124 + Increase of Limits Order 2025
effective_from:  2025-04-06   effective_to: 2026-04-05
description:     "Prior-year figure - needed for back-dated cases (EDT in this window)."
```
```
rule_key:        unfair_dismissal.compensatory_cap_amount
value_text:      "uncapped"
authority_ref:   ERA 1996 s.124 as amended by ERA 2025      is_prospective: true
effective_from:  2027-01-01   effective_to: NULL
description:     "Cap removed for dismissals with EDT on/after 1 Jan 2027. Compensation = actual loss, uncapped. VERIFY whether the 52-week alternative limit is also removed or retained - confirm against amended s.124 text."
```
```
rule_key:        unfair_dismissal.compensatory_cap_weeks_pay
value_numeric:   52         unit: weeks_gross_pay
authority_ref:   ERA 1996 s.124(1ZA)
effective_from:  2013-07-29   effective_to: <verify - may end 2026-12-31>
description:     "Alternative cap: 52 weeks' gross actual pay if lower than the £ figure. Whether this survives 1 Jan 2027 must be verified."
```

### 2.5 Week's pay cap and basic award
```
rule_key:        unfair_dismissal.weeks_pay_cap_amount
value_numeric:   751        unit: GBP
authority_ref:   ERA 1996 s.227 + Increase of Limits Order 2026
effective_from:  2026-04-06   effective_to: NULL   (until next April uprating)
description:     "Cap on a week's pay for the basic award (and statutory redundancy). Prior figure £719 (2025-04-06 to 2026-04-05) - seed as a second dated row for back-dated cases."
```
```
rule_key:        unfair_dismissal.basic_award_min_automatic
value_numeric:   9157       unit: GBP
authority_ref:   ERA 1996 s.120 + Increase of Limits Order 2026
effective_from:  2026-04-06   effective_to: NULL
description:     "Minimum basic award where dismissal is automatically unfair on specified grounds (health & safety, trade union, etc.)."
```
```
rule_key:        unfair_dismissal.basic_award_formula
value_text:      "Per year of service (max 20): 1.5 weeks' pay for each year aged 41+, 1.0 week aged 22-40, 0.5 week under 22; week's pay capped at weeks_pay_cap_amount."
authority_ref:   ERA 1996 s.119
effective_from:  <verify>   effective_to: NULL
description:     "Deterministic formula. Max basic award currently = 20 x 1.5 x £751 = £22,530 (derived, not stored as a literal - compute from the formula + week's-pay cap so it stays correct after uprating)."
```
> Do not store £22,530 as a literal. It is `20 x 1.5 x weeks_pay_cap_amount`. Storing the derived figure means it silently goes stale next April. Compute it.

---

## 3. Deadline-calculation logic (deterministic - runs in WASM client-side + validated server-side; the LLM NEVER computes this)

This is the highest-risk arithmetic in the product. Spell it out, test it hard, verify the mechanics against the live s.111(2) and s.207B text and current ACAS guidance before relying on it. The rule VALUES (3 or 6 months) come from `rules` by EDT date; the arithmetic below is the logic.

**Inputs:** EDT (effective date of termination), and optionally Day A (date claimant first contacted ACAS for EC) and Day B (date the EC certificate was received/issued).

**Step 1 - Base limit (no EC):**
Take `time_limit_months` from `rules` for the row covering the EDT. The limit is the period of that many months "beginning with" the EDT, which ends the day *before* the corresponding date.
- Example: EDT = 10 May 2026, limit = 3 months. Period "beginning with 10 May" runs to end of **9 August 2026**. Claim must be presented on or before 9 Aug 2026.

**Step 2 - EC "stop the clock" (s.207B):** If EC was used:
1. Count the days from the day *after* Day A up to and including Day B - this is the paused period.
2. Add that number of days to the Step 1 base limit.
3. **Floor:** if the resulting date falls earlier than **one month after Day B**, the deadline is instead **one month after Day B**.
4. Final limitation date = the later of (base limit + paused days) and (one month after Day B), per s.207B(4).

**Worked example (floor does not bite):**
- EDT 10 May 2026 -> base limit 9 Aug 2026.
- Day A = 1 Jun, Day B = 20 Jun. Paused days = 2 Jun to 20 Jun inclusive = 19 days.
- 9 Aug + 19 days = 28 Aug 2026.
- One month after Day B = 20 Jul 2026. 28 Aug is later, so final = **28 Aug 2026**.

**Worked example (floor bites):**
- EDT 10 May 2026 -> base limit 9 Aug 2026.
- Day A = 5 Aug, Day B = 25 Aug (EC started near the end of the window). Paused days = 6 Aug to 25 Aug = 20 days. 9 Aug + 20 days = 29 Aug.
- One month after Day B = 25 Sep 2026. 25 Sep is later than 29 Aug, so final = **25 Sep 2026**.

**Notes / flags:**
- The "not reasonably practicable" extension under s.111(2)(b) is a *merits judgement*, not deterministic - do NOT compute it. Surface it as a possible factor and route to the honesty/uncertainty path, never assert it.
- Multiple respondents can have different EC certificates / dates - handle per-respondent if relevant; for the single-employer MVP, one EC pair is fine but note the limitation.
- When the 6-month time limit commences, only the `rules` value changes; this logic is untouched. That is the test that proves the determinism design works.
- VERIFY the exact day-counting convention (inclusive/exclusive of Day A and Day B) against the live s.207B text and a known-good worked example from ACAS - the inclusive/exclusive boundary is the classic place to be one day wrong, and one day wrong here loses someone their claim.

---

## 4. Live-verification checklist (do before seeding - never assume)

- [ ] ERA 1996 chapter number (c.18?) via `/id?title=Employment Rights Act 1996`.
- [ ] TULRCA 1992 and Employment Tribunals Act 1996 chapters via title resolution.
- [ ] ERA 2025 chapter number, and the specific commencement SIs for: ET time-limit extension, qualifying-period reduction, cap removal.
- [ ] s.111(2) current text - confirm "3 months beginning with the EDT" wording and fetch `/prospective` for the 6-month version.
- [ ] s.207B current text - confirm the exact stop-the-clock and one-month-floor mechanics.
- [ ] s.124 current text + the 52-week limit (s.124(1ZA)); fetch `/prospective` to see what the cap removal actually does to the section.
- [ ] s.227 + the Increase of Limits Order 2026 (uksi number) - confirm £751.
- [ ] Confirm £123,543 compensatory max for EDT on/after 6 Apr 2026 against the same Order.
- [ ] Confirm £9,157 minimum basic award.
- [ ] Current ACAS Code of Practice on Disciplinary and Grievance Procedures edition (for the merits/uplift layer, not this table - but verify while you are at it).

---

## 5. Test fact-patterns to capture (these become part of the Phase 2 regression set)

1. Straightforward EDT, no EC -> base 3-month-less-1-day limit. (Boundary value: confirm the exact last valid day.)
2. EC used, floor does not bite -> base + paused days.
3. EC used, floor bites (EC started late) -> one month after Day B.
4. EDT before 6 Apr 2026 -> older cap figure (£118,223) applies, not the current one. (Proves effective-dating works.)
5. Hypothetical EDT on/after 1 Jan 2027 -> 6-month qualifying period, uncapped compensation. (Proves prospective rows resolve correctly once commenced; keep flagged `is_prospective` until the SI confirms.)
6. Service of 18 months, EDT in 2026 -> NO ordinary unfair dismissal claim (under the 2-year rule). Same facts, EDT in 2027 -> claim qualifies. (Proves the qualifying-period transition.)

Each pattern needs an expected outcome recorded, so future changes cannot silently break the maths.

---

## 6. What must NOT happen (guardrail restatement for this artefact)

- No legal number hardcoded in application code. Every figure comes from `rules`, read by `effective_from`/`effective_to`.
- The LLM never computes, recalls, or re-derives a deadline, cap, qualifying period, or week's-pay figure.
- Do not seed a single undated regime. The ERA 2025 transition means undated values are wrong within months.
- Do not reuse Northern Ireland figures (£123,785 / £783) for GB.
- Do not assert the "not reasonably practicable" extension - it is a judgement, route it to the honesty path.
- Treat the October 2026 and January 2027 dates as provisional until the commencement SIs are published; mark prospective rows accordingly.

---

*Sources for the figures and dates in this spec were verified against ACAS, gov.uk/business.gov.uk, and multiple firm summaries as of 29 May 2026. The agent must still re-verify against the primary legislation.gov.uk text at ingest and record `last_verified_at`, because commencement SIs and the April uprating order are the authoritative sources, not secondary summaries.*
