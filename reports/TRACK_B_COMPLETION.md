# TRACK B (Production Prerequisites)  -  Completion Report

Branch: `release/lawapp-clean-snapshot`  
Baseline: `f798e63` (Track A complete)  
Completed: 2026-06-15

## Status vs production definition of done

| Task | Criterion | Status | Artifact |
|------|-----------|--------|----------|
| B1 | Expand RAG corpus (legislation+ACAS), >>323 chunks, RAG PASS | **PASS*** | reports/track_b_rag_expansion_cursor.txt |
| B2 | 13 partial modules promoted OR scope-cut fenced | **PASS** | reports/track_b_module_status_cursor.txt |
| B3 | k6 smoke/readiness tuned | **FAIL** | reports/k6_100k_readiness_cursor.txt |
| B4 | OTEL trace_id ↔ brain_traces SQL | **PASS** | reports/otel_trace_proof_cursor.txt |
| B5 | Backlog fix or document | **PASS** | reports/TRACK_B_BACKLOG_CURSOR.txt |
| B6 | a11y/mobile audit | **PASS*** | reports/a11y_mobile_audit_cursor.txt |
| Track C prep | Owner handoff doc (no execution) | **PASS** | reports/TRACK_C_OWNER_HANDOFF.md |

\*B1 waiver: 889 chunks (goal >>1000 if feasible  -  close but not reached; 7 ACAS URLs 404 skipped).  
\*B6 waiver: findings A1–A4 documented, no P0 fixes in Track B scope.

## B1–B6 summary table

| ID | PASS/FAIL | Key evidence |
|----|-----------|--------------|
| B1 | PASS | 323→889 corpus_chunks; hybrid-search insufficient_grounding=false |
| B2 | PASS | 13 modules scope_cut; API `not_covered`; UI PARTIAL_HIDDEN |
| B3 | FAIL | assess 94% http_req_failed under 50 VU  -  SlowAPI 30/min rate limit |
| B4 | PASS | trace_id 4e6f144b… in HTTP + brain_traces SQL |
| B5 | PASS | datetime/services/ollama documented |
| B6 | PASS | a11y baseline good; 4 low/medium findings logged |

## Commits (logical units)

- `54ba433` Expand licensed RAG corpus via legislation.gov.uk and ACAS sources
- `6bd8bdd` Formal scope-cut fencing for 13 partial employment modules
- `a30be0d` Tune k6 readiness script for assess tags and scope-cut checks
- `b03e55a` Add Track B production prerequisite evidence and completion report

Pushed to `origin/release/lawapp-clean-snapshot` (not main).

## Production verdict

**Still NO-GO for unrestricted public production**  -  closer to GO than post–Track A:

**Improved**
- RAG corpus ~2.75× larger (889 chunks, licensed sources only)
- 13 partial modules formally scope-cut (honest product boundary)
- brain_traces ↔ trace_id proven for Brain path
- Scope-cut API/UI tests green

**Remaining blockers**
- k6 assess path fails under concurrent load (rate limit + latency p95 6.15s on assess tag)
- GO_LIVE_MODE=production still fails (13 DB modules `partial` by design until promoted)
- K8s/prod secrets/Stripe live/backup drill  -  Track C owner actions only
- Full pytest suite not re-run in Track B (Track A baseline stands)

**Beta / controlled staging:** **GO WITH RISK** (inherits Track A) + stronger corpus + explicit scope cut.

## Escalations

None requiring STOP. No live secrets found or printed.

## Track C handoff summary

Owner must execute: G2 PAT rotation, prod secret provisioning, K8s deploy smoke, Stripe live webhook proof, backup/restore drill on staging, marketing/legal sign-off. See reports/TRACK_C_OWNER_HANDOFF.md.

## Waivers

1. B1 chunk count 889 vs 1000 stretch goal  -  licensed-source-limited; no fake rows for 404 ACAS pages.
2. B3 k6  -  host k6.exe blocked by App Control; Docker grafana/k6 used; failure attributed to assess rate limit not product crash.
3. B6  -  audit-only; fixes deferred to UX track.
