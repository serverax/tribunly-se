# Case OS architecture

## User workspace (static client)

**Current path:** `/pages/workspace.html?case_id={uuid}`

Hash tabs (single-page, no extra HTML files):

| Hash | Panel |
|------|--------|
| `#timeline` | Matter timeline from `/cases/{id}/timeline` |
| `#evidence` | Uploads via `/cases/{id}/uploads` |
| `#notes` | User notes as `custom_user_event` timeline rows |
| `#documents` | Drafts from `/api/cases/{id}/documents` |
| `#analysis` | Live debounced `/assess` via `case-engine.js` |

Layout: case header (status, deadline, strength), left section tabs, right AI panel (reasoning, risk, next action).

Mobile: stacked panels, hamburger sidebar from `case-os.css` + `app-shell.js`.

## Planned Next.js path

`/app/workspace/case/[id]` will mirror the same layout and API contracts. The static workspace is the reference implementation until the App Router shell ships.

## Admin control center

**UI:** `/admin/dashboard.html` (and siblings) on the monolith static host.

**API (JWT admin role, fail closed):**

- `GET /admin/cases`
- `GET /admin/ai-logs`
- `GET /admin/users`
- `GET /admin/system-health`
- `GET /admin/compliance`

**Service boundary:** `lawapp-admin-service` on port **8007** exposes the same dashboard metrics plus these list endpoints for cluster-internal callers. Owner decision: reviewer gate UI lives on the dedicated admin service with SSO/MFA for reviewers.

## AI audit

Every governed assess path writes `brain_traces` with `input_summary`, `retrieved_sources`, `reasoning_trace`, `confidence`, `model_version` (migration `081_admin_audit_extensions.sql`).
