# 08a - Corrected Deadline & Value Logic

**Type:** Specification correction. Folds into `08_UNFAIR_DISMISSAL_SEED_SPEC.md`, replacing Section 5 (deadline arithmetic) and adding the compensatory/basic award logic that was under-specified.
**Project root:** `F:\lawapp`
**Pairs with:** `03_DATABASE_DESIGN.md` (`rules` table), `04_RAG_REASONING_SPEC.md` (deterministic-facts rule), `05_WASM_SPEC.md` (deadline calc runs client-side).

**Status of values:** every monetary figure and period below is read from the `rules` table at runtime, keyed to the reference date. The figures named in worked examples are the agent's live-API fetches of 2026-05-31 (SI 2026/310). They are NOT independently confirmed in this document. The logic is the deliverable; the numbers remain owned by the `rules` table.

**One hard rule for the whole of this document:** the deadline and value calculations are deterministic arithmetic only. Any test that requires judgement (whether it was "not reasonably practicable" to present in time; how a tribunal would assess future loss; whether a dismissal is automatically unfair) is OUT of scope for this logic and must be surfaced as "needs a human", never computed.

---

## PART A - Limitation date (replaces Section 5)

### A0. Authorities this logic implements
- **Primary limit:** ERA 1996 s.111(2) - claim presented "before the end of the period of three months beginning with the effective date of termination." (Verified: s.111 text fetched.)
- **EC mandatory:** ETA 1996 s.18A. (Verified.)
- **Stop-the-clock + floor:** ERA 1996 s.207B(3) and s.207B(4). (Verified: s.207B text fetched.)
- **(3)/(4) interaction:** governed by EAT case law, **not** the bare statute. The leading authority is believed to be *Luton Borough Council v Haque* (EAT). **VERIFY the exact neutral citation and the precise ratio before implementation** and record it as the `authority_ref` for the deadline WASM module. Until verified, implement the claimant-favourable "later of the two" rule in A5, which cannot disadvantage a claimant whichever way the precise mechanics fall.

### A1. Calendar-month helper (with month-end clamping)
```
add_calendar_months(d, n):
    # advance d by n calendar months, clamping to the last valid day of the target month
    y, m = normalise(d.year, d.month + n)        # carry months into years
    last = days_in_month(y, m)                   # 28/29/30/31, leap-aware
    return date(y, m, min(d.day, last))
```
Clamping cases (must be unit-tested): 30 Nov + 3m -> 28/29 Feb; 31 Jan + 1m -> 28/29 Feb; 31 Aug + 1m -> 30 Sep.

### A2. Primary limit
```
N = rules["unfair_dismissal.time_limit_months"].value     # = 3 [from rules]
base_limit_date = add_calendar_months(edt, N) - 1 day
```
Worked check: EDT 2026-03-14 -> +3m = 2026-06-14 -> -1 day = **2026-06-13**. (Matches the practitioner "one day short of three months" rule.)

> **Month-end EDT is an edge case.** Where `edt.day` is 29/30/31 and the target month is shorter, the clamp in A1 governs, but the correct treatment of "beginning with" a month-end date has attracted argument. FLAG any month-end EDT: compute the clamped date, but mark the result `deadline_edge_case = true` so the honesty layer tells the user the date is at an edge and to confirm with an adviser. Do not present it as certain.

### A3. EC gate and preconditions (run before any extension)
EC is mandatory for unfair dismissal, so in almost all real cases Day A and Day B exist. Handle the states explicitly:
```
if not ec_started:                         # no Day A
    return { date: base_limit_date, flag: "EC_NOT_STARTED" }
    # Claim cannot be presented at all until EC is done. Surface: start EC now.

if ec_day_b is null:                       # EC started, certificate not yet received
    return { date: provisional, flag: "EC_IN_PROGRESS" }
    # Cannot finalise or present until certificate issued.

if ec_day_a > base_limit_date:             # EC started after primary limit already gone
    return { date: base_limit_date, flag: "EC_STARTED_AFTER_LIMIT", likely_out_of_time: true }
    # s.207B gives no extension once the limit has expired. Late-claim relief (s.111(2)(b))
    # is a discretionary judicial test -> route to human, do NOT compute.
```

### A4. s.207B(3) - stop the clock
The excluded period is "beginning with the day after Day A and ending with Day B." Day A itself is counted; Day A+1 to Day B inclusive are not.
```
conciliation_days = (ec_day_b - ec_day_a).days      # NO +1  (this was the bug)
date_under_3 = base_limit_date + conciliation_days
```
This is the corrected formula. The previous `+ 1` wrongly excluded Day A.

### A5. s.207B(4) - the one-month floor, and the (3)/(4) interaction
(4) provides a minimum: if the limit would expire in the window starting at Day A and ending one month after Day B, it expires instead at the end of that window.
```
one_month_after_B = add_calendar_months(ec_day_b, 1)   # clamp per A1

# (4) is triggered generously (claimant-favourable): if EITHER the primary limit
# OR the (3)-extended date falls within [Day A, one_month_after_B].
four_triggered = within(base_limit_date, ec_day_a, one_month_after_B)
              or within(date_under_3,   ec_day_a, one_month_after_B)

date_under_4 = one_month_after_B if four_triggered else date_under_3

# FINAL: the later of the two. max() guarantees we never give less than (3),
# and awards the (4) floor when it is more generous.
limitation_date = max(date_under_3, date_under_4)
```
> This "later of the two" construction is deliberately claimant-favourable and is robust to the precise statutory reading. Once *Haque* (or the controlling authority) is verified, confirm this matches its ratio; if the authority requires a stricter construction, change it then, with the case as `authority_ref`.

Worked checks:
- **(3) governs:** EDT 2026-03-14 -> base 2026-06-13. Day A 2026-04-01, Day B 2026-04-20. `conciliation_days = 19`. `date_under_3 = 2026-07-02`. `one_month_after_B = 2026-05-20`. base (13 Jun) not in [1 Apr, 20 May] and date_under_3 (2 Jul) not in it -> (4) not triggered. **Final = 2026-07-02.**
- **(4) floor bites:** base 2026-04-10. Day A 2026-04-05, Day B 2026-04-25. `conciliation_days = 20` -> date_under_3 = 2026-04-30. `one_month_after_B = 2026-05-25`. base (10 Apr) is in [5 Apr, 25 May] -> (4) triggered -> date_under_4 = 2026-05-25. **Final = max(30 Apr, 25 May) = 2026-05-25.** The floor correctly gives the claimant more time.

### A6. Edge cases (each a required test)
| Case | Rule |
|---|---|
| Month-end EDT | Clamp (A1); set `deadline_edge_case`; flag to user. |
| Leap year | Handled by leap-aware `days_in_month`. |
| Weekend / bank holiday deadline | Do NOT auto-roll to the next working day. ET online presentation is available 24/7, so the limitation date stands. FLAG for legal confirmation; default = no roll-over. |
| Multiple respondents | Each respondent can have its own Day A / Day B. Compute per respondent; the operative deadline per respondent may differ. |
| Second / no EC certificate, EC-exempt matters | Out of the common path; flag and route to human rather than guessing. |
| "Not reasonably practicable" late claim (s.111(2)(b)) | DISCRETIONARY judicial test. Never computed. Surface: a tribunal may in limited cases allow a late claim, but it is not automatic and needs advice. |

### A7. Honesty-layer hooks (ties to the governance gate)
- If `limitation_date` is within a short window of today, or `deadline_edge_case = true`, or any A3 flag is set, the displayed output must state the urgency/uncertainty plainly and recommend immediate action, not present a clean certain date.
- The deadline is computed in WASM from `rules` values passed in by the server. WASM never embeds the period or any figure (per `05_WASM_SPEC.md`).

---

## PART B - Compensatory award cap (the value-honesty fix)

### B0. The rule the seed spec was missing
ERA 1996 s.124(1ZA): the compensatory award is capped at the **lower** of:
- (a) the prescribed amount (the uprated statutory cap), and
- (b) **52 x a week's pay** of the claimant.

**Critical:** the ERA 1996 s.227 cap on "a week's pay" (the basic-award cap, e.g. £751 [from rules]) does **NOT** apply to limb (b). Limb (b) uses the claimant's **actual gross weekly pay, uncapped**. Storing a single "compensatory cap = £123,543" row models only limb (a) and overstates value for most ordinary claimants - the exact dishonesty this product exists to avoid.

### B1. Logic
```
stat_cap   = rules["unfair_dismissal.compensation_cap_compensatory"]
                .value_for(reference_date)          # e.g. 123543 [from rules, in force at reference_date]
weekly_pay = user.actual_gross_weekly_pay           # ACTUAL, not s.227-capped

limb_b_52wk      = 52 * weekly_pay
compensatory_cap = min(stat_cap, limb_b_52wk)

# the award itself is assessed loss (past + future net loss, etc.), THEN capped:
compensatory_award = min(assessed_loss, compensatory_cap)
```

### B2. Worked checks (why this matters)
- **Low earner, £350/wk gross:** limb_b = 52 x 350 = **£18,200**. min(123,543, 18,200) = **£18,200**. The real ceiling is ~£18k, not £123,543. The tool must quote £18,200.
- **High earner, £3,000/wk gross:** limb_b = 52 x 3,000 = £156,000. min(123,543, 156,000) = **£123,543**. Statutory cap binds.

### B3. Reference date, not today
The in-force cap is the one applying at the relevant date (effective date of termination), not the date the user runs the tool. Read it from `rules` via `effective_from`/`effective_to` covering the EDT. This is the same `:reference_date = EDT` principle already in the spec's SQL.

### B4. Cap disapplication (note, out of Phase 1 scope)
The compensatory cap does not apply where the dismissal is automatically unfair under specified provisions (e.g. s.100 health and safety, s.103A protected disclosure). Those categories are out of Phase 1 scope; do not implement them, but the rule row's `description` should note the cap is disapplied for them so the model never quotes a cap in a matter it shouldn't.

---

## PART C - Basic award and the minimum-award scoping fix

The basic award is separate and uses the **s.227-capped** week's pay:
```
wk_capped   = min(user.actual_gross_weekly_pay, rules["...week_pay_cap"].value)   # e.g. 751 [from rules]
basic_award = sum over each complete year of service (max 20) of
                 multiplier(age_in_that_year) * wk_capped
# multipliers: 0.5 (age <22), 1.0 (22-40 inclusive), 1.5 (41+)
```
**Minimum basic award (e.g. £9,157 [from rules]) does NOT apply to ordinary unfair dismissal.** It applies only to specified automatically-unfair categories (s.120). Do not seed it as a general unfair-dismissal rule; scope it to those categories, which are out of Phase 1 scope. Seeding it generally would inflate every basic-award estimate.

---

## PART D - Required changes to the `rules` rows and the spec

1. **Replace** Section 5.3 Component A formula: `conciliation_days = (ec_day_b - ec_day_a).days` (no `+1`).
2. **Add** the s.207B(4) floor and the "later of the two" final step (A5) to Section 5.
3. **Replace** the single compensatory-cap row's usage with the lower-of-two logic (B1); the cap row stays, but the calculation that consumes it must apply limb (b) with uncapped actual pay.
4. **Re-scope** the minimum-basic-award row to its automatically-unfair categories (C); flag out of Phase 1 scope.
5. **Record** the verified `Haque` (or controlling) citation as `authority_ref` for the deadline module once confirmed.

---

## PART E - Verify before implementing (must pass before any code or row)
1. Confirm the s.207B(3)/(4) controlling authority - exact neutral citation and ratio. Confirm the "later of the two" construction is consistent with it.
2. Confirm s.124(1ZA) limb (b) is "52 x a week's pay" and that s.227 does NOT cap limb (b) - against the fetched s.124 and s.227 text.
3. Confirm the minimum basic award provision and the exact list of categories it applies to (s.120 / related).
4. Confirm the no-weekend-roll-over position for online ET presentation, or flag the contrary authority if found.
5. Confirm month-end EDT treatment, or keep the `deadline_edge_case` flag as the conservative default.

No `rules` rows are written and no WASM is built until items 1-5 are reported back and approved.
