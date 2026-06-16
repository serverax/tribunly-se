# BUILD ORDER checkpoint

**Branch:** `release/lawapp-clean-snapshot`  
**Updated:** 2026-06-16  
**Supersedes focus:** ingestion + LangGraph → **owner build order 1-7**

## Build order status

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | Case OS beta ship (honesty + boundary + coverage labels) | **DONE** | `reports/case_os_beta_ship_cursor.txt` |
| 2 | Dual-plane ingestion + corpus (migration 084, 1024 local embed) | **DONE** (local) | `db/migrations/084_ingestion_jobs_dual_plane.sql`, `reports/ingestion_dual_plane_cursor.txt` |
| 3 | LangGraph STOP gate | **DONE** | `docs/adr/ADR-000-langgraph-gate.md` |
| 4 | Multi-language EN/AR verify | **DONE** | `reports/multi_language_verify_cursor.txt` |
| 5 | Domain plugin fail-closed | **DONE** | `reports/domain_plugin_verify_cursor.txt` |
| 6 | Checkpoint (this file) | **DONE** | — |
| 7 | SSH IdentityFile tilde fix | **DONE** | `reports/ssh_config_housekeeping_cursor.txt` |

## Owner decisions — RESOLVED (do not re-ask)

All 11 deployment-plan questions + feature/agentic items are recorded in `docs/decisions/OWNER_DECISIONS_2026-06-16.md`. Summary:

1. **Q1 Schema:** `provision` canonical; `corpus_chunks` = embedding layer referencing `provision.id`.
2. **Q2 Graph:** Postgres `legal_nodes`/`legal_edges`; no Neo4j as default.
3. **Q3 Module taxonomy:** 16 codes; map 24 employment keys; honest 11 production / partial labels.
4. **Q4 FCL:** sample-only until written Computational Analysis Licence.
5. **Q5 Embeddings:** 1024-dim local (`bge-large-en-v1.5` / `mxbai-embed-large` via Ollama); no `text-embedding-3-small`.
6. **Q6 Phase 0:** parallel with k6/Ollama fixes; risky phases gated.
7. **Q7 Corpus DB:** shared DB, `knowledge.*` schema.
8. **Q8 K8s:** `infra/k8s/` canonical; deprecate `k8s/`.
9. **Q9 Admin reviewer:** lawapp-admin-service (8007), SSO+MFA.
10. **Q10 ERA 2025:** scheduled detection + human sign-off.
11. **Q11 Licensing:** owner sign-off per `legal_source` row before go-live.

Plus agentic endorsements: **no second orchestration runtime**, RLHF queue-only, **employment_uk only** for answers, bilingual split (UI any provider; case facts on-device/self-hosted only).

## LangGraph STOP gate

See `docs/adr/ADR-000-langgraph-gate.md`. No `/api/v1/legal/reason` on this branch.

## Genuinely open (owner / ops)

- FCL written grant status (owner)
- Partner org signing (owner)
- Companies House API key (owner)
- ACAS/EHRC/HSE licence rows (owner)
- Staging cluster provisioning (owner)
- Track C production entry (independent gate)
- Live docker corpus re-embed at scale when Ollama + DB available in target env

## Resume commands

```bash
cd F:/lawapp
python -m ingestion.freshness.report
python scripts/corpus_count_report.py
python scripts/test_ingestion_connector_idempotency.py
pytest tests/test_unified_indexer_dual_write.py tests/test_control_plane_governance.py -q
```
