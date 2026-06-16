# SA-007 Frontend UI/UX Audit (honest, command-based)

**Architecture:** static HTML/JS/CSS client in `client/public/`, served by the FastAPI backend
(`backend/api/main.py`: mounts `/css`,`/js`; serves `index.html` and `/pages/{page_name}`). No SPA
framework/build step. A design system exists: `client/public/design-tokens.json`,
`client/public/css/styles.css`, `client/public/design-preview.html`.

## Pages (client/public/pages/)
index.html (landing) · login.html · register.html · dashboard.html · intake.html · assessment.html ·
constructive_dismissal.html · case_detail.html · saved_case.html · success.html · cancel.html.

## Wiring status  -  GOOD (not mock)
Frontend JS/pages call REAL backend routes (grep proof in `frontend-backend-wiring-map.md`):
`/auth/register`, `/auth/token`, `/auth/me`, `/assess`, `/api/workflows/constructive-dismissal`,
`/rules/{claimType}`, `/cases`, `/documents/generate`, `/handoff/leads`, `/api/payment/create-session`.
No `mock`/`fake`/`dummy`/hardcoded-answer markers found in `client/public/js` or `pages`.
→ This is NOT a mock-only frontend; the core flows hit real endpoints.

## FINDINGS / GAPS (honest)
1. **FAKE build/lint/test gates (must fix):** `client/package.json` `build`/`lint`/`test` are
   `echo "…" && exit 0` stubs (see `frontend-build-proof.txt`). They assert success without doing
   anything  -  a constitution violation (`echo PASS`). Real check is `npm run e2e` (Playwright),
   which needs a running backend. CI must not treat the stubs as a passing frontend gate.
2. **Citation / deadline / trace display  -  needs verification in the live answer view.** The brain
   returns `trace_id`, RAG sources, and CitationGuard fields; `assessment.html` makes 5 fetch calls.
   A render-level check (Playwright against the live backend) is required to PROVE the answer view
   shows citations, deadline/risk warnings, and trace ID. Not yet rendered-proven.
3. **Design depth / accessibility / responsive**  -  tokens + a preview page exist, but a per-page
   a11y pass (semantic headings, input labels, focus states, contrast) and responsive breakpoints
   need a real review pass + Playwright/axe evidence. Not yet proven.
4. **Backend route coverage**  -  pages cover auth, assessment, constructive-dismissal, cases,
   documents, handoff, payment. A `dashboard`/workspace "module entitlement" call was not observed in
   JS grep; verify the dashboard loads real workspace/entitlement data vs static markup.

## VERDICT
`SA-007 FAIL  -  frontend is real-wired (good) but not yet upgraded/proven`: fake build gates remain,
and citation/deadline/trace rendering + a11y/responsive are not yet render-proven. Real wiring to
backend routes is in place (no mock-data product path detected). Next: replace stub gates with real
Playwright e2e, render-prove the answer view (citations/deadline/trace), run an a11y/responsive pass.
