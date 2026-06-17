# DEBUG ARTIFACT — NOT ARCHITECTURE TRUTH

> **Do not treat this file as authoritative state.** Architectural truth =
> git commits on `release/lawapp-clean-snapshot` +
> `docs/adr/ADR-000-langgraph-gate.md` only.

**Status:** PRE-BETA. C-F gates remain open until grounding evidence appears in
`reports/beta_gate_evidence_unified.txt` on remote.

---

## LangGraph (STOPPED — verify via ADR + commits only)

LangGraph orchestration is blocked per ADR-000. Single Brain runtime:
`backend/core/brain.py`. Enforcement: `tests/test_single_brain_architecture.py`.

Reference commits: `eccdef7`, `088cec1`. Do not infer runtime state from this
checkpoint; read ADR-000 and the release branch git log.

Graph RAG is retrieval only (Postgres `legal_nodes` / `legal_edges`).

## Owner decisions (locked — reference copy)

| Topic | Decision |
|-------|----------|
| Knowledge schema | `provision` canonical; `corpus_chunks` embedding layer |
| Graph engine | Postgres `legal_nodes` / `legal_edges` |
| Module map | 16 canonical modules + tag layer; beta UI shows 11 topics honestly |
| Embeddings | 1024-dim local via Ollama |
| Find Case Law bulk | Not granted — sample/manual only |
| Domain scope | `employment_uk` retrieval; pack code `employment` only enabled |

## Ingestion dual-plane (084) — debug notes

- Migration: `db/migrations/084_ingestion_jobs_dual_plane.sql`
- Workers: `ingestion/workers/`
- Re-embed: `scripts/reembed_corpus_1024.py`

## Proof commands (resume / debug only)

```bash
python scripts/proof/audit_case_os_beta.py
python scripts/proof/verify_ingestion_084.py
python scripts/proof/verify_grounding.py
python scripts/proof/verify_multi_language.py
python scripts/proof/verify_domain_plugin.py
pytest tests/test_single_brain_architecture.py tests/test_grounding_regression.py -q
```

Gate evidence (when run): `reports/beta_gate_evidence_unified.txt`
