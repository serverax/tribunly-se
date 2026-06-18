Generated: 2026-06-18T02:02:21+01:00
Repo: serverax/lawapp
Branch: release/lawapp-clean-snapshot
Code HEAD: 4209216
Phase: 3 (RAG/ingestion verification complete; beta promotion decision pending)

> **MANDATORY — agents and subagents STOP state:** [AGENTS_AND_SUBAGENTS_STATE.md](./AGENTS_AND_SUBAGENTS_STATE.md)
> All agent/subagent work is stopped. No background agents authorised. Read before spawning any Task/subagent or resuming hidden subagent context.

## Completed (this snapshot)

- Local Docker stack for LawApp core services reported healthy (db, backend, rag, graph-rag, rules, admin, audit, ollama, outbox-worker).
- Handoff documentation set under `docs/handoff/` including agent/subagent state ([AGENTS_AND_SUBAGENTS_STATE.md](./AGENTS_AND_SUBAGENTS_STATE.md)).
- Recent history includes Gate D PASS evidence (verify_ingestion_084 exit 0) and unified evidence stamping.
- **RAG 1024 verification PASS** (8/8 checks, 2026-06-18): `reports/rag_1024_retrieval_repair.txt`.
- **Beta readiness PASS** (subject to owner promotion only): `reports/BETA_PROMOTION_REVIEW.md`.
- Evidence reports refreshed in proof commit after `b75cd6c`.
- SEO Track B still not approved.

## Recently modified

- `docs/handoff/HANDOFF.md`, `docs/handoff/AGENTS_AND_SUBAGENTS_STATE.md`, `docs/handoff/RELEASE_STATE.md`, `docs/handoff/NEXT_TASKS.md`, `docs/handoff/PROOF_INDEX.md` (reconcile pass)

## Currently running (local, verified)

- Docker: lawapp-db-1, lawapp-backend-1, lawapp-lawapp-rag-service-1, lawapp-lawapp-graph-rag-service-1, lawapp-lawapp-rules-service-1, lawapp-lawapp-admin-service-1, lawapp-lawapp-audit-service-1, lawapp-ollama-1, lawapp-outbox-worker-1, lawapp-control-plane-1 (all Up, healthy where reported)
- **No agent or subagent processes authorised** — see [AGENTS_AND_SUBAGENTS_STATE.md](./AGENTS_AND_SUBAGENTS_STATE.md)

## Broken / failing

- Kubernetes cluster: kubectl cannot reach configured AKS API (DNS lookup failure). Remote deployment state unverified from this workstation.
- Untracked workspace noise: `_wt_feat/` (not committed)

## Build phase (01-06)

- Phase 3 RAG verification complete on release line @ `4209216`.
- Pre-beta engineering gate cleared; owner promotion decision is the remaining step.

## RAG status

- **RAG 1024 verification PASS:** 978/978 embedded @ 1024-dim `bge-large-en-v1.5`; `/api/rag/search` 4/4 queries with cited hits (5 each).
- Semantic plane: `corpus_chunks` canonical; query embed 1024-dim; ADR-000 clean.
- Source tables (`legislation`, etc.) remain `vector(384)` — non-blocking; corpus plane is canonical.

## Agent status

- Single reasoning runtime: `brain.py` (ADR-000); no second runtime.
- **All agents and subagents stopped.** Full policy: **[AGENTS_AND_SUBAGENTS_STATE.md](./AGENTS_AND_SUBAGENTS_STATE.md)**
- LangGraph still blocked (ADR-000).

## Legal compliance / guardrails

- Verification gate and citation requirements unchanged (see `.cursor/rules/40-ai-gate.mdc`).
- No secrets written to handoff docs; no production deploy or push performed.
