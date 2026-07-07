# Phase 1 Exit Report

Generated: 2026-07-07

## Scope

- Root: `F:\lawapp-restore`
- Branch: `codex/phase-1`
- Base: `codex/phase-0`
- No push, merge, deploy, secret rotation, Stripe proof, or Phase 2 work performed.

## Stage 1 - Collection Unlock

- Initial collection root cause: `tests/test_knowledge_proposals.py` imported missing `propose_knowledge_gap`.
- Fix: `backend/core/knowledge_proposer.py` restored a queue-only compatibility entry point.
- Targeted collect proof: `tests/test_knowledge_proposals.py --collect-only -q` collected 7 tests.
- Whole-suite collect proof: `1875 tests collected in 42.72s`.

## Stage 2 - Real Floor

- Commit: `a14f263`
- Full Docker pytest baseline: `6 failed, 1814 passed, 61 skipped, 6 warnings in 380.31s`.
- Raw log: `reports/phase1_stage2_full_pytest_raw.txt`.

## Stage 3 - Fixes

| Commit | Fix | Proof |
| --- | --- | --- |
| `5a4c786` | Restored knowledge proposal collection path and initial triage reports | `tests/test_knowledge_proposals.py --collect-only` collected 7 |
| `00b05c5` | Defined Brain module logger | Former logger crash cluster cleared |
| `fe0293a` | Published proposal approval event | `tests/test_knowledge_proposals.py`: 7 passed |
| `3c08e60` | Schema bootstrap compatibility for payment events/audit events | migrations complete; schema readiness PASS |
| `a14f263` | Graph Redis cache disables when Redis unconfigured | `tests/brain/test_brain.py`: 43 passed |
| `63fe17b` | Factual lane DB outage fails closed; proposal inserts satisfy recovered columns | targeted DB/proposal tests: 8 passed |
| `670ccef` | Proposal type constraint compatibility | migration 087 applied; proposal tests pass |
| `00ae393` | Environment skip for zero source-table embeddings | embedding tests: 2 skipped |
| `7fc5144` | Legal node type canonicalization | graph/indexer targeted tests: 4 passed |

## Triage Table

| Test | Root cause | Class | Lane |
| --- | --- | --- | --- |
| `tests/ingestion/test_ingestion.py::*_has_embeddings` | Fresh Docker DB has populated source rows but zero source-table embeddings; run condition documented in reports | ENVIRONMENT, skip when `0/N`; partial remains failure | Retrieval/embedding |
| `tests/test_assess_orchestrator.py::test_db_unavailable_fails_closed_not_crash` | Factual lane did not catch rules DB outage | REAL DEFECT fixed | Intake/diagnosis |
| `tests/knowledge_graph/test_knowledge_graph.py::test_node_types_are_valid` | Indexer wrote extractor labels `Section`/`Guidance` into Postgres taxonomy | REAL DEFECT fixed | Retrieval/graph |
| `tests/test_assess_orchestrator.py::test_missing_rule_fails_closed` | Status semantics: no NI rule returns `insufficient_grounding`, test expects `not_supported` | OWNER-GATED legal-output status | Intake/diagnosis |
| `tests/test_brain_outbox.py::test_brain_publishes_assessment_complete_then_worker_processes` | Legal-truth gate demotes patched uncited/nested-citation `ok` result | OWNER-GATED citation/legal-output behavior | Brain/outbox |
| `tests/test_integration_tools.py::test_resume_after_login_restores_answers_exactly` | Test conflicts with owner decision: anonymous special-category answers are not persisted | OWNER-GATED privacy/product decision | Intake/funnel |

## Stage 4 - Wire Proof

- Compose stack: all core `lawapp-restore-*` services healthy on alternate host ports.
- Backend health: `status=ok`, `db=connected`, `auth_mode=jwt`, `payment_mode=disabled`, local Ollama provider active.
- RAG health: `status=ok`.
- Rules health: `status=ok`.
- DB health: `pg_isready` accepting connections.
- Redis health: `PONG`.
- Ollama: `/api/tags` reachable; `bge-large-en-v1.5` present with 1024 embedding length.
- Frontend: `http://localhost:13000/intake` returned HTTP 200.
- Live diagnosis: `/api/workflow/diagnosis` unfair dismissal returned `status=success`, assessment `status=ok`, citations present, graph context present, deadline `2026-08-19` with source `rules`.
- Deadline endpoint: `/api/deadline/calculate` returned `limitation_date=2026-08-19`, source `rules`, authority `ERA 1996 s.111(2)`.
- Out-of-scope query: `/assess` tenant eviction query returned `status=not_supported`.
- Thin facts: `/assess` unfair-dismissal query with empty facts returned `status=missing_edt` and rendered honesty text for insufficient facts.
- Payment gate: seeded unpaid DB-backed case and `/api/documents/generate` returned HTTP 402 with `Payment required to generate documents`.
- Live fencing spot checks: `discrimination`, `whistleblowing`, `tupe`, and `pregnancy_maternity_discrimination` returned `status=not_covered`.

## Final Floor

- Commit: `7fc5144`
- Final full Docker pytest line: `3 failed, 1821 passed, 57 skipped, 6 warnings in 408.45s`.
- Raw log: `reports/phase1_final_full_pytest_raw.txt`.
- Comparison: Stage 2 baseline was `6 failed, 1814 passed, 61 skipped`; final floor improves the baseline with no unexplained regressions.

## STOPPED For Owner Approval

1. NI/no-rule status semantics (`insufficient_grounding` vs `not_supported`).
2. Legal-truth/citation gate behavior for outbox test's patched `ok` assessment.
3. Anonymous resume answer restoration versus the no-anonymous-special-category-persistence owner decision.

## Whole-Branch Diff Stat

See `git diff --stat codex/phase-0..codex/phase-1`. Scope includes targeted backend, migration, test, and report changes only; no secrets, Stripe proof, remote push, merge, or deploy.
