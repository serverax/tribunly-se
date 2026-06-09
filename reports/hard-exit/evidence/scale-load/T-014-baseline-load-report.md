# T-014 — Baseline Load Report (100k NFR, scaled-down local)

**Date:** 2026-06-07
**Target:** live `lawapp-backend-1` (local Docker, single container).
**Harness:** `scripts/load/baseline_load.py` (real concurrent HTTP, percentile latency).
**Result:** 🔴 **NOT 100k-ready** — current single-node config is ~200× short of target.
**Scope honesty:** this is a *local single-node* probe to expose code/config bottlenecks. A
true 100k test needs the AKS cluster (unreachable) + a distributed load-gen fleet → owner-blocked.

---

## Measured (real numbers)

### `/health` — trivial endpoint, no DB, concurrency=100, requests=2000
`reports/hard-exit/evidence/scale-load/t014-baseline/health-c100-n2000.json`
```
throughput_rps : 51.3
error_rate_pct : 0.0   (2000/2000 HTTP 200)
latency_ms     : p50=1748  p95=2505  p99=3104  max=3241  mean=1699
```

## Interpretation vs targets
| Target (SCALE_ARCHITECTURE §1) | Measured | Gap |
|---|---|---|
| P95 < 200 ms | **2505 ms** | ~12× over |
| ≥ 10,000 RPS sustained | **51 RPS** | ~200× under |
| error < 0.1% | 0.0% | ✅ (no errors, just slow) |

**Root causes (consistent with the architecture audit):**
1. Single backend container, **single uvicorn worker** (dev mode) — no process/worker scaling.
2. **No connection pooling** — even non-DB routes share one event loop saturated at c=100.
3. `replicas: 1` everywhere — no horizontal scale, no LB.
4. No caching → every request does full work.

## What this proves
- The bottleneck is **architectural/config**, not a single bug. The fixes in
  `docs/SCALE_ARCHITECTURE_100K.md` (PgBouncer + pool, gunicorn/uvicorn workers, HPA replicas≥3,
  Redis cache, CDN, async LLM) are mandatory, not optional.
- 0% error rate confirms correctness holds under load; the problem is throughput/latency.

## Next (T-014)
1. Add gunicorn multi-worker + uvicorn workers to backend image; re-baseline (expect big RPS gain).
2. Implement connection pool in `ingestion/db.py` (pooled accessor) + PgBouncer manifest.
3. Author HPA manifests (replicas≥3) for all 9 services.
4. Add Redis cache for CitationGuard UUID set + corpus/rules hot paths.
5. Re-run baseline after each; full 100k distributed run = owner-blocked (needs AKS + load fleet).

**Verdict: T-014 = FAIL (not yet 100k-ready) — baseline captured, remediation plan binding.**
