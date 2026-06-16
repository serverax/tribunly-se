# LawApp Case OS - Frontend Architecture

**Version:** 1.0  
**Date:** 16 June 2026  
**Stack (Phase 1):** Static HTML + `styles.css` + `case-os.css` + vanilla JS modules  
**Stack (Phase 2):** Next.js App Router (planned)

## Purpose

Case OS is the authenticated workspace where users track employment matters after registration: dashboard, case builder, grounded AI analysis, timeline, evidence, documents, deadlines, and solicitor escalation. Every screen calls a real backend route or shows an honest empty state.

## Module map

| Module | Path | Role |
|--------|------|------|
| Design tokens | `client/public/css/case-os.css` | Fraunces + Inter, navy `#0f1729`, legal gold `#c9a227`, responsive shell |
| App shell | `client/public/js/app-shell.js` | Mobile sidebar, `aria-current`, `case_id` propagation |
| Case state | `client/public/js/case-engine.js` | Active case id, cache, API bundle load, debounced `liveAssess` |
| UI components | `client/public/js/case-components.js` | StrengthMeter, Timeline, EvidenceBoard, DeadlineWidget, etc. |
| API client | `client/public/js/api-client.js` | Cookie-auth fetch wrappers for `/cases`, `/assess`, timeline, escalation |

## Responsive shell

- **Mobile (default, test 375px):** Off-canvas sidebar, bottom nav (5 items), single-column content  
- **Tablet (768px-1024px):** Icon rail sidebar, no bottom nav  
- **Desktop (1025px+):** Full sidebar labels, two-column analysis and document builder splits  

## Auth boundary

- **Public:** `index.html`, `intake.html`, `login.html`, `register.html`, free tools  
- **Case OS (login required):** `dashboard.html`, `case-intake.html` (save path), `my-case.html`, `timeline.html`, `deadlines.html`, `evidence.html`, `documents.html`, `escalation.html`, `advisor.html`, `settings.html`  
- **Hybrid:** `analysis.html` (session assessment or saved case), `case-intake.html` (anonymous through step 4 live preview; save on finish if logged in)

## Data flow

```
User input (case-intake)
  -> CaseEngine.liveAssess (debounced POST /assess)
  -> sessionStorage assessment_result
  -> CaseEngine.createCase (POST /cases) when logged in
  -> CaseEngine.loadCase (GET /cases/{id}, /deadline, /uploads, /bundle, /timeline, /escalation)
  -> LAWAPP_COMPONENTS.* render panels
```

## Figma alignment

Design tokens in `case-os.css` mirror the Figma spec (navy, legal gold, Fraunces display, Inter UI). Figma file creation is documented in `reports/figma_case_os_cursor.txt` (MCP unavailable in this session).

## Phase 2 (Next.js)

See `docs/frontend/FIGMA_CASE_OS_SCREEN_MAP.md` for route mapping to `/app/dashboard`, `/app/cases/[id]/timeline`, etc.
