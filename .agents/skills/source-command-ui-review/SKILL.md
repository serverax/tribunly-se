---
name: "source-command-ui-review"
description: "Review lawapp UI/UX  -  design-system consistency, accessibility, working buttons, real backend wiring, honest copy."
---

# source-command-ui-review

Use this skill when the user asks to run the migrated source command `ui-review`.

## Command Template

# /ui-review

Review the frontend against the UI/UX gates.

## Steps
1. `ui-design-system-agent` audits tokens, type hierarchy, spacing, focus, dark mode, AI-slop.
2. `product-ux-agent` checks journeys, legal-boundary copy, no overpromising.
3. `frontend-engineer` confirms every button works + maps to a real backend route; visible error/loading states; XSS-safe rendering.
4. Capture screenshots / Playwright flow per key page.
5. Score against `tasks/UI_UX_ACCEPTANCE.md`.

## Output
Per-page: pass/fail + screenshot + wired-route evidence + a11y notes.
