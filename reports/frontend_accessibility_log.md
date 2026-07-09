# Frontend Accessibility Log

Generated: 2026-07-08
Branch: `codex/backend-complete`

## Audit Scope

Surfaces reviewed in the closure pass:

- payment surface on `client/public/pages/assessment.html`
- download surface on `client/public/pages/case_detail.html`
- workspace persistence path on `client/public/pages/workspace.html`
- deadline tracker on `client/public/pages/deadlines.html`

Keyboard and small-screen render checks remained free of new P1 blockers in this pass.

## Findings

| Severity | Surface | Finding | Evidence |
| --- | --- | --- | --- |
| P2 | `client/public/pages/deadlines.html` | Live recalculation updates the visible deadline and note text, but the updated explanation text is not announced through an `aria-live` region. Screen-reader users can miss that the rule-backed preview changed after editing the date. | `#dl-note` is a plain `<p>` with no live-region semantics; see `reports/frontend_deadline_recalc_proof.json` |
| P2 | `client/public/pages/case_detail.html` | Download/payment failures still surface through `alert(...)` dialogs instead of a persistent inline status region. This is usable, but it is abrupt and gives weaker context to assistive technology than an in-flow error/status container. | `downloadDoc()` in `client/public/pages/case_detail.html` |
| P3 | `client/public/pages/case_detail.html` | The top legal notice uses `role="alert"` even though it is static page chrome, so assistive tech may announce it as an urgent interruption on every visit. This is more forceful than necessary for a persistent notice. | top-level `.legal-notice` block in `client/public/pages/case_detail.html` |
| P3 | `client/public/pages/saved_case.html` | The saved-case legal notice also uses `role="alert"` for static disclosure copy. The content is important, but it does not need interruptive announcement semantics. | top-level `.legal-notice` block in `client/public/pages/saved_case.html` |
| P3 | `client/public/pages/success.html` | The success-state checkmark is a standalone emoji glyph with no separate accessibility text beyond the heading. The page remains understandable, but the decorative symbol should ideally be hidden from assistive tech. | success icon block in `client/public/pages/success.html` |

## WO009 Fixes Applied

| Item | Fix | File |
| --- | --- | --- |
| P2-1 | Added `aria-live="polite" aria-atomic="true"` to `#dl-note` | `client/public/pages/deadlines.html:34` |
| P2-2 | Replaced 3 `alert()` calls with inline `showDocStatus()` status region | `client/public/pages/case_detail.html` |
| P3-1 | `role="alert"` → `role="note"` on static legal notice | `client/public/pages/case_detail.html:11` |
| P3-2 | `role="alert"` → `role="note"` on static legal notice | `client/public/pages/saved_case.html:11` |
| P3-3 | `role="alert"` → `role="note"` + `aria-hidden="true"` on emoji | `client/public/pages/success.html:11,22` |

## WO009 Plain-English / Jargon Sweep

Grep patterns: `EDT`, `ACAS EC`, `TULRCA`, `pursuant`, `notwithstanding`, `hereinafter`.

| Fix | File | Change |
| --- | --- | --- |
| Label jargon | `intake.html:86` | "Dismissal date (EDT)" → "Dismissal date" (hint already explains) |
| Label jargon | `deadlines.html:30` | "ACAS EC start" → "ACAS early conciliation start" |
| Label jargon | `case-intake.html:55` | "ACAS EC" → "ACAS early conciliation" |
| UI text | `assessment.html:559,563` | "ACAS EC stop-clock" → "ACAS early conciliation stop-clock" |
| UI text | `case-components.js:153` | "ACAS EC" → "ACAS early conciliation" in timeline steps |
| Validation msg | `document_preview.js:115` | "Date your employment ended (EDT)" → "Date your employment ended" |

**Logged but not changed** (appropriate statutory citations in context):
- `assessment.html:537` — "s.111(2A) ERA 1996" in late-deadline warning (correct legal citation)
- `deadlines.html:132` — "ERA 1996 s.111(2)" in source attribution
- `compensation.html:139` — "ERA 1996 s.227(1)" in authority display
- Backend `assess_logic.py` — "TULRCA 1992 s.152" in internal auto-unfair mapping
- Backend `timeline.py` — "EDT" and "ACAS EC" in trace/debug labels (not user-facing)

## P1 Summary

- No journey-blocking keyboard, label, or focus-order regressions were found in the closure pass.

## Guarantee Language Sweep

Command:

```powershell
rg -n "guarantee|guaranteed" client/public
```

Result:

- zero hits
