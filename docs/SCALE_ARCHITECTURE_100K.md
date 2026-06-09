# LawApp — 100k Concurrent Scale Architecture (BINDING NFR)

**Status:** 🔴 NOT MET TODAY — foundational gaps identified (live audit 2026-06-07).
**Owner:** project-manager. **Applies to:** every task T-001..T-014 and all teams.
**Rule:** This is a non-functional requirement, not optional optimization. No task reaches
PASS unless it satisfies its slice of this spec OR explicitly records the gap as owner-blocked.

---

## 0. Honest current-state audit (live, 2026-06-07)

| Concern | Required for 100k | Current state | Verdict |
|---|---|---|---|
| API rate limiting | edge + app | slowapi `_limiter`, 19 routes in `backend/api/main.py` | 🟡 app-layer only |
| DB connection pooling | PgBouncer + app pool | **none** — `ingestion/db.py` `psycopg2.connect()`+`close()` per query | 🔴 GAP |
| Service replicas | N≥3 + HPA each | **all 9 k8s deployments `replicas: 1`** (SPOF) | 🔴 GAP |
| HPA / autoscaling | CPU+RPS HPA | **no HorizontalPodAutoscaler manifests** | 🔴 GAP |
| Redis caching | hot-path cache | redis container up, **backend has no cache reads/writes** | 🔴 GAP |
| Read replicas | ≥2 read replicas | single PG instance | 🔴 GAP (owner infra) |
| CDN / static edge | global CDN | none (frontend baked into backend image) | 🔴 GAP |
| Load/spike/soak/chaos tests | k6/Locust harness | **none** | 🔴 GAP → T-014 |

**Conclusion:** as built, the system handles low-hundreds concurrent, not 100k. The work below is mandatory.

---

## 1. Capacity model (targets)
- **100,000 concurrent visitors**, assume ~10–20% active RPS → design for **10k–20k RPS** sustained.
- **P95 API latency < 200 ms** (non-LLM routes). LLM/brain routes are async/queued (see §6).
- **Error rate < 0.1%** under sustained load; **< 1%** during spike.
- **First contentful paint < 3 s** at 100k (frontend, §5).
- **No single point of failure** — every service N≥3, stateless, behind a load balancer.

## 2. Backend (T-001/T-005/T-008/microservices)
- All FastAPI services **stateless** (no in-process session/state) → horizontally scalable.
- **Connection pooling is mandatory** — replace per-call `psycopg2.connect()` with a pooled
  accessor (`psycopg2.pool.ThreadedConnectionPool` or SQLAlchemy pool) shared per process,
  fronted by **PgBouncer** (transaction mode) in the cluster. *This is the #1 blocker.*
- **Circuit breakers** on every cross-service + DB + LLM call (fail-closed → cached/deterministic
  fallback, never a fake legal answer). CitationGuard fallback already models this.
- **Graceful degradation:** if RAG/LLM saturated → deterministic rules-engine answer + "high load" caveat.
- Async LLM: brain/LLM calls must not hold a request thread for seconds at 100k → queue + poll or SSE.

## 3. Database (T-003/T-004/data-engineer)
- **PgBouncer** transaction pooling in front of Postgres (target ≥ thousands of client conns → ~100 server conns).
- **≥2 read replicas**; route all read-only corpus/RAG/retrieval queries to replicas; writes to primary.
- **Redis cache** for hot, rarely-changing data: corpus_chunks lookups, CitationGuard UUID-validity
  set, rules table, legal_sources. TTL + explicit invalidation on ingestion.
- **No N+1**: audit `valid_corpus_uuids` (already batched via `= ANY(%s::uuid[])` — good), retrieval,
  rules load. Every list endpoint paginated.
- Indexes verified for every hot query path (HNSW for vectors already present on AKS corpus).

## 4. Infrastructure / K8s (T-012/platform-devops)
- Every Deployment: `replicas: ≥3`, `HorizontalPodAutoscaler` (target CPU 60% + custom RPS metric), PDB.
- Resource requests/limits set on every container (HPA needs requests).
- LB: ingress/Service per service; readiness gates traffic; liveness restarts.
- Multi-AZ node pools; multi-region only if traffic is global (owner decision).
- Edge: rate limiting + **DDoS/WAF** (Azure Front Door / Cloudflare) — see §7.

## 5. Frontend (T-009/UI-UX)
- **CDN** for all static assets (currently baked into backend image — must be externalized).
- Lazy-load heavy pages; defer non-critical JS (no blocking scripts); preconnect to API.
- Image optimization: responsive + WebP/AVIF.
- FCP < 3 s at load; cache-control + immutable hashed assets.

## 6. Security at scale (T-010/security-architect)
- **Edge DDoS protection + WAF** (L3/L4 + L7) before traffic hits the cluster.
- Rate limiting per-IP + per-user + global; bot/abuse detection; CAPTCHA on abuse spikes.
- RLS/entitlement checks must stay O(1) and cached — no per-request full-table scans.
- No auth/PII path that degrades into a bypass under load (fail-closed under saturation).

## 7. Testing (T-014 — NEW; QA T-013 gates it)
- **Load test** @ 100k concurrent (k6/Locust, distributed generators).
- **Spike test**: sudden +10k.
- **Soak test**: sustained hours (watch leaks, pool exhaustion).
- **Chaos**: kill pods, inject network latency, DB failover — verify graceful degradation + recovery.
- **Reports**: P50/P95/P99 latency, error rate, RPS, CPU/mem/conn utilization per layer.
- **Honest scoping:** true 100k generation needs the AKS cluster (currently unreachable) + a
  distributed load-gen fleet → **owner-blocked**. Local baseline runs now (single-node, scaled-down)
  to find code-level bottlenecks before the full test.

---

## 8. Acceptance gates (added to T-013 QA gatekeeper)
A release claiming 100k-readiness MUST present:
1. PgBouncer + app pool config in repo + live `SHOW POOLS` proof.
2. HPA manifests for every service + `kubectl get hpa` showing scale events under load.
3. Redis cache hit-rate proof on hot paths.
4. Read-replica routing proof (read queries hit replica).
5. CDN serving static assets (response headers).
6. k6/Locust report: P95<200ms, error<0.1% at target RPS.
7. Chaos test: pod kill → no user-facing failure, auto-recovery.
Any missing item → **PARTIAL** or **FAIL**, never PASS. No `echo PASS`, no synthetic numbers.
