# LawApp Checkpoints

Session checkpoint documents capture **evidence-backed progress** and **ordered next actions** when work stops mid-stream (context limits, subagent failure, owner input needed).

**Branch:** `release/lawapp-clean-snapshot`  
**Rule:** No fabricated state. If unknown, mark `UNKNOWN - requires verification`.

---

## Index

| Checkpoint | Updated | Scope | Status |
|------------|---------|-------|--------|
| [INGESTION_LANGGRAPH_CHECKPOINT.md](./INGESTION_LANGGRAPH_CHECKPOINT.md) | 2026-06-16 | LangGraph STOP enforced; single Brain confirmed; ingestion dual-plane | **CLOSED** (LangGraph blocked per ADR-000) |

---

## Single-brain enforcement (2026-06-16)

- **ADR:** `docs/adr/ADR-000-langgraph-gate.md`
- **Test gate:** `tests/test_single_brain_architecture.py`
- **Proof:** `reports/single_brain_enforcement_cursor.txt`
- **Owner:** Agentic Foundation Q1 — Python Brain only; no second orchestration runtime

---

## Related status docs (not checkpoints)

| Doc | Purpose |
|-----|---------|
| `docs/qa/CURSOR_CHECKPOINT_REPORT.md` | Go-live / beta readiness (2026-06-15) |
| `docs/qa/CURSOR_CHECKPOINT_STATUS_DETAILED.md` | Detailed service and gate status |
| `docs/decisions/OWNER_DECISIONS_2026-06-16.md` | Resolved owner decisions (31 items) |
| `docs/handoff/` | Auto-generated handoff snapshots (context recovery) |

---

## When to add a checkpoint

- Multi-step build (ingestion, control plane) interrupted before merge.
- Subagent dispatched but transcript shows no completion.
- Owner must answer architecture questions before further implementation.

Each checkpoint must include: **Completed**, **In progress**, **Not started**, **Owner questions pending**, **Next actions** (ordered), **Commands to resume**.
