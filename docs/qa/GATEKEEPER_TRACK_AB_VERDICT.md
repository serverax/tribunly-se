# QA Gatekeeper  -  Track A+B (post gate session c295e3c)

**Date:** 2026-06-16  
**Branch / HEAD:** `release/lawapp-clean-snapshot` @ `c295e3c`  
**Verdict:** **REJECT** (controlled beta with waivers only)

## Gate evidence (this session)

| Gate | Result | Artifact |
|------|--------|----------|
| 1  -  Docker full pytest | **PASS** | `reports/pytest_docker_full_c295e3c.txt` (1728 passed, 48 skipped) |
| 2  -  Live Ollama legal accuracy | **FAIL** | `reports/legal_accuracy_live.txt` |
| 3  -  k6 @ 50 VU + load-test mode | **FAIL** | `reports/k6_100k_readiness_post_repair.txt` |
| 4  -  Migration 075 + bootstrap | **PASS** | `reports/bootstrap_gate4_c295e3c.txt` |

## Rationale

**Gate 1** clears Track A regression bar: full docker pytest green after repair batch fixes (Dockerfile dotfiles, outbox JSONB, DB hygiene).

**Gate 2 FAIL:** `run_legal_accuracy.py --live` exits 0 but **does not prove live generative inference**. Ollama reachable; `LocalInferenceReasoningModel` times out at 60s on full assessment prompt → `MODEL_UNAVAILABLE` → `fallback_used=True`, `source=rules_table`. Answers are rules-grounded via deterministic fallback, not live model output. **P0-002, P0-003, P0-008 remain OPEN.**

**Gate 3 FAIL:** With `LAWAPP_LOAD_TEST_MODE=1`, assess path has **0% HTTP failures** and **100%** `assessment responds 200`, but **p(95) latency = 36.93s** vs 3s threshold (`http_req_duration{type:assess}`). Rate-limit repair works; **assess latency at 50 VU is a genuine product/infra issue** (CPU-bound pipeline + optional Ollama contention). Login check also flaky (25% pass) under load  -  secondary.

**Gate 4 PASS:** Migration `075_official_guidance_multi_chunk.sql` recorded in `_migrations`; `official_guidance_source_url_key` unique constraint dropped; `db-bootstrap` completed exit 0, corpus_chunks=941.

## Still open (not in scope this session)

- Corpus 1000, a11y, scope-cut pages, Track C
- `lawapp-graph-rag-service` crash-looping (13/14 healthy at gate time)
- Production DB gate policy (P1-001)

## Re-open ACCEPT when

- Live Ollama generative path completes without `MODEL_UNAVAILABLE` / `fallback_used` on legal-accuracy gate
- k6 assess `p(95)<3000ms` at 50 VU with `LAWAPP_LOAD_TEST_MODE=1`, artifact saved
- graph-rag service stable on cold start

## Evidence cited

- `reports/pytest_docker_full_c295e3c.txt`
- `reports/legal_accuracy_live.txt`
- `reports/legal_accuracy_live_console_rerun.txt`
- `reports/k6_100k_readiness_post_repair.txt`
- `reports/bootstrap_gate4_c295e3c.txt`
- `reports/SESSION_GATES_C295E3C.md`
