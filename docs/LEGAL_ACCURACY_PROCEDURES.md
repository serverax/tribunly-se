# Legal Accuracy Procedures

**Owner:** must be a named human — this cannot be tribal memory or an agent task.
**Frequency:** monthly check at minimum; immediately on any new employment-law news.

These procedures exist because the safety of the deadline product depends on a human
keeping the `rules` table current. An agent cannot know when a commencement SI has
been published; only a person monitoring the statute book can.

---

## 1. Promoting a prospective rules row to current (CRITICAL)

When a commencement SI is published for ERA 2025 provisions, the following rows
must be updated in the `rules` table before the product reflects the new law.
Getting this wrong in either direction is dangerous:
- **Flip too early:** users are told they have longer than they do — claims are lost.
- **Never flip:** users are permanently given the old (shorter or capped) position.

### Rules rows that need promotion when commencement SIs arrive

| rule_key | value | Waits for | Action on commencement |
|---|---|---|---|
| `unfair_dismissal.time_limit_months` | 6 months | ERA 2025 s.152 commencement SI | 1. Set `effective_to = <commencement date - 1 day>` on the 3-month row. 2. Set `is_prospective = false` and `effective_from = <commencement date>` on the 6-month row. |
| `unfair_dismissal.qualifying_period` | 6 months | ERA 2025 s.25 commencement SI | Same pattern: close the 2-year row, promote the 6-month row. |
| `unfair_dismissal.compensatory_cap_amount` | uncapped | ERA 2025 s.25 commencement SI | Close the £123,543 row (`effective_to = <date - 1>`), promote the `uncapped` row. Also verify whether s.124(1ZA)(b) 52-week cap survives — if removed, close that row too. |

### How to check for commencement SIs

1. Search legislation.gov.uk for SIs with "Employment Rights Act 2025" and "Commencement":
   `https://www.legislation.gov.uk/search?title=Employment+Rights+Act+2025+Commencement`
2. Check the government's ERA 2025 implementation timeline page on gov.uk.
3. Sign up for legislation.gov.uk email alerts for ERA 2025 (ukpga/2025/36).

### The SQL to run when promoting

```sql
-- Step 1: close the current row
UPDATE rules
SET effective_to = '<commencement_date - 1 day>',
    last_verified_at = now()
WHERE rule_key = '<rule_key>'
  AND is_prospective = false
  AND effective_to IS NULL;

-- Step 2: promote the prospective row
UPDATE rules
SET is_prospective = false,
    effective_from = '<commencement_date>',
    last_verified_at = now()
WHERE rule_key = '<rule_key>'
  AND is_prospective = true
  AND value_numeric = <new value>;  -- sanity check: confirm the right row

-- Step 3: verify — should return exactly one active row per rule_key
SELECT rule_key, value_numeric, value_text, effective_from, effective_to, is_prospective
FROM rules
WHERE rule_key = '<rule_key>'
ORDER BY effective_from;
```

> **After running:** re-run `python -m ingestion.freshness.report` and verify
> the rules table still shows all sources fresh. Run the Phase 2 regression test
> suite (when built) to confirm the change produces correct deadline outputs.

---

## 2. Annual April uprating (week's pay cap and compensatory cap)

Each April the Employment Rights (Increase of Limits) Order uprates the figures.
Usually published in February/March, in force from 6 April.

When the new Order is published:

1. Fetch `https://www.legislation.gov.uk/uksi/<year>/<SI number>/schedule/made`
   and confirm the new figures for s.227(1) (week's pay) and s.124(1ZA) (comp cap).
2. Add a new row to `rules` for each uprated figure with the new `effective_from = <6 Apr>`.
3. Set `effective_to = <5 Apr>` on the outgoing row.
4. Update `ingestion/rules/seed.py` with the new rows so future re-seeds are correct.
5. **Never hardcode the derived maximum basic award** (20 × 1.5 × week's pay cap).
   It is computed from the formula row — it will self-update when the cap row is current.

---

## 3. ACAS Code of Practice — edition check

The ACAS Code of Practice on Disciplinary and Grievance Procedures (March 2015,
as at 2026-05-29) is occasionally revised.

- Check `https://www.acas.org.uk/acas-code-of-practice-on-disciplinary-and-grievance-procedures`
  at each ingestion run. The ingest script flags if the page text does not mention "March 2015".
- If a new edition appears: update `ACAS_CODE_EDITION` in `ingestion/config.py`,
  re-run `python -m ingestion.acas.ingest`, then re-embed `acas_guidance`.

---

## 4. EC max duration — authority still to confirm

`unfair_dismissal.ec_max_duration_weeks` is seeded at 12 weeks from 2025-12-01 with
`authority_ref = "VERIFY — ..."`. Before this value is used in any user-facing deadline
output, confirm the exact statutory authority. The value was flagged in external review;
primary source verification is outstanding.

---

*This document is a written procedure, not a code comment. Keep it current as the law
changes. The product's honesty guarantee depends on it.*
