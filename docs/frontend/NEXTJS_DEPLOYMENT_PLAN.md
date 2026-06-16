# Next.js Frontend Deployment Plan

**Date:** 16 June 2026  
**Branch:** `release/lawapp-clean-snapshot`  
**Location:** `client/next/` (App Router, TypeScript)  
**Backend:** Python FastAPI monolith at `:8000` (unchanged)

---

## 1. Directory choice

| Option | Decision |
|--------|----------|
| `client/next/` | **Selected.** Keeps all UI under `client/` alongside legacy `client/public/` Case OS static assets. |
| `frontend/` | Rejected. Would split client code across two top-level trees. |

Migration strategy: run Next.js on port **3000** in parallel with the monolith-served static UI on **8000** until route parity is proven, then retire static HTML pages incrementally.

---

## 2. Blueprint route to API mapping

| Next.js route | Purpose | FastAPI endpoint(s) | Auth |
|---------------|---------|----------------------|------|
| `/` | Landing, trust copy, CTA to diagnosis | `GET /health` | None |
| `/intake` | Guided fact capture | `POST /cases` (save), facts in session until login | Optional |
| `/diagnosis` | Free diagnosis / assessment | `POST /api/diagnosis`, `POST /assess`, `POST /api/features/claim-assessment` | Optional anonymous; cookie to save |
| `/dashboard` | User case list | `GET /cases` | JWT cookie |
| `/case/[id]` | Case hub | `GET /cases/{id}`, `GET /cases/{id}/timeline`, `GET /cases/{id}/deadline` | JWT cookie |
| `/documents` | Paid document generation | `POST /api/workflow/documents/generate`, `GET /cases/{id}/bundle` | JWT + entitlement |
| `/payment` | Checkout | `POST /api/workflow/payment/create`, `POST /api/workflow/payment/confirm` | JWT cookie |
| `/handoff` | Solicitor referral capture | `POST /handoff/leads` | JWT cookie |
| `/workspace` | Saved matters / workspace | `GET /cases`, `POST /onboarding/complete`, `GET /onboarding/status` | JWT cookie |
| `/admin/*` | Reviewer gate (stub) | Proxy to `lawapp-admin-service:8007` (SSO deferred) | Admin JWT (future) |

### Supporting APIs (shared lib)

| Concern | Endpoint | Notes |
|---------|----------|-------|
| Auth session | `GET /api/auth/me` | httpOnly cookies, `credentials: include` |
| Login | `POST /api/auth/login` | Sets access + refresh cookies |
| Register | `POST /api/auth/register` | 201 |
| Logout | `POST /api/auth/logout` | Clears cookies |
| Deadline (rules-backed) | `POST /api/deadline/calculate` | Deterministic, rules table |
| Deadline alias | `POST /api/deadline/calc` | Alias for Next.js scaffold |
| Deadline (preview tool) | `POST /api/tools/deadline-calculator` | Anonymous funnel |
| Case deadline | `GET /cases/{id}/deadline` | Persisted case |
| Brain trace (debug) | `POST /api/brain/trace` | Governance audit |
| Graph RAG | Postgres `legal_nodes` / `legal_edges` via `POST /api/rag/graph` | No Neo4j (owner decision) |

---

## 3. Gap table: exists vs net-new

| Capability | Status | Action |
|------------|--------|--------|
| Diagnosis (`/api/diagnosis`) | **Exists** | Wired in `lib/api.ts` |
| Assessment (`/assess`) | **Exists** | Legacy alias, same handler |
| Claim assessment feature | **Exists** | `/api/features/claim-assessment` |
| Deadline calculate | **Exists** | `/api/deadline/calculate` |
| Deadline calc alias | **Added** | `POST /api/deadline/calc` |
| Auth cookies | **Exists** | `/api/auth/*` |
| Cases CRUD | **Exists** | `/cases/*` |
| Payment workflow | **Exists** | `/api/workflow/payment/*` |
| Document workflow | **Exists** | `/api/workflow/documents/generate` |
| Handoff leads | **Exists** | `/handoff/leads` |
| WASM deadline engine | **Exists** | `client/wasm/`; bind via `lib/wasm/` when pkg built |
| Next.js app shell | **Scaffolded** | `client/next/` |
| shadcn/ui components | **Scaffolded** | `components/ui/*` |
| Admin SSO reviewer UI | **Deferred** | Stub pages; proxy to 8007 later |
| Graph entity extraction UI | **Deferred** | Backend test routes only |
| Matter vs cases migration | **Partial** | `/cases` canonical today |

---

## 4. Architecture alignment

```
Browser (:3000 Next.js)
    |  fetch /api/* with credentials:include
    v
Next.js rewrites (dev/prod) -> NEXT_PUBLIC_API_URL
    v
FastAPI monolith (:8000)
    |-- Brain orchestrator (CitationGuard, rules-first)
    |-- PostgreSQL + pgvector
    |-- legal_nodes / legal_edges (graph, no Neo4j)
    v
Microservices (8016-8020) as wired in compose
```

**Non-negotiables:**

- Backend stays Python FastAPI; Next.js is UI only.
- Rules from DB always first; governance path unchanged.
- Graph RAG uses Postgres, not Neo4j.
- Local Ollama default for generative lane.

---

## 5. Docker deployment

### Compose service (`frontend`)

```yaml
frontend:
  build: ./client/next
  ports: ["3000:3000"]
  environment:
    NEXT_PUBLIC_API_URL: http://backend:8000
  depends_on:
    backend:
      condition: service_healthy
```

**Browser note:** For local Docker, set `NEXT_PUBLIC_API_URL=http://localhost:8000` at build time so the browser can reach the API from the host.

| URL | Service |
|-----|---------|
| http://localhost:3000 | Next.js UI |
| http://localhost:8000 | FastAPI API + legacy static |
| http://localhost:8007 | Admin service (future SSO) |

---

## 6. Migration path from `client/public`

| Phase | Action |
|-------|--------|
| 0 (now) | Scaffold Next.js; static Case OS remains on `:8000` |
| 1 | Port landing + diagnosis + intake to Next routes |
| 2 | Port dashboard, case hub, documents, payment |
| 3 | Redirect monolith `/pages/*` to Next equivalents |
| 4 | Remove static HTML when parity tests pass |

Reuse patterns:

- `client/public/js/auth.js` -> `lib/auth.ts`
- `client/public/js/case-engine.js` -> `store/caseStore.ts` + hooks
- `client/wasm/` -> `lib/wasm/deadline.ts` (after wasm-pack)

---

## 7. Tech stack

- Next.js 14 App Router
- TypeScript, Tailwind CSS, shadcn-style UI
- Zustand (`store/caseStore.ts`, `store/userStore.ts`)
- TanStack Query (`hooks/useCase.ts`, `hooks/useAssessment.ts`)
- WASM deadline calc (optional client-side, validated against API)

---

## 8. Deferred

- Full admin reviewer SSO (MFA) on `lawapp-admin-service`
- Graph entity extraction UI (`/api/kg/entity` test-only today)
- Matter schema cutover (`matter` replacing `cases`)
- Production ingress / TLS
- E2E Playwright suite for Next routes
