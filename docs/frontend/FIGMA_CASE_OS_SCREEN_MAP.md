# LawApp Case OS - Figma Screen Map

**Version:** 1.0  
**Date:** 16 June 2026  
**Design tokens:** Navy `#0f1729`, legal gold `#c9a227`, Fraunces (display), Inter (UI)

---

## 1. Full screen map

| # | Product name | Figma frame | HTML page | Auth | Primary API |
|---|--------------|-------------|-----------|------|-------------|
| P1 | Landing | `Public / Landing` | `/index.html` | No | `POST /assess` (teaser), static |
| P2 | Login | `Public / Auth / Login` | `/pages/login.html` | No | `POST /api/auth/login` |
| P3 | Register | `Public / Auth / Register` | `/pages/register.html` | No | `POST /api/auth/register` |
| 1 | Dashboard | `Case OS / Dashboard` | `/pages/dashboard.html` | Yes | `GET /cases`, `GET /auth/me` |
| 2 | Case Builder | `Case OS / Case Builder` | `/pages/case-intake.html` | Partial | `POST /assess` (live), `POST /cases` |
| 3 | AI Analysis | `Case OS / AI Analysis` | `/pages/analysis.html` | Partial | `GET /cases/{id}`, session `/assess` |
| 4 | Timeline | `Case OS / Timeline` | `/pages/timeline.html` | Yes | `GET /cases/{id}/timeline` |
| 5 | Evidence Hub | `Case OS / Evidence Hub` | `/pages/evidence.html` | Yes | `GET/POST /cases/{id}/uploads` |
| 6 | Document Engine | `Case OS / Document Engine` | `/pages/documents.html` | Yes | `GET/POST /cases/{id}/bundle` |
| 7 | Deadlines | `Case OS / Deadline Center` | `/pages/deadlines.html` | Yes | `GET /cases/{id}/deadline` |
| 8 | Escalation | `Case OS / Escalation` | `/pages/escalation.html` | Yes | `GET /cases/{id}/escalation`, `POST /handoff/leads` |
| - | My Case hub | `Case OS / Case Hub` | `/pages/my-case.html` | Yes | `GET /cases/{id}` |
| - | AI Advisor | `Case OS / Advisor` | `/pages/advisor.html` | Yes | `POST /assess` |
| - | Settings | `Case OS / Settings` | `/pages/settings.html` | Yes | `GET /auth/me`, logout |
| Legacy | Full case detail | - | `/pages/case_detail.html` | Yes | Combined case APIs |
| Legacy | Free intake wizard | - | `/pages/intake.html` | No | `POST /assess` |

---

## 2. Wireframes (ASCII)

### Landing (`index.html`)

```
+----------------------------------------------------------+
| TRUST: Not a law firm · Not legal advice                   |
+----------------------------------------------------------+
| lawapp          Check situation | Tools | My case | Start|
+----------------------------------------------------------+
|  [Hero] Tell us what happened at work.                   |
|  [Start free]  [How it works]                            |
|  Tools grid | Know your rights | Footer                  |
+----------------------------------------------------------+
```

### Dashboard (desktop)

```
+----------+-----------------------------------------------+
| lawapp   |  Dashboard                    [New case]      |
| Dash     +-----------------------------------------------+
| Builder  |  +----------------+  +------------------+   |
| Analysis |  | Deadline bar     |  | Strength meter   |   |
| My case  |  +----------------+  +------------------+   |
| Timeline |  | Case cards (status, deadline, strength)   |
| ...      +-----------------------------------------------+
+----------+-----------------------------------------------+
```

### Case Builder - split at step 4 (tablet stacks)

```
+----------+-----------------------------------------------+
| (nav)    |  Story Builder   Step 4 of 5                  |
|          |  +----------------------+------------------+  |
|          |  | Evidence checklist   | LIVE ANALYSIS    |  |
|          |  | [ ] contract         | Strength: Mod    |  |
|          |  | [ ] dismissal letter | Summary...       |  |
|          |  |                      | · ERA citation   |  |
|          |  +----------------------+------------------+  |
|          |  [Back]                        [Continue]     |
+----------+-----------------------------------------------+
```

### AI Analysis (desktop two-column)

```
+----------+-----------------------------------------------+
|          |  PRIMARY: Summary + strength + citations      |
|          |  +------------------+------------------------+ |
|          |  | Grounded text    | Viability badge        | |
|          |  | Strength bars    | Next step CTA          | |
|          |  | Citation list    |                        | |
|          |  +------------------+------------------------+ |
+----------+-----------------------------------------------+
```

### Timeline

```
+----------+-----------------------------------------------+
|          |  Case chronology                              |
|          |    o 2026-01-15  Employment started           |
|          |    |                                          |
|          |    o 2026-05-01  Dismissed                  |
|          |    |                                          |
|          |    o 2026-05-10  ACAS started                 |
|          |    |                                          |
|          |    o (pending)   ET1 deadline                 |
+----------+-----------------------------------------------+
```

### Evidence Hub

```
+----------+-----------------------------------------------+
|          |  [ Drop zone / Choose files ]                 |
|          |  Upload list -> POST /cases/{id}/uploads      |
|          |  Evidence tiles grid                        |
+----------+-----------------------------------------------+
```

### Document Engine

```
+----------+-----------------------------------------------+
|          |  Bundle list          | Preview pane          |
|          |  [Generate bundle]    | ET1 / particulars     |
+----------+-----------------------------------------------+
```

### Escalation

```
+----------+-----------------------------------------------+
|          |  State: CONSIDER_SOLICITOR                    |
|          |  Reason + next action (from API)              |
|          |  [Request callback] phone + notes             |
+----------+-----------------------------------------------+
```

### Mobile (375px) - all Case OS screens

```
+---------------------------+
| [=]  Screen title         |
+---------------------------+
|  (single column content)  |
|                           |
+---------------------------+
| Home | Case | TL | Adv | + |
+---------------------------+
```

---

## 3. Component inventory

| Component | File | Used on |
|-----------|------|---------|
| `CaseOSShell` | `app-shell.js` | All Case OS pages |
| `CaseEngine` | `case-engine.js` | Builder, hub, timeline, escalation |
| `CaseCard` | `dashboard.html` (article.cos-panel) | Dashboard |
| `StrengthMeter` | `case-components.js` + CSS | Dashboard, analysis, my-case |
| `DeadlineProgress` | `case-os.css` | Dashboard, deadlines |
| `Timeline` | `case-components.js` | timeline.html, case_detail |
| `EvidenceUploader` | `case-os.css` + evidence.html | Evidence hub |
| `EvidenceBoard` | `case-components.js` | evidence.html |
| `AIAnalysisPanel` | analysis.html + live panel | analysis, case-intake step 4 |
| `LegalBasis` / citations | `case-components.js` | analysis, advisor |
| `RiskPanel` | `case-components.js` | analysis (extensible) |
| `DocumentBuilder` | `case-components.js` + documents.html | Document engine |
| `DeadlineWidget` | `case-components.js` | deadlines, intake review |
| `EscalationCard` | escalation.html | Escalation |
| `StoryBuilderWizard` | case-intake.html | Case builder |

---

## 4. Figma frame to HTML to API mapping

| Figma frame | HTML | API endpoints |
|-------------|------|---------------|
| `Public / Landing` | `/index.html` | Optional `POST /assess` |
| `Case OS / Dashboard` | `/pages/dashboard.html` | `GET /auth/me`, `GET /cases` |
| `Case OS / Case Builder` | `/pages/case-intake.html` | `POST /assess`, `POST /api/tools/deadline-calculator`, `POST /cases` |
| `Case OS / AI Analysis` | `/pages/analysis.html` | `GET /cases/{id}`, session from `/assess` |
| `Case OS / Timeline` | `/pages/timeline.html` | `GET /cases/{id}/timeline`, `POST /cases/{id}/timeline/events` |
| `Case OS / Evidence Hub` | `/pages/evidence.html` | `GET/POST /cases/{id}/uploads` |
| `Case OS / Document Engine` | `/pages/documents.html` | `GET /cases/{id}/bundle`, `POST .../bundle/generate` |
| `Case OS / Deadline Center` | `/pages/deadlines.html` | `GET /cases/{id}/deadline` |
| `Case OS / Escalation` | `/pages/escalation.html` | `GET /cases/{id}/escalation`, `POST /handoff/leads` |
| `Case OS / Advisor` | `/pages/advisor.html` | `POST /assess` |
| `Public / Auth / Login` | `/pages/login.html` | `POST /api/auth/login` |

---

## 5. Next.js migration path (Phase 2)

| Current HTML | Next.js App Router | Notes |
|--------------|-------------------|--------|
| `/index.html` | `/app/(public)/page.tsx` | Marketing + teaser |
| `/pages/login.html` | `/app/(auth)/login/page.tsx` | Server actions for auth |
| `/pages/dashboard.html` | `/app/(workspace)/dashboard/page.tsx` | RSC case list |
| `/pages/case-intake.html` | `/app/(workspace)/cases/new/page.tsx` | Client wizard + live assess |
| `/pages/analysis.html` | `/app/(workspace)/cases/[id]/analysis/page.tsx` | |
| `/pages/timeline.html` | `/app/(workspace)/cases/[id]/timeline/page.tsx` | |
| `/pages/evidence.html` | `/app/(workspace)/cases/[id]/evidence/page.tsx` | Upload route handlers |
| `/pages/documents.html` | `/app/(workspace)/cases/[id]/documents/page.tsx` | |
| `/pages/deadlines.html` | `/app/(workspace)/cases/[id]/deadlines/page.tsx` | |
| `/pages/escalation.html` | `/app/(workspace)/cases/[id]/escalation/page.tsx` | |
| Shared shell | `/app/(workspace)/layout.tsx` | Sidebar + bottom nav from design tokens |

Shared Zustand store replaces `CaseEngine` localStorage cache; API contracts unchanged.

---

## 6. Responsive breakpoints per screen

| Screen | Mobile `<768` | Tablet `768-1024` | Desktop `>=1025` |
|--------|---------------|-------------------|------------------|
| Landing | Single column, hamburger nav | 2-col tools | Full nav, hero max-width |
| Dashboard | Bottom nav, stacked cards | Rail nav, 1-col metrics | Sidebar, 2-col metrics + cards |
| Case Builder | Stacked steps, live panel below | Stacked analysis | Optional side-by-side step 4 |
| AI Analysis | Stacked panels | Stacked | 60/40 split |
| Timeline | Vertical list | Vertical list | Vertical list + wider gutters |
| Evidence | Full-width dropzone | 2-col tile grid | 3-col tile grid |
| Documents | Stacked builder/preview | Stacked | 50/50 split |
| Escalation | Form full width | Form full width | Max-width 640px form |
| Auth | Full width form | Centered card | Centered card |

Test viewports: **375px**, **768px**, **1280px**.

---

## 7. Implementation roadmap (Phases 1-4)

### Phase 1 - Shell + tokens + page stubs (current)

- [x] `case-os.css` tokens (navy, gold, Fraunces, Inter)  
- [x] Responsive shell (sidebar, bottom nav, overlay)  
- [x] HTML pages for all 7 core screens + auth + landing  
- [x] `app-shell.js`, `case-engine.js`, `case-components.js`  
- [x] Wire dashboard, evidence, documents, deadlines to real APIs  

### Phase 2 - Grounded workflows

- [x] Debounced live `/assess` on case-intake step 4  
- [ ] Unify nav via single shell partial (reduce duplicated sidebar HTML)  
- [ ] Trace ID display on all analysis surfaces  
- [ ] Link landing CTA to `case-intake.html` for logged-in users  

### Phase 3 - Next.js + design system package

- Migrate workspace routes under `/app/(workspace)/*`  
- Extract tokens to `@lawapp/tokens` or Tailwind preset  
- Figma variables synced from tokens JSON  

### Phase 4 - Figma library + variants

- Figma file `LawApp Case OS` with desktop/mobile frames per screen  
- Component variants: CaseCard, Timeline event, StrengthMeter states  
- Code Connect mapping for shared components  

---

## 8. Local test URLs

Base: `http://localhost:8000`

| Screen | URL |
|--------|-----|
| Landing | http://localhost:8000/ |
| Login | http://localhost:8000/pages/login.html |
| Dashboard | http://localhost:8000/pages/dashboard.html |
| Case builder | http://localhost:8000/pages/case-intake.html |
| AI analysis | http://localhost:8000/pages/analysis.html |
| Timeline | http://localhost:8000/pages/timeline.html |
| Evidence | http://localhost:8000/pages/evidence.html |
| Documents | http://localhost:8000/pages/documents.html |
| Deadlines | http://localhost:8000/pages/deadlines.html |
| Escalation | http://localhost:8000/pages/escalation.html |
