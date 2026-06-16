# LawApp — Project Status

**Updated:** 2026-06-16  
**Branch:** `release/lawapp-clean-snapshot`  
**HEAD:** `12f835f` (pre–Phase 1 repair commits; refresh after repair push)  
**QA input:** [docs/qa/CURSOR_REPAIR_NOW_LIST.md](../docs/qa/CURSOR_REPAIR_NOW_LIST.md), [docs/qa/CURSOR_CHECKIN_REPORT.md](../docs/qa/CURSOR_CHECKIN_REPORT.md)  
**Overall verdict:** 🟡 **GO WITH RISK (controlled beta)** — Track A+B complete; Phase 1 P0 repairs in progress; public production **NO-GO**

---

## Track A — Beta Finish (complete)

| Task | Result | Evidence |
|------|--------|----------|
| A1–A9 | **PASS*** | `reports/TRACK_A_BETA_FINISH_COMPLETION.md` |
| Host pytest | **1704 passed**, 153 skipped, 0 failed | `reports/pytest_full_postfix_cursor.txt` |
| Docker collect | **1858 collected**, 0 import errors | `reports/docker_pytest_collect_fixed_cursor.txt` |
| Auth / phase5 / phase6 | Repaired | `reports/pytest_auth_*`, `reports/pytest_phase5a_phase6_cursor.txt` |

\*A7 waiver: `test_stream_chat_real_tokens_from_qwen` skipped when local Ollama unreachable — see `docs/ops/OLLAMA_LOCAL.md` and P0-002.

---

## Track B — Production prerequisites (mostly complete)

| Task | Result | Evidence |
|------|--------|----------|
| B1 RAG corpus | **889 chunks** (881 embedded) — stretch >>1000 open | `reports/track_b_rag_expansion_cursor.txt` |
| B2 Scope-cut modules | **13 partial** fenced in API/UI | `reports/track_b_module_tests_cursor.txt` |
| B3 k6 load | **FAIL** assess @ 50 VU (rate limit) — P0-001 repair | `reports/k6_100k_readiness_cursor.txt` |
| B4 OTEL trace | **PASS** trace_id ↔ brain_traces | `reports/track_b_otel_cursor.txt` |
| B5 DB beta gate | **PASS** | `reports/proof_database_integrity_beta_cursor.txt` |
| B6 a11y | **PASS*** (4 findings A1–A4 deferred) | `reports/track_b_a11y_cursor.txt` |

---

## Fresh runtime (2026-06-16 check-in)

| Check | Status |
|-------|--------|
| Docker | **12/12 healthy** |
| Backend `/health` | `status: ok`, `db: connected`, `auth_mode: jwt` |
| Rules | **125** |
| Corpus | **889** chunks / **881** embedded |
| Modules | **11 production** + **13 partial** (scope-cut in product) |
| Migrations | **74** |

---

## Phase 1 P0 repair status (this session)

| ID | Item | Status |
|----|------|--------|
| P0-001 | k6 assess rate limit profile | **IN PROGRESS** — `LAWAPP_LOAD_TEST_MODE` + k6 re-run |
| P0-002 | Ollama local dev override | **IN PROGRESS** — compose + `docs/ops/OLLAMA_LOCAL.md` |
| P0-003 | Live vs stub legal accuracy | **IN PROGRESS** — `run_legal_accuracy.py --live` |
| P0-004 | RAG corpus ≥1000 | **IN PROGRESS** — ACAS URL fixes + gov.uk ingest |
| P0-005 | assessment.html `fetchWithAuth` | **IN PROGRESS** |
| P0-006 | This document refresh | **IN PROGRESS** |
| P0-007 | Gatekeeper Track A+B verdict | **IN PROGRESS** |

---

## Go-live matrix

| Scope | Verdict |
|-------|---------|
| Local Docker dev/demo | **GO** |
| Controlled beta (11 topics) | **GO WITH RISK** |
| Public production | **NO-GO** — k6, prod DB gate, K8s/secrets/Stripe live |

---

## P0 blockers (honest)

| ID | Blocker | Owner | Status |
|----|---------|-------|--------|
| P0-001 | k6 assess rate limit under load | platform | OPEN → repair |
| P0-002/003/008 | Ollama / live legal accuracy / streaming waiver | local-llm | OPEN → repair |
| P0-004 | Corpus 889 vs 1000 stretch | legal-data | OPEN → repair |
| P0-005 | assessment.html raw `fetch` on mutations | frontend | OPEN → repair |

---

## Legal-data pipeline (binding)

`uk-employment-law-scraper-agent → legal-data-engineer-agent → db-rag-ingestion-agent → ai-brain-citationguard-agent → qa-release-gatekeeper`

No FCL bulk without licence. No fake rows for missing sources.

---

## Track C — owner only (not agent-executed)

Secrets rotation (G2), prod deploy, Stripe live, backup drill — see `reports/TRACK_C_OWNER_HANDOFF.md`.

---

## Next (Phase 2 engineering)

1. P1-002 — assess → brain_traces on all paths  
2. P1-003 + P1-009 — a11y A1–A4 + scope-cut static pages  
3. P1-001 — production DB gate policy (promote vs gate rule)  
4. P1-004/005/008 — compose sidecars, bootstrap cold start, docker full pytest  
5. P1-007 — tiered rate limits for production scale  

---

*Honest status: controlled beta remains GO WITH RISK with documented waivers until Phase 1 P0 items close and gatekeeper re-issues ACCEPT.*
