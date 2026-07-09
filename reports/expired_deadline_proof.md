# Expired Deadline Rendering Proof

**Phase C T1 mandatory (a):** "the expired-limitation-date case renders as an urgent warning with out-of-time guidance, never a neutral date"

## Backend Evidence (live /assess response)

```
POST /assess with edt=2025-01-15 (450 days ago), use_model=false

deadline_info:
  limitation_date: "2025-04-14"
  source: "rules"
  authority: "ERA 1996 s.111(2)"
  deadline_passed: true
  days_remaining: -450
  urgency_level: "expired"
  deadline_warning: "⚠ This deadline appears to have PASSED (450 days ago, on 2025-04-14).
    Out-of-time claims are only accepted in limited circumstances - seek advice from
    ACAS or a solicitor IMMEDIATELY if you still wish to claim."
```

## Frontend Rendering (assessment.html code audit)

1. **Line 468:** `const passed = dl.deadline_passed === true;` → `true`
2. **Line 469-470:** `isUrgent` → `true` (passed=true OR urgency_level='expired')
3. **Line 473:** Card class = `deadline-card deadline-urgent` → activates red gradient CSS (styles.css:354: `background: linear-gradient(135deg, #c15536 0%, #963c22 100%)`)
4. **Line 485:** Label = `"Tribunal deadline - PASSED"`
5. **Line 491-497:** Backend `deadline_warning` text rendered with `role="alert"` (screen reader announcement)
6. **Line 530:** Additional guidance: `"This deadline appears to have passed. Late claims are accepted only in exceptional circumstances (s.111(2A) ERA 1996). Seek legal advice immediately — a solicitor can assess whether a 'not reasonably practicable' or 'just and equitable' extension argument applies to your case."`
7. **Line 531:** Card gets `role="alert"` attribute

## Rendering Order

Deadline card is rendered at **position 1** (first card, before viability). Changed from position 4 in Phase C T1 commit.

## CSS Class Fix

JS now uses `deadline-urgent` (was `urgent` — CSS mismatch fixed in Phase C T1 commit 16797ae).

## Verdict

An expired deadline renders as:
- Red gradient background (`.deadline-urgent`)
- "PASSED" label
- Warning text with days-ago count
- Out-of-time legal guidance citing s.111(2A) ERA 1996
- ARIA `role="alert"` for accessibility
- Position 1 (first card user sees)

It never renders as a neutral date.
