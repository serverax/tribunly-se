# UX Review v2 -- SA-6 (UI/UX Review), WO007

**Branch:** cc/convergence  
**Reviewer:** SA-6 (read-only)  
**Date:** 2026-07-08  

---

## 1. Assessment rendering order -- does the deadline dominate?

**Verdict: P2 -- Deadline is buried at position 4 of 10.**

The `renderAssessment()` function at `client/public/pages/assessment.html:241-252` appends cards in this order:

1. Viability card (`renderViabilityCard`) -- line 241
2. Tribunal checklist (`renderTribunalChecklist`) -- line 242
3. Save section (`renderSaveSection`) -- line 243
4. **Deadline card** (`renderDeadlineCard`) -- line 244
5. Weaknesses (`renderWeaknessSection`) -- line 245
6. Employer arguments (`renderEmployerSection`) -- line 246
7. Value range (`renderValueRange`) -- line 247
8. Next step (`renderNextStep`) -- line 248
9. Document section (`renderDocumentSection`) -- line 249
10. Handoff section (`renderHandoffSection`) -- line 250

The product promise is "understand your deadline" -- the deadline is the single most time-sensitive, actionable piece of information. It sits behind viability, a checklist, and a save-to-account CTA. On mobile, a user must scroll past three full cards before seeing their deadline. The deadline card should be position 1 or 2 (immediately after viability at most).

---

## 2. Expired limitation date renders as urgent warning, NOT neutral date

**Verdict: P1 -- Expired deadlines DO render as urgent. Implementation is correct but has a CSS class mismatch.**

The `renderDeadlineCard()` function at `client/public/pages/assessment.html:452-524` implements expired-date detection:

- **Line 459:** `const passed = dl.deadline_passed === true;`
- **Line 460-461:** `const isUrgent = passed || ['expired', 'critical', 'urgent'].includes(dl.urgency_level) || (dt && daysUntil(dt) <= 30);`
- **Line 464:** Card gets class `deadline-card urgent` when `isUrgent` is true.
- **Line 476:** Label text changes to `'Tribunal deadline  -  PASSED'` when `passed` is true.
- **Line 482-495:** A bold warning div is appended: either the backend's `deadline_warning` text (with `role="alert"` for screen readers), or a fallback `"Fewer than 30 days remain"`.

The `daysUntil()` helper at line 1240-1242 correctly returns a negative number for past dates, triggering the <=30 check.

**CSS class mismatch (P2):** The JS applies class `urgent` (line 464: `deadline-card urgent`), but the CSS defines `.deadline-urgent` (styles.css:354), not `.deadline-card.urgent`. The red gradient background (`linear-gradient(135deg, #c15536, #963c22)`) never activates. An expired deadline gets the standard navy gradient, not the intended red. The text says "PASSED" but the card colour does not change. This is a styling-only bug -- the urgency IS communicated via text, but the visual signal (red background) is broken.

**Intake deadline preview (correct):** The intake wizard at `client/public/pages/intake.html:399-401` also checks `daysLeft < 0` and applies CSS class `passed` with badge text `"Deadline passed"`. The intake CSS at line 23 defines `.deadline-badge.passed { background: #dc3545; color: #fff; }` -- this one works correctly.

---

## 3. 120-second loading state

**Verdict: P1 -- No timeout, no progress indication, no abort.**

After submit at `client/public/pages/intake.html:470-506`:

- The form is hidden (`form.style.display = 'none'`).
- A loading div appears (line 249-252) with a spinner and text: `"Analysing your case... This may take a moment."`.
- A single `fetch()` call to `/assess` is issued (line 474) with **no AbortController, no timeout, no progress bar, no elapsed-time counter**.
- If the backend takes 30, 60, or 120 seconds, the user sees an indefinite spinner with no feedback on whether the request is still alive.
- The only exit is a network error or server error, which triggers a bare `alert()` (line 503).

Missing:
- No `AbortController` with a timeout (e.g., 120s).
- No "still working..." message after 10-15 seconds.
- No progress indication (percentage, step labels, or elapsed time).
- No "this is taking longer than expected" warning after 30s.
- No retry button if the request appears stuck.

---

## 4. Weakness section visual weight

**Verdict: P3 -- Weaknesses have adequate visual prominence.**

The `renderWeaknessSection()` at `client/public/pages/assessment.html:586-606` renders weaknesses as `<li>` elements inside a `<ul class="weakness-list">`.

CSS at `client/public/css/styles.css:342`:
```
.weakness-list li {
  padding: .65rem .85rem;
  background: var(--warn-bg);
  border-left: 3px solid var(--warn);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  margin-bottom: .55rem;
  font-size: .95rem;
}
```

Each weakness item has: a warning-tinted background (`--warn-bg`), a 3px left border in warning colour (`--warn`), and rounded corners. This is visually distinct from plain text. The section header "Key weaknesses in your case" and subtext "These are the issues most likely to reduce your prospects or compensation" provide context. No icons are used, but the coloured border + background provide sufficient visual weight. Acceptable.

---

## 5. Intake wizard time estimate

**Verdict: P3 -- No time estimate on the intake page itself.**

The landing page at `client/public/index.html:68` promises:
- `"Start your case in 5 minutes"` (CTA button)
- `"About 5 minutes . Private & secure . No account needed to start"` (line 72)

However, the intake form at `client/public/pages/intake.html:54` says only:
- `"Tell us about your situation to receive an honest assessment of your claim."`

No "takes about 5 minutes" or "4 steps, ~5 min" indicator appears on the actual form page. Users arriving directly (bookmarks, back-navigation) have no time-cost framing. The 4-step wizard with progress bar partially compensates, but an explicit time estimate would reinforce the landing page promise.

**Also note:** The landing page CTA links to `/pages/case-intake.html` (line 68), while the actual intake wizard lives at `/pages/intake.html`. A separate `case-intake.html` file exists at `client/public/pages/case-intake.html` -- unclear whether this is a redirect or a duplicate. Potential dead link if `case-intake.html` does not redirect.

---

## 6. Error state differentiation

**Verdict: P2 -- Differentiated, but generic errors get only an alert().**

The assessment page at `client/public/pages/assessment.html` handles four distinct statuses:

| Status | UI Treatment | Lines |
|---|---|---|
| `not_supported` | Yellow-tinted card, "Outside our scope", link home | 137-159 |
| `missing_edt` | Yellow-tinted card, "Missing dismissal date", link to intake | 162-185 |
| `insufficient_grounding` | Assessment card with "Uncertain" badge, actionable suggestions, handoff section | 187-229 |
| `ok` | Full assessment rendering | 231+ |

The intake form at `client/public/pages/intake.html` differentiates `invalid_date` (lines 484-498) -- field-level errors shown inline, user returned to step 2.

**Gap:** A generic server error (HTTP 500, network failure, or any non-JSON response) at intake.html:502-505 produces only:
```
alert('Something went wrong: ' + err.message + '\nPlease try again.');
```
No styled error card, no recovery guidance, no trace ID. This is a bare browser alert for what may be a production outage. Compare with the assessment page's structured error state (lines 34-38) which at least shows a styled card.

The assessment page itself handles fetch failure (line 74-77) by showing the `#error-state` div, but this says "Your session may have expired" -- potentially misleading if the actual cause is a server error.

---

## 7. Floor delta

Floor: 1834->1919 passed (+85 from test discovery in container copy), 8->0 errors (ExternalLLMForbidden->skip, doc_type->fix, Dockerfile->skip), 44->58 skipped (+14 from gating fixes).

---

## Priority summary

| # | Finding | Priority | File:Line |
|---|---------|----------|-----------|
| 1 | Deadline card CSS class mismatch -- urgent red gradient never applies | P1 | assessment.html:464, styles.css:354 |
| 2 | No loading timeout/progress on /assess call (indefinite spinner) | P1 | intake.html:470-506 |
| 3 | Deadline card position 4 of 10 -- should be 1-2 | P2 | assessment.html:244 |
| 4 | Generic server error is a bare alert(), not a styled state | P2 | intake.html:502-505 |
| 5 | No time estimate on intake form page (landing says "5 minutes") | P3 | intake.html:54 |
| 6 | Weakness section styling is adequate | P3 (ok) | styles.css:342 |

---

*End of review. All observations from tree at F:\lawapp-restore, branch cc/convergence.*
