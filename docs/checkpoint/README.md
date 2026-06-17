# LawApp Checkpoints

**DEBUG ARTIFACT — NOT ARCHITECTURE TRUTH. See ADR-000 + git log.**

Session checkpoint documents are debug/resume aids only. They are **not**
authoritative architecture or gate status.

## Single source of truth

**Architectural truth = git commits on `release/lawapp-clean-snapshot` +
`docs/adr/ADR-000-langgraph-gate.md` only.**

**Status:** PRE-BETA. C-F gates remain open until grounding evidence is in
`reports/beta_gate_evidence_unified.txt` on remote.

**Branch:** `release/lawapp-clean-snapshot`

---

## Index (debug snapshots)

| Checkpoint | Scope |
|------------|-------|
| [INGESTION_LANGGRAPH_CHECKPOINT.md](./INGESTION_LANGGRAPH_CHECKPOINT.md) | Ingestion 084, LangGraph rollback notes |
| [MULTI_LANGUAGE_CHECKPOINT.md](./MULTI_LANGUAGE_CHECKPOINT.md) | EN/AR language engine |

LangGraph STOPPED per ADR-000. Verify via commits + `tests/test_single_brain_architecture.py`.

---

## Gate evidence (owner review bundle)

When proof scripts are run, results belong in **one** report:

`reports/beta_gate_evidence_unified.txt`

Do not treat scattered `reports/*_cursor.txt` files or this README as gate PASS/FAIL truth.

Proof scripts: `scripts/proof/audit_case_os_beta.py`, `verify_ingestion_084.py`,
`verify_grounding.py`, `verify_multi_language.py`, `verify_domain_plugin.py`.

---

## Related authoritative docs

| Doc | Purpose |
|-----|---------|
| `docs/adr/ADR-000-langgraph-gate.md` | Single-brain gate; LangGraph blocked |
| `docs/decisions/OWNER_DECISIONS_2026-06-16.md` | Resolved owner decisions |

---

## When to add a checkpoint

- Multi-step build interrupted before merge.
- Subagent dispatched but transcript shows no completion.

Each checkpoint must label itself as debug artifact and must **not** claim C-F PASS.
