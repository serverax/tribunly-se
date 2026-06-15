# LawApp — Project Status

**Updated:** 2026-06-15  
**Branch:** `release/lawapp-clean-snapshot`  
**HEAD:** `f38c22f` fix(go-live): wire RAG corpus, bootstrap, and beta QA gates
**QA input:** [docs/qa/CURSOR_REPAIR_BACKLOG.md](../docs/qa/CURSOR_REPAIR_BACKLOG.md), [docs/qa/CURSOR_COMPLETION_DECISION.md](../docs/qa/CURSOR_COMPLETION_DECISION.md)  
**Overall verdict:** 🟡 **NOT READY FOR GO-LIVE** — P0 RAG wiring repaired; P0 module gate fail-closed in API; full 24-module + test suite still open


## Post-approval workflow (2026-06-15)

| Check | Result |
|-------|--------|
| Commit | `f38c22f6806353f1110127d9b43a910d6f242875` — fix(go-live): wire RAG corpus, bootstrap, and beta QA gates |
| Push | `origin/release/lawapp-clean-snapshot` (20650a0..f38c22f) |
| Docker build | backend, db-bootstrap, ingestion — **OK**; backend + lawapp-rag-service recreated |
| pytest --collect-only | **1833** tests collected (2 import errors: test_rules_engine_scale, test_service_tracing_integration) |
| RAG `/api/rag/search` | **HTTP 200**, vector hits (ACAS + ERA) |
| prove_database_integrity.sh (GO_LIVE_MODE=beta) | **PASS** |
| prove_lawapp_full_workflows.sh | **PASS** |

---

## Recovery session (2026-06-14)

| Item | Before | After | Status |
|------|--------|-------|--------|
| QA-001 RAG search | 0 hits (wrong table `legal_corpus`) | 5 hits for "unfair dismissal" (ACAS + ERA s.98/111) | 🟡 **PARTIAL** |
| QA-001 corpus size | 28 chunks | 323 chunks, 315 embedded | 🟡 below >>1000 target |
| QA-002 partial modules | 13/24 partial | 13/24 partial; API fail-closed for non-production | 🟡 **PARTIAL** (scope-cut UX) |
| Docker health | 12/12 | 12/12 | ✅ |
| Rules in DB | 125 | 125 | ✅ |

---

## P0 blockers

| ID | Blocker | Owner | Status |
|----|---------|-------|--------|
| QA-001 | RAG corpus + search | db-rag-ingestion-agent | 🟡 Search **FIXED**; corpus 323 (needs more ingest for >>1000) |
| QA-002 | 13 partial employment modules | legal-rule-engine-agent | 🟡 Fail-closed in `/api/workflow/diagnosis` + registry; DB go-live gate still fails |

---

## P1 (unchanged)

QA-003 container pytest parity · QA-004 59 test failures · QA-005 k6 load · QA-006 K8s deploy · QA-015 prod secrets

---

## Legal-data pipeline (binding)

Delegation sequence unchanged:

`uk-employment-law-scraper-agent → legal-data-engineer-agent → db-rag-ingestion-agent → ai-brain-citationguard-agent → qa-release-gatekeeper`

Bootstrap run 2026-06-14: legislation + ACAS ingested, 288 embeddings, corpus sync **295 rows added** after `jurisdiction` NOT NULL fix.

---

## Next (ordered)

1. Rebuild `db-bootstrap` image so `ingestion.sync_corpus_chunks` is included (bootstrap exited 1 on missing module in image).
2. Expand corpus toward >>1000 chunks (full domain pack ingest + case law where licensed).
3. QA-002: either promote next modules via migrations 062–068 + legal review, or enforce UI hide for partial modules in intake picker.
4. QA-004: auth fixtures on integration tests.
5. Owner: G2 leaked PAT rotation (not agent-performed).

---

## Task ledger

| Task | State |
|------|-------|
| QA-001 RAG wiring + bootstrap | 🟡 in progress — search proven, corpus partial |
| QA-002 module fail-closed | 🟡 API proven; full promotion backlog |
| 007a–007d legal-data provenance | 📋 backlog |
