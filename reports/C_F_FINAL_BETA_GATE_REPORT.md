# C-F Final Beta Gate Report

> **SUPPLEMENTARY — see `reports/beta_gate_evidence_unified.txt` for authority.**
> This file must not contradict the unified bundle or claim BETA READY YES.

**BETA READY: NO** (Gate D live ingestion proof FAIL — Docker daemon not running; 2 i18n API tests FAIL without DB)

Generated: 2026-06-17  
Repo: serverax/lawapp  
Branch: `release/lawapp-clean-snapshot`  
Commit: see `git rev-parse --short HEAD` at commit time

---

## Gate summary

| Gate | Description | Verdict | Evidence |
|------|-------------|---------|----------|
| **C** | Case OS audit — honesty banner, boundary footer, Ready to read / Coming soon labels | **PASS** | `reports/case_os_beta_ship_cursor.txt` |
| **D** | Ingestion 084 — migration apply, pipeline, embeddings, idempotency | **FAIL** | `reports/ingestion_084_cursor.txt` (code PASS; live DB/Docker unreachable) |
| **E** | Grounding — CitationGuard on assess/brain path | **PASS** | `reports/grounding_verification_cursor.txt` |
| **F** | i18n + domain — assessment_core equivalence; no translate APIs; employment fail-closed | **PASS** (code) / **PARTIAL** (2 i18n API tests need DB) | `reports/i18n_equivalence_proof.txt`, `reports/multi_language_verify_cursor.txt`, `reports/domain_plugin_verify_cursor.txt` |
| **SB** | Single Brain — no LangGraph / legal/reason bypass | **PASS** | `reports/single_brain_enforcement_cursor.txt` |

---

## Locked invariants verified

| Invariant | Result | Evidence |
|-----------|--------|----------|
| Legal output: retrieve_hybrid → brain.py → CitationGuard → response | **PASS** | `tests/test_grounding_regression.py` 11 passed; static checks in grounding report |
| Graph/Neo4j retrieval only; /assess does not call :8018 for legal output | **PASS** | No `8018`/`graph/search` in `backend/api/main.py` or `backend/core/control_plane/` |
| assessment_core identical en/ar (same input) | **PASS** | `reports/i18n_equivalence_proof.txt` — empty diff |
| employment_uk only; others fail closed | **PASS** | `reports/domain_plugin_verify_cursor.txt` |
| LangGraph STOPPED (33abd9c) | **PASS** | `rg -i langgraph backend/` zero hits; `tests/test_single_brain_architecture.py` 13 passed |

---

## Pytest bundle (2026-06-17, no Docker)

| Suite | Result |
|-------|--------|
| test_single_brain_architecture.py | 13 passed |
| test_grounding_regression.py | 11 passed |
| test_no_translation_invariant.py + test_language_engine_router.py | 9 passed |
| test_domain_plugin_system.py | 9 passed |
| test_i18n_api.py (MotherController paths) | **2 FAILED** — `psycopg2.OperationalError` port 5435 connection refused |

**Total without DB-dependent i18n tests:** 42 passed

---

## Grep evidence

### `rg -i "langgraph|legal/reason" backend/`

**Result:** zero matches — `reports/_grep_langgraph_backend.txt` (empty)

### `rg -i "google.*translate|deepl|azure.*translator" backend/`

**Result:** zero matches — `reports/_grep_translate_backend.txt` (empty)

### /assess → brain.py (not graph service for reasoning)

| Layer | Evidence |
|-------|----------|
| `backend/api/main.py` `@app.post("/assess")` | `MotherController().process()` |
| `mother_controller.py` L151-162 | `brain.orchestrator.execute_generative_lane()` |
| `mother_controller.py` L181-183 | `_apply_language_layer()` **after** govern (presentation only) |
| Graph HTTP on assess path | **None** in control plane or main API |

---

## Gate D failure detail

`scripts/proof/verify_ingestion_084.py` verdict **FAIL**:

- Live DB: connection refused on `localhost:5435`
- Docker: `dockerDesktopLinuxEngine` pipe not found (Docker Desktop not running)
- Idempotent pipeline re-run: blocked (no Docker)

Code-path checks (migration file, workers, Ollama 1024 embedder, FCL disabled, chunk_hash idempotency) all **PASS**.

**Resume:** `docker compose up -d db redis` then re-run `python scripts/proof/verify_ingestion_084.py`

---

## Gate F detail

1. **assessment_core equivalence:** PASS — `reports/i18n_equivalence_proof.txt`
2. **No third-party translate APIs:** PASS — grep + `test_no_translation_invariant.py`
3. **No :8018 on /assess:** PASS — code trace
4. **Post-brain language router:** PASS — `MotherController._apply_language_layer` after govern
5. **Domain fail-closed:** PASS — `reports/domain_plugin_verify_cursor.txt`

---

## Violations fixed during closure

| Fix | Reason |
|-----|--------|
| Restored `tests/test_single_brain_architecture.py` (8981c53 enforcement version) | Test file had been flipped to require LangGraph |
| Removed untracked `backend/ai/`, LangGraph install scripts, `test_langgraph_legal_reason.py` | Forbidden artifacts per ADR-000 |
| Added `scripts/proof/i18n_equivalence_proof.py` | Mandatory F equivalence artifact |
| Updated `docs/checkpoint/*` | DEPRECATED LangGraph banner + C-F gate table |

---

## Checkpoint updates

- `docs/checkpoint/INGESTION_LANGGRAPH_CHECKPOINT.md` — DEPRECATED banner, 33abd9c rollback, gate table
- `docs/checkpoint/README.md` — advisory-only LangGraph rule, C-F status

---

## Owner summary

**C, E, SB, and F (code-level) PASS** with evidence on disk. Single Brain architecture re-enforced after LangGraph artifacts reappeared on the branch.

**Gate D FAIL** blocks beta-ready: Docker/Postgres not available for migration 084 live proof and pipeline idempotency re-run.

**BETA READY: NO** until Docker is up and Gate D proof is re-run green. Re-run command:

```bash
docker compose up -d db redis
python scripts/proof/verify_ingestion_084.py
pytest tests/test_i18n_api.py -q
```
