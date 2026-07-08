# Frontend Complete Report

Generated: 2026-07-08
Branch: `codex/backend-complete`

## Scope

Stage 2 of Work Order 004 was completed in `client/public/` only. The Next.js scaffold was left untouched.

## What Changed

1. Beta honesty for solicitor referrals:
   - `assessment.html`, `case_detail.html`, `saved_case.html`, and `escalation.html` now show an honest controlled-beta descope message instead of a live referral form.
   - `app-shell.js` hides the Escalation nav entry when referral handoff is disabled in beta.
   - `beta-scope.js` is the single source of truth for the `handoffReferrals` beta flag and the user-facing notice copy.

2. Footer duplication fix:
   - `auth.js` and `app-shell.js` no longer inject a second dark footer when a page already has one.
   - Responsive screenshot evidence now shows one footer per audited page.

3. Honesty sweep:
   - Removed all `guarantee` / `guaranteed` wording from `client/public/`.
   - `rg -n "guarantee|guaranteed" client/public` now returns zero hits.

4. Deadline tracker UX:
   - `deadlines.html` now loads `deadline.js` and performs a live in-browser preview from server-supplied rule values.
   - The note on the page now states that reminder delivery remains descoped in controlled beta.

## Responsive Matrix

Audited screens:

- landing
- intake
- diagnosis result
- workspace (auth gate / anonymous path)
- payment entry surface
- download surface
- escalation surface

Widths audited:

- 360
- 390
- 768
- 1024
- 1440

Evidence files:

- screenshots: `reports/frontend_snaps/*.png`
- machine-checked overflow matrix: `reports/frontend_responsive_matrix.json`

Observed result:

- every audited page in the matrix reported `overflowX=false`
- every audited page reported `footerCount=1`
- every audited page reported `hasLegalNotice=true`

## Accessibility / WCAG Notes

- Keyboard affordances already present and retained: skip links, labeled mobile menu buttons, labeled auth and intake form fields.
- No new P1 keyboard or label blockers were introduced.
- Workspace anonymous path still lands on login rather than restoring case state, which aligns with the authenticated-only resume rule.

## Coverage / Honesty Checks

- `Not a law firm / Not legal advice` remains present on the audited surfaces.
- Solicitor introductions are explicitly marked unavailable during controlled beta.
- Reminder delivery is explicitly labeled future / descoped rather than silently absent.

## Floor

Final branch floor after Stage 2:

- `1827 passed, 63 skipped, 6 warnings in 432.90s (0:07:12)`
