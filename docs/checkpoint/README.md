# LawApp Checkpoints

Session checkpoint documents capture **evidence-backed progress** and **ordered next actions** when work stops mid-stream (context limits, subagent failure, owner input needed).

**Branch:** `release/lawapp-clean-snapshot`  
**Status:** PRE-BETA ENGINEERING (not production ready)  
**Rule:** No fabricated state. If unknown, mark `UNKNOWN - requires verification`.

---

## Index

| Checkpoint | Updated | Scope | Status |
|------------|---------|-------|--------|
| [INGESTION_LANGGRAPH_CHECKPOINT.md](./INGESTION_LANGGRAPH_CHECKPOINT.md) | 2026-06-16 | Dual-plane ingestion; LangGraph **STOPPED** (33abd9c); Brain-only runtime | **OPEN** (084 Docker proof, Case OS audit, grounding suite pending) |
| [MULTI_LANGUAGE_CHECKPOINT.md](./MULTI_LANGUAGE_CHECKPOINT.md) | 2026-06-16 | EN/AR language engine, RTL, i18n API | **OPEN** (verify tests + Brain wiring) |

---

## Architecture gates (enforced)

| Gate | State |
|------|-------|
| **Single Brain** | `backend/core/brain.py` only. LangGraph rolled back at `33abd9c`. ADR-000 enforced. |
| **Graph RAG** | Retrieval only via `retrieve_hybrid()`; Neo4j optional read-only (`NEO4J_ENABLED=false` default). |
| **LangGraph** | **STOPPED.** No `/api/v1/legal/reason`. `tests/test_single_brain_architecture.py` blocks reintroduction. |
| **Owner decisions** | **RESOLVED** 2026-06-16 (31 items). See `docs/decisions/OWNER_DECISIONS_2026-06-16.md`. **Do not re-ask.** |

Proof: `reports/single_brain_enforcement_cursor.txt`

---

## C-F critical path (pre-beta engineering)

Not LangGraph. Ordered priorities:

| ID | Item | Status |
|----|------|--------|
| **C** | Ingestion migration 084 Docker proof | PENDING |
| **D** | Case OS audit (wiring, coverage honesty, auth) | PENDING |
| **E** | Grounding suite (live Ollama, fail-closed insufficient_grounding) | PENDING |
| **F** | i18n verify (language engine + API tests) | PENDING |

Also: domain fail-closed (`employment_uk`), k6 Gate 3, gatekeeper re-ACCEPT.

---

## Related status docs (not checkpoints)

| Doc | Purpose |
|-----|---------|
| `docs/adr/ADR-000-langgraph-gate.md` | Single-brain gate; LangGraph blocked |
| `docs/decisions/OWNER_DECISIONS_2026-06-16.md` | Resolved owner decisions (31 items) |
| `docs/architecture/INGESTION_DUAL_PLANE_V1.md` | Dual-plane workers + migration 084 |
| `docs/architecture/GRAPH_RAG_LAYER_V1.md` | Hybrid retrieval; Neo4j optional |
| `docs/qa/GATEKEEPER_TRACK_AB_VERDICT.md` | Gatekeeper REJECT (Gates 2+3) |
| `docs/qa/CURSOR_CHECKPOINT_REPORT.md` | Go-live / beta readiness (2026-06-15) |
| `docs/handoff/` | Auto-generated handoff snapshots (context recovery) |

---

## When to add a checkpoint

- Multi-step build (ingestion, control plane, i18n) interrupted before merge.
- Subagent dispatched but transcript shows no completion.
- Owner must answer architecture questions before further implementation.

Each checkpoint must include: **Completed**, **In progress**, **Not started**, **Owner questions pending**, **Next actions** (ordered), **Commands to resume**.

**Do not** include LangGraph `/api/v1/legal/reason` curl proof commands. Brain entry is `/assess` only.
