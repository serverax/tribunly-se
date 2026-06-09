# 08 - Unfair Dismissal `rules` Seed Specification

**Type:** Specification document. Not code. Not Phase 1 build artefact.
**Project root:** `F:\lawapp`
**Pairs with:** `03_DATABASE_DESIGN.md` (rules table schema), `04_RAG_REASONING_SPEC.md` (how the rules table feeds the pipeline), `01a_PHASE1_API_APPENDIX.md` (how to fetch from legislation.gov.uk).
**Status:** All values carry a VERIFY flag until pulled from the live API. No figure in this document is settled. Section references are a fetch plan, not confirmed facts.

---

## Purpose

This document tells the Phase 1 ingestion agent exactly what to seed into the `rules` table for the unfair dismissal claim type, and exactly how to compute the limitation date so that the WASM deadline module can implement deterministic arithmetic without any generative inference. Values must be replaced by live-verified figures before any row is written to the database.

**Guardrail 3 applies throughout:** deadlines, caps, and thresholds enter the `rules` table only after being pulled from the canonical source URI cited here. A figure from model memory or a secondary summary is not acceptable evidence of correctness.

---

## Section 1 - Source Acts and Resolution URIs

Before fetching any section, resolve each Act's canonical URI using the title-resolution endpoint. This confirms the exact type code and chapter number and must be done programmatically.

### 1.1 Primary Act - Employment Rights Act 1996

**Title resolution endpoint:**
```
GET https://www.legislation.gov.uk/id?title=Employment%20Rights%20Act%201996
```
Expected response: `301 Moved Permanently` to the canonical identifier URI. The chapter number `18` is noted here as a cross-reference only.

**VERIFY:** Confirm the resolved chapter before constructing any section URIs. If it does not match expectations, do not proceed - flag the mismatch.

**Point-in-time note:** The Employment Rights Act 2025 (if enacted and commenced by the time Phase 1 runs) amends several ERA 1996 provisions including qualifying periods, time limits, and compensation caps. Before fetching sections, check whether relevant provisions are enacted-but-not-yet-commenced. Use the `/prospective` URI suffix to retrieve prospective in-force text. Record `is_prospective = true` for any row reflecting law not yet in force.

### 1.2 Supporting Act - Employment Tribunals Act 1996

**Title resolution endpoint:**
```
GET https://www.legislation.gov.uk/id?title=Employment%20Tribunals%20Act%201996
```
VERIFY the canonical URI (expected `ukpga/1996/17` but confirm via the API before use).

### 1.3 Annual Uprating Instruments

The week's pay cap and compensatory award cap are uprated annually by statutory instrument, usually effective each April. To find the current SI:
```
GET https://www.legislation.gov.uk/search?title=Employment+Rights+%28Increase+of+Limits%29&type=uksi&sort=enacted-desc
```
Identify the most recent instrument and check its effective date. Fetch its Schedule to obtain current figures. Record the SI number and effective date in `authority_ref` and `effective_from`.

**VERIFY:** Confirm this is the most recent uprating SI in force on the relevant date before recording any monetary figure.

---

## Section 2 - Sections to Fetch (Fetch Plan)

Section references below are working hypotheses to be confirmed by fetching each section and reading the text. Do not treat these numbers as authoritative until the fetch returns the expected content.

| Purpose | Act | Section ref (VERIFY) | URI pattern to fetch | VERIFY note |
|---|---|---|---|---|
| Right not to be unfairly dismissed | ERA 1996 | s.94 | `/ukpga/1996/{chapter}/section/94/data.xml` | Confirm heading and substance. |
| Meaning of dismissal | ERA 1996 | s.95 | `/ukpga/1996/{chapter}/section/95/data.xml` | Confirm covers actual, constructive, and fixed-term expiry. |
| Effective date of termination | ERA 1996 | s.97 | `/ukpga/1996/{chapter}/section/97/data.xml` | Anchors the limitation clock. Confirm the definition. |
| Qualifying period | ERA 1996 | s.108 | `/ukpga/1996/{chapter}/section/108/data.xml` + `/prospective` | Expected 2 years (VERIFY). Check ERA 2025 amendment. |
| Time limit | ERA 1996 | s.111 | `/ukpga/1996/{chapter}/section/111/data.xml` | Confirm subsection (2) states the N-month period "beginning with" the EDT. |
| Basic award | ERA 1996 | s.119 | `/ukpga/1996/{chapter}/section/119/data.xml` | Confirm age-banded formula and reference to the week's pay cap. |
| Compensatory award | ERA 1996 | s.123 | `/ukpga/1996/{chapter}/section/123/data.xml` | Confirm "just and equitable" basis. |
| Limit on compensatory award | ERA 1996 | s.124 | `/ukpga/1996/{chapter}/section/124/data.xml` + `/prospective` | Verify current cap amount from SI. Check ERA 2025 removal of cap. |
| Week's pay cap | ERA 1996 | s.227 | `/ukpga/1996/{chapter}/section/227/data.xml` | Confirm this is the provision setting the capped week's-pay figure. |
| EC stop-the-clock | ERA 1996 | s.207B | `/ukpga/1996/{chapter}/section/207B/data.xml` | Confirm Day A / Day B mechanic and one-month floor. |
| EC requirement before claim | ETA 1996 | s.18A | `/ukpga/1996/{eta-chapter}/section/18A/data.xml` | Confirm ACAS notification required before presenting a claim. |

Replace `{chapter}` and `{eta-chapter}` with values confirmed in Section 1.

**Fetch protocol for each section:**
1. Resolve the Act canonical URI via the title endpoint (Section 1).
2. Fetch `{canonical_base}/section/{n}/data.xml` - current in-force version.
3. Fetch `{canonical_base}/section/{n}/prospective/data.xml` - prospective version.
4. If the prospective fetch returns `404`, record `is_prospective = false` and note no unapplied amendment is available.
5. If prospective text differs materially, create a second `rules` row with `is_prospective = true` and `effective_from` equal to the prospective commencement date (verified from the commencement SI).

---

## Section 3 - Rules Rows to Seed

Each row is a template. All values marked **[VERIFY]** are placeholders - replace from the live API fetch before writing to the database. Schema follows `03_DATABASE_DESIGN.md` section 2.4.

---

### Row 3.1 - Unfair dismissal: limitation period

```
rule_key:         unfair_dismissal.time_limit_months
claim_type:       unfair_dismissal
jurisdiction:     EW
value_numeric:    [VERIFY - expected 3 but confirm from the time-limit section text]
value_text:       null
unit:             months
description:      The claim must be presented before the end of the period of
                  [value_numeric] months beginning with the effective date of
                  termination (EDT), unless not reasonably practicable (a merits
                  question, not a deterministic rule). Extended by the ACAS EC
                  stop-the-clock mechanic. See Section 5 for the full arithmetic.
authority_type:   legislation
authority_ref:    Employment Rights Act 1996 s.111(2)  [VERIFY section number]
authority_url:    https://www.legislation.gov.uk/ukpga/1996/{chapter}/section/111/data.xml
                  [VERIFY chapter after title resolution]
effective_from:   [VERIFY - date s.111(2) in current form came into force]
effective_to:     null  (add effective_to and prospective sibling row if ERA 2025 extends the period)
is_prospective:   false
last_verified_at: [set at ingest time]
```

**Scotland note:** ERA 1996 extends to Great Britain. The substantive time limit is the same in Scotland. Flag any provision where the fetched text specifies a different EW vs Scotland rule.

**Prospective note:** ERA 2025 may extend the limitation period. If so, create a sibling row with `is_prospective = true`, `effective_from = [commencement date - VERIFY from SI]`, `value_numeric = [extended period - VERIFY]`.

---

### Row 3.2 - Early Conciliation: mandatory requirement

```
rule_key:         unfair_dismissal.ec_required
claim_type:       unfair_dismissal
jurisdiction:     EW
value_numeric:    null
value_text:       required
unit:             null
description:      A prospective claimant must notify ACAS and obtain an Early
                  Conciliation certificate before presenting a claim to the
                  employment tribunal. Procedural pre-condition, not an extension
                  of the limitation period itself. Failure to comply renders
                  the claim inadmissible.
authority_type:   legislation
authority_ref:    Employment Tribunals Act 1996 s.18A  [VERIFY section number and Act chapter]
authority_url:    https://www.legislation.gov.uk/ukpga/1996/{eta-chapter}/section/18A/data.xml
                  [VERIFY chapter after title resolution]
effective_from:   [VERIFY - date mandatory EC requirement came into force;
                  expected circa May 2014 but confirm from legislation text]
effective_to:     null
is_prospective:   false
last_verified_at: [set at ingest time]
```

---

### Row 3.3 - Qualifying period for unfair dismissal

```
rule_key:         unfair_dismissal.qualifying_period_years
claim_type:       unfair_dismissal
jurisdiction:     EW
value_numeric:    [VERIFY - expected 2 but confirm from the qualifying period section text]
value_text:       null
unit:             years
description:      An employee must have been continuously employed for at least
                  [value_numeric] years ending on the EDT to bring an ordinary
                  unfair dismissal claim. Exceptions exist for automatically unfair
                  dismissals (whistleblowing, trade union activity, health and
                  safety) which carry no qualifying period. Those exceptions are
                  not covered by this row.
authority_type:   legislation
authority_ref:    Employment Rights Act 1996 s.108(1)  [VERIFY section number]
authority_url:    https://www.legislation.gov.uk/ukpga/1996/{chapter}/section/108/data.xml
                  [VERIFY chapter after title resolution]
effective_from:   [VERIFY - the current 2-year period was introduced by SI circa 2012;
                  confirm exact date from the amending instrument]
effective_to:     null  (add effective_to and prospective sibling row if ERA 2025 reduces the period)
is_prospective:   false
last_verified_at: [set at ingest time]
```

**Prospective note:** ERA 2025 proposes reducing the qualifying period. If commenced, create a sibling row: `is_prospective = true`, `effective_from = [commencement date - VERIFY from SI]`, `value_numeric = [reduced period - VERIFY from Act text]`.

**Scotland note:** Same qualifying period applies across Great Britain. No separate row needed unless a Scotland-specific rule is discovered in the fetch.

---

### Row 3.4 - Week's pay cap

```
rule_key:         unfair_dismissal.weeks_pay_cap_gbp
claim_type:       unfair_dismissal
jurisdiction:     EW
value_numeric:    [VERIFY - fetch current figure from the most recent
                  Employment Rights (Increase of Limits) SI.
                  Do NOT use any figure from memory or a secondary source.]
value_text:       null
unit:             GBP
description:      The maximum amount of a week's pay for the purpose of calculating
                  the basic award for unfair dismissal. Uprated annually by statutory
                  instrument, usually effective each April. The basic award formula
                  applies this cap to each week of service in the age-banded
                  calculation. See Row 3.6 for the formula.
authority_type:   legislation
authority_ref:    Employment Rights Act 1996 s.227(1) as uprated by
                  [VERIFY: full SI citation from current uprating instrument]
authority_url:    [VERIFY: URL of the relevant SI schedule page on legislation.gov.uk]
effective_from:   [VERIFY - the date the current SI took effect]
effective_to:     [VERIFY - typically the day before the next April uprating;
                  null if no subsequent SI is yet published]
is_prospective:   false
last_verified_at: [set at ingest time]
```

**Annual uprating protocol:** Re-verify and update this row each time a new Increase of Limits Order is made. The `effective_to` of the outgoing row and the `effective_from` of the new row must be contiguous - no gap, no overlap.

---

### Row 3.5 - Compensatory award: statutory cap (Limb A)

The compensatory award is limited to the lower of two alternative figures under s.124(1ZA). Both limbs must be computed; neither is the default. **The s.227 capped week's pay figure (£751) does NOT apply to the 52-week comparator in Limb B** - Limb B uses the employee's actual gross weekly pay, uncapped.

**Limb A - Statutory cap (this row):**

```
rule_key:         unfair_dismissal.compensatory_cap_gbp
claim_type:       unfair_dismissal
jurisdiction:     EW
value_numeric:    [VERIFY - fetch current figure from the most recent
                  Employment Rights (Increase of Limits) SI.
                  Do NOT use any figure from memory.
                  Verified 2026-05-31: £123,543 per SI 2026/310, effective 6 April 2026.]
value_text:       null
unit:             GBP
description:      Limb A of the s.124(1ZA) compensatory cap: the fixed statutory
                  maximum. Uprated annually by statutory instrument. The compensatory
                  award is limited to the LOWER of this figure (Limb A) and 52 x
                  actual gross weekly pay (Limb B). Both limbs must be computed;
                  the lower applies. The s.227 capped week's pay (£751) does NOT
                  apply to Limb B - Limb B uses actual gross weekly pay, uncapped.
authority_type:   legislation
authority_ref:    Employment Rights Act 1996 s.124(1ZA)(a) as uprated by
                  Employment Rights (Increase of Limits) Order 2026 (SI 2026/310)
authority_url:    https://www.legislation.gov.uk/uksi/2026/310/schedule/made
effective_from:   2026-04-06
effective_to:     [VERIFY - null if no subsequent SI yet published]
is_prospective:   false
last_verified_at: [set at ingest time]
```

**Limb B - 52-week comparator (computation logic, not a rules row):**

Limb B is `52 x actual_gross_weekly_pay` where `actual_gross_weekly_pay` is the employee's actual gross weekly earnings, **not** capped at the s.227 figure. Application code must model this separately. The s.227 cap applies only to the basic award calculation, not to the Limb B comparator.

```
limb_a = compensatory_cap_gbp                     -- from rules table
limb_b = 52 x employee_actual_gross_weekly_pay    -- actual pay, NOT s.227-capped
compensatory_award_ceiling = min(limb_a, limb_b)
```

This computation runs in application code, not in WASM and not as a rules row.

**Prospective note:** ERA 2025 may remove the statutory cap entirely. If enacted and commenced, create a sibling row: `is_prospective = true`, `effective_from = [commencement date - VERIFY]`, `value_text = "uncapped"`, `value_numeric = null`. Limb B (52-week comparator) would still apply even if Limb A is removed, unless the Act also removes it - verify against the amended s.124 text.

---

### Row 3.6 - Basic award formula (reference row)

The basic award formula applies multipliers to whole completed years of service, capped at 20 years, using the capped week's pay figure:

- Service while aged under 22: 0.5 x capped week's pay x years
- Service while aged 22 to 40: 1.0 x capped week's pay x years
- Service while aged 41 or over: 1.5 x capped week's pay x years

These multipliers do not change with annual uprating. They are deterministic constants from the statute. Record as a reference text row; the computation belongs in application code.

```
rule_key:         unfair_dismissal.basic_award_formula_note
claim_type:       unfair_dismissal
jurisdiction:     EW
value_numeric:    null
value_text:       "Multipliers: under 22 = 0.5x; aged 22-40 = 1.0x; aged 41+ = 1.5x;
                   max 20 complete years; week's pay capped at weeks_pay_cap_gbp.
                   Computed in application code - do not hard-code the cap value."
unit:             null
description:      Reference row documenting the statutory basic award formula. The
                  monetary cap is in the weeks_pay_cap_gbp row. Multipliers are from
                  ERA 1996 basic award section  [VERIFY section number].
authority_type:   legislation
authority_ref:    Employment Rights Act 1996 basic award section  [VERIFY section number]
authority_url:    [VERIFY: section URL after confirming chapter and section number]
effective_from:   [VERIFY - date the basic award provisions in current form came into force]
effective_to:     null
is_prospective:   false
last_verified_at: [set at ingest time]
```

### Minimum basic award (£9,157) - OUT OF PHASE 1 SCOPE: do not seed as a general UD rule

The Employment Rights (Increase of Limits) Order 2026 (SI 2026/310) sets a **minimum basic award of £9,157** under ERA 1996 s.120. This figure is confirmed as of 6 April 2026.

**Critical scoping constraint:** this minimum applies only where dismissal is automatically unfair on specific grounds listed in s.120 — namely dismissals in contravention of ss.100(1)(a) or (b), 101A(d), 102(1), or 103. These are the health-and-safety, working-time, trustee, and employee-representative automatically-unfair categories. It is **not** a minimum for ordinary unfair dismissal generally.

**Do not seed this as a general `unfair_dismissal.*` rule.** Seeding it without the automatically-unfair scope would mislead the assessment engine into applying a floor that does not exist for ordinary UD claims.

**Phase 1 action:** note the figure for record. Do not create a rules row for it until the Phase 5 automatically-unfair claim types are built. If a row is added at that stage, the `claim_type` or `rule_key` must be scoped to the relevant automatically-unfair categories, not to `unfair_dismissal` generally.

---

## Section 4 - Rules Table Retrieval Logic

The application code retrieves the correct row for a given claim date:

```sql
SELECT value_numeric, value_text, authority_ref, authority_url
FROM   rules
WHERE  rule_key     = :rule_key
  AND  claim_type   = 'unfair_dismissal'
  AND  jurisdiction IN ('EW', 'GB')
  AND  is_prospective = false
  AND  effective_from <= :reference_date
  AND  (effective_to IS NULL OR effective_to >= :reference_date)
ORDER  BY effective_from DESC
LIMIT  1;
```

The `:reference_date` for unfair dismissal is the **effective date of termination (EDT)**, not today's date. This ensures the correct figures apply to the case being assessed, not the current date.

**Prospective rows** (`is_prospective = true`) are excluded from standard retrieval. They exist for future use when a commencement SI is published. At that point: set `is_prospective = false` on the new row, set `effective_to` on the preceding row, re-verify both dates.

---

## Section 5 - Limitation Date and Value Logic: Deterministic Arithmetic

**Source document:** `08a_DEADLINE_AND_VALUE_LOGIC.md` (folded in here). All logic is deterministic arithmetic only. Any test requiring judicial judgement (whether it was "not reasonably practicable" to present in time; how a tribunal would assess future loss; whether a dismissal is automatically unfair) is OUT of scope and must be surfaced as "needs a human", never computed.

**One hard rule:** the WASM module never embeds any rule value (period, cap, figure). All values come from the `rules` table at runtime and are passed in by the server. Per `05_WASM_SPEC.md`.

### 5.0 Authorities

- **Primary limit:** ERA 1996 s.111(2) - claim presented "before the end of the period of three months beginning with the effective date of termination." (Fetched and verified 2026-05-31.)
- **EC mandatory:** ETA 1996 s.18A. (Fetched and verified 2026-05-31.)
- **Stop-the-clock + floor:** ERA 1996 s.207B(3) and s.207B(4). (Fetched and verified 2026-05-31.)
- **(3)/(4) interaction:** Luton Borough Council v Haque UKEAT/0180/17/JOJ, [2018] UKEAT 0180_17_1204 (12 April 2018), **paragraph 17** (Naomi Ellenbogen DHC). Para 17: "Sub-section 207B(4) operates to extend the time limit as first modified by sub-section 207B(3) of the ERA." (3) and (4) apply sequentially: (3) first to get the extended date; (4) tested against the (3)-extended date, not the primary date. This is the judicially-approved counting method and is the `authority_ref` for the deadline WASM module.

### 5.1 Calendar-month helper (with month-end clamping)

```
add_calendar_months(d, n):
    y, m = normalise(d.year, d.month + n)    # carry months into years
    last = days_in_month(y, m)               # 28/29/30/31, leap-aware
    return date(y, m, min(d.day, last))
```

Required unit-test clamping cases: 30 Nov + 3m -> 28/29 Feb; 31 Jan + 1m -> 28/29 Feb; 31 Aug + 1m -> 30 Sep.

### 5.2 Inputs

| Input | Type | Source | Notes |
|---|---|---|---|
| `edt` | Date | User-supplied | Effective date of termination. Validate as a valid calendar date not in the future. |
| `time_limit_months` | Integer | `rules` table, `unfair_dismissal.time_limit_months` | Retrieved for the EDT using Section 4 query. |
| `ec_day_a` | Date or null | User-supplied | Date claimant first contacted ACAS for EC. |
| `ec_day_b` | Date or null | User-supplied | Date EC certificate issued. Must be >= `ec_day_a` if provided. |

### 5.3 Primary limit (A2)

ERA 1996 s.111(2): "before the end of the period of N months beginning with the effective date of termination." "Beginning with" means the EDT is day 1.

```
N               = rules["unfair_dismissal.time_limit_months"].value    # = 3 [from rules table]
base_limit_date = add_calendar_months(edt, N) - 1 day
```

Worked check: EDT 2026-03-14 -> +3m = 2026-06-14 -> -1 day = **2026-06-13**. Matches the practitioner "one day short of three months" rule.

**Month-end EDT:** where `edt.day` is 29/30/31 and the target month is shorter, the clamp in 5.1 applies. Mark the result `deadline_edge_case = true`; the honesty layer must tell the user the date is at an edge and to confirm with an adviser. Do not present it as certain.

### 5.4 EC gate: three states to handle explicitly (A3)

EC is mandatory for unfair dismissal (ETA 1996 s.18A), so Day A and Day B almost always exist. Handle each state:

```
if ec_day_a is null:                         # EC not started at all
    return { date: base_limit_date, flag: "EC_NOT_STARTED" }
    # Claim cannot be presented until EC is done. Surface: start EC immediately.

if ec_day_b is null:                         # EC started, certificate not yet received
    return { date: base_limit_date, flag: "EC_IN_PROGRESS" }
    # Cannot finalise or present until certificate issued.

if ec_day_a > base_limit_date:               # EC started after primary limit had already expired
    return { date: base_limit_date, flag: "EC_STARTED_AFTER_LIMIT", likely_out_of_time: true }
    # s.207B gives no extension. Late-claim relief (s.111(2)(b)) is a discretionary
    # judicial test -> route to human, do NOT compute.
```

Only proceed to 5.5 and 5.6 if all three gates pass (i.e. ec_day_a is not null, ec_day_b is not null, and ec_day_a <= base_limit_date).

### 5.5 s.207B(3) - stop the clock (A4)

The excluded period is "beginning with the day after Day A and ending with Day B." Day A itself is counted; Day A+1 to Day B inclusive are not.

```
conciliation_days = (ec_day_b - ec_day_a).days    # NO +1 (Day A is counted)
date_under_3      = base_limit_date + conciliation_days
```

### 5.6 s.207B(4) - the one-month floor, applied sequentially (A5)

**Authority: Luton BC v Haque UKEAT/0180/17/JOJ, paragraph 17 (ratio) and paragraph 26 (worked example).**

Para 17: "(4) operates to extend the time limit as first modified by (3)."
Para 26 establishes that (3) always runs first, but may produce no modification (e.g. where Day A = Day B, conciliation_days = 0 and date_under_3 = base_limit_date). (4) is then tested against whatever (3) produced — whether that is an extended date or the unchanged primary date. This is the critical distinction: (3) is not a prerequisite for (4); it is a mandatory first step that may happen to change nothing.

```
one_month_after_B = add_calendar_months(ec_day_b, 1)    # clamp per 5.1

# Step 1: (3) ALWAYS runs. It may be a no-op (conciliation_days = 0 when Day A = Day B).
# date_under_3 is the result of (3), which equals base_limit_date when (3) is a no-op.

# Step 2: (4) is tested against date_under_3 (i.e. the result of (3), whatever it is).
# Do NOT re-test against base_limit_date separately; para 17 says (4) tests
# "the time limit as first modified by (3)".
four_triggered = (ec_day_a <= date_under_3 <= one_month_after_B)

date_under_4    = one_month_after_B if four_triggered else date_under_3

# FINAL: the later of the two (para 17 sequential method).
limitation_date = max(date_under_3, date_under_4)
```

**Why max() still gives the right answer when (3) is a no-op (para 26 insight):**
When conciliation_days = 0, date_under_3 = base_limit_date. If that date falls within
[Day A, one_month_after_B], (4) triggers and sets limitation_date = one_month_after_B.
max(base_limit_date, one_month_after_B) = one_month_after_B. Correct.
The description above (not the arithmetic) is what changed: (3) is mandatory even when it
adds zero days; (4) is always tested against the (3) result.

**Worked check 1 - (3) governs, floor does not bite:**
```
EDT 2026-03-14 -> base 2026-06-13.
Day A 2026-04-01, Day B 2026-04-20. conciliation_days = 19.
date_under_3 = 2026-07-02. one_month_after_B = 2026-05-20.
date_under_3 (2 Jul) NOT in [1 Apr, 20 May] -> (4) not triggered.
Final = 2026-07-02.
```

**Worked check 2 - (4) floor bites (Day B after primary limit; Day A was before it — coherent):**
```
EDT 2026-01-10 -> base_limit_date 2026-04-09 (add 3m = 2026-04-10 - 1 day).
Day A 2026-04-05 [<= 2026-04-09: gate passes. EC started before limit].
Day B 2026-04-25 [> base - certificate arrived after limit expired; Day A was before it].
conciliation_days = 20. date_under_3 = 2026-04-29. one_month_after_B = 2026-05-25.
date_under_3 (29 Apr) IS in [5 Apr, 25 May] -> (4) triggered.
Final = max(29 Apr, 25 May) = 2026-05-25. Floor rescues the claim.
Gate checks Day A only, not Day B. Day B after the primary limit is the normal s.207B scenario.
```

**Worked check 3 - para 26 regression: (3) is a no-op, (4) still fires (REQUIRED TEST):**
```
EDT 2026-03-14 -> base 2026-06-13.
Day A = Day B = 2026-06-13. conciliation_days = (13 Jun - 13 Jun).days = 0.
date_under_3 = 2026-06-13 (unchanged from base). one_month_after_B = 2026-07-13.
date_under_3 (13 Jun) IS in [13 Jun, 13 Jul] -> (4) triggered.
Final = max(13 Jun, 13 Jul) = 2026-07-13.
This case: claimant contacts ACAS and receives certificate on the very last day of the
primary limit. (3) extends nothing. (4) still grants one month from Day B. Para 26.
```

**Worked check 3 - from Luton BC v Haque facts:**
```
EDT 20 Jun 2016 -> base 19 Sep 2016.
Day A 22 Jul 2016, Day B 22 Aug 2016.
conciliation_days = 31 -> date_under_3 = 20 Oct 2016.
one_month_after_B = 22 Sep 2016.
date_under_3 (20 Oct) not in [22 Jul, 22 Sep] -> (4) not triggered.
Final = 20 Oct 2016. Claimant presented 18 Oct 2016 - in time.
```

### 5.7 Return value

```
IF all EC gates passed (5.4) AND ec_day_b is not null:
    RETURN { date: limitation_date, flags: [] }
ELSE:
    RETURN the flagged response from 5.4
```

The WASM module returns a plain calendar date (YYYY-MM-DD) and any applicable flags. It does not apply working-day adjustments, the "not reasonably practicable" extension, or any tribunal procedural rules.

### 5.8 Edge cases (A6) - each a required test

| Scenario | Rule |
|---|---|
| Month-end EDT (29/30/31) | Clamp per 5.1; set `deadline_edge_case = true`; flag to user to confirm with adviser. |
| Leap year | Handled by leap-aware `days_in_month` in 5.1. |
| Weekend or bank holiday deadline | **Do NOT auto-roll to the next working day.** ET online presentation is available 24/7; the limitation date stands. Flag for legal confirmation; default = no roll-over. |
| Multiple respondents | Each respondent may have its own Day A / Day B. Compute per respondent; operative deadline may differ per respondent. |
| No EC certificate; EC-exempt matters | Out of common path. Flag and route to human. |
| `ec_day_b < ec_day_a` | Invalid input. Return validation error. |
| EDT in the future | Invalid input. Return validation error. |
| "Not reasonably practicable" late claim (s.111(2)(b)) | Discretionary judicial test. **Never computed.** Surface: "a tribunal may in limited cases allow a late claim, but it is not automatic and needs legal advice." |

### 5.9 Honesty-layer hooks (A7)

- If `limitation_date` is within a short window of today's date, surface urgency plainly and recommend immediate action.
- If `deadline_edge_case = true`, do not present the date as certain; state it is at a month-end edge and the user should confirm with an adviser.
- If any flag from 5.4 is set (EC_NOT_STARTED, EC_IN_PROGRESS, EC_STARTED_AFTER_LIMIT), do not present a final deadline; surface the appropriate action or human-route instead.
- Deadline is computed in WASM from `rules` values passed in by the server. WASM never embeds any figure.

---

## Section 5B - Compensatory Award: Two-Limb Cap (from 08a Part B)

### 5B.1 The rule (ERA 1996 s.124(1ZA))

The compensatory award is capped at the **lower** of:
- Limb A: the prescribed statutory cap (uprated annually by SI)
- Limb B: 52 x the claimant's **actual gross weekly pay**

**Critical:** the s.227 cap on "a week's pay" (£751 from the `rules` table) applies to the **basic award** calculation only. It does **NOT** cap Limb B. Limb B uses actual gross weekly pay, uncapped by s.227.

### 5B.2 Logic

```
stat_cap      = rules["unfair_dismissal.compensatory_cap_gbp"].value   # e.g. 123543 [from rules]
weekly_pay    = user.actual_gross_weekly_pay                           # ACTUAL, not s.227-capped

limb_b_52wk      = 52 * weekly_pay
compensatory_cap = min(stat_cap, limb_b_52wk)

# The award itself is assessed loss, THEN capped:
compensatory_award = min(assessed_loss, compensatory_cap)
```

### 5B.3 Worked checks (why both limbs matter)

- **Low earner, £350/wk gross:** Limb B = 52 x £350 = **£18,200**. min(£123,543, £18,200) = **£18,200**. The real ceiling is ~£18k. The tool must quote £18,200, not £123,543.
- **High earner, £3,000/wk gross:** Limb B = 52 x £3,000 = £156,000. min(£123,543, £156,000) = **£123,543**. Statutory cap binds.

Presenting only the statutory cap would systematically overstate the value for most claimants. This is the exact dishonesty this product exists to avoid.

### 5B.4 Reference date

The in-force cap is the one applicable at the EDT (effective date of termination), not today's date. Read from `rules` using `effective_from`/`effective_to` covering the EDT. Same `:reference_date = EDT` principle as Section 4's SQL.

### 5B.5 Cap disapplication (out of Phase 1 scope)

The compensatory cap does not apply where dismissal is automatically unfair under specified provisions (e.g. s.100 health and safety, s.103A protected disclosure). Those categories are Phase 5 scope. Do not implement. The `description` field on the cap rule row must note that the cap is disapplied for those categories, so the model never quotes a cap in a matter where it should not apply.

---

## Section 5C - Basic Award Formula (from 08a Part C)

The basic award uses the **s.227-capped** week's pay (unlike the compensatory Limb B):

```
wk_capped   = min(user.actual_gross_weekly_pay,
                  rules["unfair_dismissal.weeks_pay_cap_gbp"].value)   # e.g. 751 [from rules]

basic_award = sum over each complete year of service (max 20 years) of:
                  multiplier(age_in_that_year) * wk_capped

# multipliers: 0.5 (age under 22), 1.0 (22-40 inclusive), 1.5 (41 and over)
```

**Minimum basic award (£9,157 from SI 2026/310) does NOT apply to ordinary unfair dismissal.** It applies only to specified automatically-unfair categories under s.120. Do not seed it as a general `unfair_dismissal.*` rule. Seeding it generally would inflate every basic-award estimate. Defer to Phase 5 when those categories are built.

---

## Section 5D - Outstanding Verifications (08a Part E)

These must pass before any rules rows are written or WASM is built:

1. **s.207B(3)/(4) controlling authority confirmed.** Luton BC v Haque UKEAT/0180/17/JOJ recorded above. Verify that the "later of the two" / claimant-favourable construction in 5.6 is consistent with its ratio. If the authority requires a stricter construction, revise at that point.
2. **s.124(1ZA) Limb B confirmation.** Verify from the fetched s.124 and s.227 text that Limb B is "52 x a week's pay" and that s.227 does NOT cap that week's pay figure. (Fetched 2026-05-31: text confirms £123,543 cap under s.124(1ZA)(a); s.227 sets the basic-award cap at £751. The two provisions are separate.)
3. **Minimum basic award categories.** Confirm the exact list of automatically-unfair categories to which s.120's minimum applies, for Phase 5 use.
4. **No weekend roll-over.** ET online presentation is 24/7; confirm this or flag any contrary authority found.
5. **Month-end EDT treatment.** Confirm the clamped result is the correct legal interpretation, or keep `deadline_edge_case = true` as the conservative default pending confirmation.

---

## Section 6 - Point-in-Time and Prospective Law Flags

### 6.1 Employment Rights Act 2025

At the time of writing, this Act may amend at minimum: qualifying period, compensatory award cap, day-one rights scope, and the limitation period.

**Fetch protocol for prospective amendments:**
1. Fetch the `/prospective` version of each relevant section.
2. If it differs from the current in-force text, parse the commencement date from the amending instrument cited in the prospective version.
3. Create a sibling `rules` row with `is_prospective = true` and `effective_from = [commencement date]`.
4. Do not set `is_prospective = false` until a commencement SI is confirmed in force.

**VERIFY:** Check the current legislative status of the Employment Rights Act 2025 at the time Phase 1 runs. The legislation.gov.uk "changes and effects" tab for each section lists pending amendments.

### 6.2 Annual Uprating Protocol

When ingesting monetary figures:
1. Confirm the SI is in force (effective date must be <= ingestion date).
2. Set `effective_from` to the SI's in-force date.
3. Set `effective_to` on the preceding row to the day before `effective_from` (no gap, no overlap).
4. Set `effective_to` on the new row to `null` until a subsequent SI is published.

### 6.3 Scotland

ERA 1996 extends to Great Britain. Substantive unfair-dismissal rules (time limit, qualifying period, caps) are the same across England, Wales, and Scotland. Employment tribunals in Scotland sit in Edinburgh and Glasgow but apply the same law. Use `EW` and `S` as separate rows, or a single `GB` row, per schema convention. No Scotland-specific difference is assumed here. Flag if the fetch reveals one.

---

## Section 7 - Verification Checklist (complete before any row is written)

- [ ] ERA 1996 canonical URI confirmed via title resolution: ___________________
- [ ] ETA 1996 canonical URI confirmed via title resolution: ___________________
- [ ] Time-limit section fetched, "N months beginning with" wording confirmed: ___________________
- [ ] "Beginning with" arithmetic confirmed against statutory text: ___________________
- [ ] Qualifying period section fetched, figure confirmed: ___________________
- [ ] EC stop-the-clock section fetched, mechanic confirmed (Day A / Day B / excluded period / one-month floor): ___________________
- [ ] EC requirement section (ETA 1996) fetched, requirement confirmed: ___________________
- [ ] Compensatory cap section fetched, current figure from SI confirmed: ___________________
- [ ] Week's pay cap section fetched, current figure from SI confirmed: ___________________
- [ ] Current uprating SI identified, figure confirmed, effective date confirmed: ___________________
- [ ] Prospective ERA 2025 amendments checked (qualifying period, cap, time limit): ___________________
- [ ] Scotland-specific differences checked: ___________________
- [ ] Annual uprating protocol documented in runbook: ___________________

---

## Section 8 - What This Spec Does Not Cover

Out of scope for this seed spec:

- **Automatically unfair dismissal** categories (whistleblowing, health and safety, trade union activity, maternity/paternity). These carry no qualifying period and different remedies. Separate `rules` rows required.
- **Redundancy pay** (different formula, though uses the same week's pay cap).
- **Discrimination** (Equality Act 2010; no compensation cap, different time limits). Phase 5.
- **Wrongful dismissal** (breach of contract; different limitation periods).
- **Interim relief** (very short time limit for certain automatically-unfair claims).
- **"Not reasonably practicable" extension:** a merits question, not a deterministic rule.
- **Polkey reductions, contributory fault, ex gratia payments:** application logic, not `rules` rows.

---

*Specification complete. No application code written. No `rules` rows inserted. Phase 1 has not started. All values carry VERIFY flags. Awaiting review and approval before any build action.*
