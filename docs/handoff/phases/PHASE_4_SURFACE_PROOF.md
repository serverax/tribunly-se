# PHASE 4 - SURFACE PROOF (RESPONSIVE, ACCESSIBILITY, PERSISTENCE, NOTICES)

**Owner of this phase:** CC1.
**Precondition:** PHASE_3 hard exit signed.
**Scope:** the static `client/public/` beta surface ONLY. The Next.js scaffold is unwired - do not audit it, do not build on it.
**Why this phase exists:** mobile was claimed working but never re-proven; accessibility was never audited; workspace persistence and deadline live-recalc are unverified. "Responsive website" is a launch requirement, not a nice-to-have.

## Read first
1. `docs/handoff/LAWAPP_RESET_AND_EXECUTION_PLAN.md` - Gate 4 section
2. `05_WASM_SPEC.md` - deadline calculator acceptance criteria
3. `reports/BETA_GATE_STATUS.md`

## Task 1 - Responsive audit
Test every beta screen (landing, intake, diagnosis result, payment, document download, account/workspace) at widths: **360, 390, 768, 1024, 1440**.
- Screenshot evidence per screen per width.
- Fix every break (overflow, unreadable text, dead buttons, broken layout). Each fix gets before/after evidence.

## Task 2 - WCAG 2.2 AA audit
- Keyboard navigation through the full journey, focus order, visible focus states.
- Contrast ratios on all text and interactive elements.
- Form labels, error messaging, alt text.
- Fix P1s (journey-blocking for keyboard/screen-reader users) now; log P2/P3 with severity to `reports/` for post-beta.

## Task 3 - Workspace persistence
Save a case, close the session, return, and prove state intact: facts, assessment, key dates, payment status. Paste the evidence.

## Task 4 - Deadline tracker
- Live WASM recalculation on date edit proven working (rule VALUES fetched from the server `rules` table; arithmetic client-side per the WASM spec).
- Reminder path: proven working, OR formally descoped from beta with an honest label on the surface saying so. No silent absence.

## Task 5 - Legal notices and honesty sweep
- "Not a law firm / not legal advice" notice present on every beta surface - list each surface with evidence.
- Grep the entire surface for guarantee language ("win your case", "guaranteed", outcome promises) - must return zero hits. Paste the grep.
- Coverage label honest and visible: unfair dismissal only, beta.
- Generated-document marking (self-help draft) visible pre- and post-download.

## STOP conditions
Universal set applies. Additional: no redesigns, no new components beyond what a fix requires. This is verification and repair, not a facelift.

---

## HARD EXIT - PHASE 4
All items proven with evidence in `reports/BETA_GATE_STATUS.md` before PHASE_5 may be opened:

- [ ] Full width-matrix screenshots archived; zero unfixed layout breaks
- [ ] WCAG audit complete; P1s fixed with evidence; P2/P3 logged with severity
- [ ] Workspace persistence proven across sessions
- [ ] Deadline live-recalc proven; reminders proven or honestly descoped with a visible label
- [ ] Notices proven on every surface; guarantee-language grep returns zero
- [ ] Floor still green after all fixes (paste summary line)
- [ ] `git diff --stat` proves lane isolation

**OWNER EXIT APPROVAL:** ____________  **Date:** ____________

No one opens PHASE_5_BETA_SHIP.md until signed. PHASE_5 is owner-executed.
