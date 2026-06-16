# LawApp Checkpoints

Session checkpoint documents capture **evidence-backed progress** and **ordered next actions** when work stops mid-stream (context limits, subagent failure, owner input needed).

**Branch:** `release/lawapp-clean-snapshot`  
**Rule:** No fabricated state. If unknown, mark `UNKNOWN - requires verification`.

---

## Index

| Checkpoint | Updated | Scope | Status |
|------------|---------|-------|--------|
| [INGESTION_LANGGRAPH_CHECKPOINT.md](./INGESTION_LANGGRAPH_CHECKPOINT.md) | 2026-06-16 | Ingestion 084, Case OS beta, i18n/domain verify; LangGraph **STOPPED** per [ADR-000](../adr/ADR-000-langgraph-gate.md) | **OPEN** (priorities 1-4; not LangGraph) |
| [MULTI_LANGUAGE_CHECKPOINT.md](./MULTI_LANGUAGE_CHECKPOINT.md) | 2026-06-16 | EN/AR language engine, RTL, i18n API | **OPEN** (verify tests + Brain wiring) |

**LangGraph:** Rolled back. Single Brain runtime only (`backend/core/brain.py`). Enforcement: `tests/test_single_brain_architecture.py`, proof: `reports/single_brain_enforcement_cursor.txt`.

**Owner decisions:** Resolved 2026-06-16 (`docs/decisions/OWNER_DECISIONS_2026-06-16.md`). No pending owner questions block ingestion or Case OS.

---

## Current build-order priorities (not LangGraph)

1. Ingestion migration 084 (dual-plane jobs)
2. Case OS beta baseline
3. i18n verify (language engine + API tests)
4. Domain verify (`employment_uk` fail-closed)

---

## Related status docs (not checkpoints)

| Doc | Purpose |
|-----|---------|
| `docs/adr/ADR-000-langgraph-gate.md` | Single-brain gate; LangGraph blocked |
| `docs/qa/CURSOR_CHECKPOINT_REPORT.md` | Go-live / beta readiness (2026-06-15) |
| `docs/qa/CURSOR_CHECKPOINT_STATUS_DETAILED.md` | Detailed service and gate status |
| `docs/decisions/OWNER_DECISIONS_2026-06-16.md` | Resolved owner decisions (31 items) |
| `docs/handoff/` | Auto-generated handoff snapshots (context recovery) |

---

## When to add a checkpoint

- Multi-step build (ingestion, control plane, i18n) interrupted before merge.
- Subagent dispatched but transcript shows no completion.
- Owner must answer architecture questions before further implementation.

Each checkpoint must include: **Completed**, **In progress**, **Not started**, **Owner questions pending**, **Next actions** (ordered), **Commands to resume**.
