# Next.js Frontend Deployment Plan

**Status:** Minimum viable scaffold in `client/next/`  
**Branch:** `release/lawapp-clean-snapshot`  
**Owner context:** Production target is Next.js on port 3000; static `client/public/` remains served by FastAPI :8000 until cutover.

---

## Goals

1. Next.js App Router talks to FastAPI via `NEXT_PUBLIC_API_URL`.
2. Landing, dashboard, and workspace routes call real backend endpoints (no mock data).
3. Docker service `frontend-next` on port 3000 in `docker-compose.yml`.
4. K8s: frontend Deployment behind `lawapp-ingress` in `lawapp-api` namespace (prep only).

---

## Environment

| Variable | Local Docker | Browser note |
|----------|--------------|--------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Must be host-reachable from the user's browser |
| `NODE_ENV` | `production` in image | dev: `next dev` |

---

## Routes (MVP)

| Route | Purpose | Backend |
|-------|---------|---------|
| `/` | Landing | `GET /health` smoke |
| `/dashboard` | Signed-in hub | `GET /api/auth/me`, `GET /cases` |
| `/workspace` | Case workspace shell | `GET /cases` |
| `/intake` | Case intake | `POST /cases` |
| `/diagnosis` | Brain diagnosis | `POST /api/diagnosis` |
| `/case/[id]` | Case detail | `GET /cases/{id}` |
| `/admin`, `/admin/review` | Admin gate (dev) | `lawapp-admin-service` :8007 |
| `/about-architecture` | Architecture overview | static + health links |

Rewrites in `next.config.mjs` proxy `/api/*`, `/cases/*`, `/assess`, `/health` to `NEXT_PUBLIC_API_URL`.

---

## Docker

```bash
docker compose up -d --build frontend-next backend
```

Health: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000`

---

## Cutover strategy

1. **Phase A (now):** Dual surface: Next :3000 + static :8000.
2. **Phase B:** Ingress sends `/` to Next, `/api` to backend.
3. **Phase C:** Retire static page routes except WASM assets if still needed.

---

## Out of scope (this pass)

- Full Case OS port of every `client/public/pages/*.html`
- SSR auth with httpOnly cookies (use `credentials: 'include'` when same-site)
- E2E Playwright against Next (existing tests target static client)
