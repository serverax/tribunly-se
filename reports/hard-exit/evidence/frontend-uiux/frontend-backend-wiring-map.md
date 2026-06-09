# Frontend → Backend Wiring Map (grep-derived)

| Page / JS | Backend route(s) called | Real backend handler |
|---|---|---|
| register.html, auth.js | `POST /auth/register`, `POST /auth/token` | main.py:234, 263 |
| login.html, auth.js | `POST /auth/token`, `GET /auth/me` | main.py:263, 280 |
| intake.html | `POST /assess` | main.py:487 |
| assessment.html (5 calls) | `POST /assess`, `GET /rules/{claimType}`, `POST /documents/generate`, `POST /handoff/leads` | main.py:487, 385, 581, 871 |
| constructive_dismissal.html | `POST /api/workflows/constructive-dismissal` | main.py:2453 |
| deadline.js | `GET /rules/{claimType}` (+ client WASM deadline calc) | main.py:385 |
| dashboard.html | `GET /cases` | main.py:751 |
| case_detail.html, saved_case.html | `GET /cases/{id}` | main.py:793 |
| document_preview.js | `POST /documents/generate` | main.py:581 |
| success/cancel.html | `POST /api/payment/create-session` | main.py:~2520 |

All routes above exist in `backend/api/main.py` and run real logic (DB-backed). No mock/fake-data
product path detected in `client/public/js` or `pages` (grep for mock|fake|dummy|hardcoded → none).

## Not-yet-proven at render level (needs Playwright vs live backend)
- Answer view actually DISPLAYS: citations/source panel, deadline/risk warning, trace_id, next steps.
- Dashboard loads real workspace/module-entitlement data (no entitlement fetch observed in grep).
- Auth-gated pages enforce auth via backend (login redirect on 401).
