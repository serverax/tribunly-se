# Figma Case OS screen map

## User workspace (Case Operating Environment)

| Screen | Route | APIs |
|--------|-------|------|
| Case workspace shell | `/pages/workspace.html?case_id=` | `GET /cases/{id}`, `GET /cases/{id}/deadline` |
| Timeline tab | `#timeline` | `GET /cases/{id}/timeline` |
| Evidence tab | `#evidence` | `GET/POST /cases/{id}/uploads` |
| Notes tab | `#notes` | `POST /cases/{id}/timeline/events` |
| Documents tab | `#documents` | `GET /api/cases/{id}/documents` |
| Analysis / AI panel | `#analysis` | `POST /assess`, `POST /api/features/claim-assessment` |

**Header metrics:** status, tribunal deadline, claim strength meter.

**Responsive:** mobile stack + bottom nav; tablet icon rail; desktop two-column (sections + AI panel).

**Next.js target:** `/app/workspace/case/[id]` (see `docs/frontend/CASE_OS_ARCHITECTURE.md`).

## Admin control center (port 8007 service + monolith UI)

| Screen | Route | API |
|--------|-------|-----|
| Dashboard | `/admin/dashboard.html` | aggregate of admin GETs |
| Cases | `/admin/cases.html` | `GET /admin/cases` |
| AI logs | `/admin/ai-logs.html` | `GET /admin/ai-logs` |
| Users | `/admin/users.html` | `GET /admin/users` |
| System health | `/admin/system-health.html` | `GET /admin/system-health` |
| Compliance | `/admin/compliance.html` | `GET /admin/compliance` |

Auth: JWT session with `users.is_admin = true`. Non-admin requests return 403 (fail closed).

## Legacy redirects

| Old | New |
|-----|-----|
| `/pages/my-case.html` | `/pages/workspace.html` |
