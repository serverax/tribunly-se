# Agentic Foundation  -  Implementation Plan

Maps five pillars to concrete files and phases. **Phase 1** (this session) scaffolds real, wired code  -  no fake success paths.

## Pillar → File Map

| Pillar | Existing assets | Phase 1 additions |
|--------|-----------------|-------------------|
| **1. Orchestration** | `brain.py` (19-step), thin `Orchestrator`, `agents/registry.py`, `domains/registry.py` | `orchestrator.py` (classify→route→delegate→merge), `agents/domain_plugins.py`, wire delegation in `run_brain` |
| **2. RAG** | `retrieve.py` (hybrid + RRF), `retrieval/trust_scorer.py`, `lawapp-rag-service` | `retrieval/rerank.py` (score-based rerank after trust), ensure `pipeline.assess` always calls `retrieve` first |
| **3. Compliance / Audit** | `pipeline.govern`, `citation_guard`, `lawapp-audit-service`, `brain_traces` | Migration `076_agentic_foundation.sql`, extend `_write_brain_audit`, compliance fields on trace |
| **4. Adaptive feedback** | `user_feedback`, `feedback_registry` | `agent_feedback` + `agent_memory` tables, `api/feedback_routes.py`, `agent_memory.py` (PII mask) |
| **5. Modular tools** | `core/tools.py` (preview funnel) | `core/tool_registry/` (registry + deadline + Companies House stub + document extract interface) |

---

## Phase 1  -  Implemented Now

### 1. Orchestration

- [x] `Orchestrator` interface: `classify` → `route` → `delegate` → `merge` → `run_stages`
- [x] Domain plugin: `EmploymentUkPlugin` (`employment_uk` / `employment`)
- [x] Agent delegation after hybrid retrieval in `run_brain` (step 11b)
- [x] Orchestration summary recorded on `BrainTrace`

### 2. RAG

- [x] Audit: hybrid + RRF already in `retrieve.py`; rag-service mirrors FTS+vector
- [x] Add `rerank_authorities()`  -  combines RRF, trust_score, exact-citation boost
- [x] Pipeline unchanged: `assess()` calls `retrieve()` before reasoning (existing guardrail)

### 3. Compliance / Audit

- [x] Every assess path: `pipeline.assess` → `govern` → `insert_audit_log` (existing)
- [x] Brain path: citation verify + safety + `_write_brain_audit`
- [x] New trace columns: `compliance_verdict`, `reasoning_chain_summary`, `orchestration_stages`

### 4. Feedback (scaffold)

- [x] `agent_feedback` table (user corrections, trace-linked)
- [x] `agent_memory` table (masked key/value, consent-gated)
- [x] `POST /api/feedback` (auth-gated when `LAWAPP_AUTH_MODE != none`)

### 5. Tools (scaffold)

- [x] `ToolRegistry` with `deadline_calculate`, `companies_house_lookup` (stub), `document_extract` (interface)
- [x] Orchestrator exposes `available_tools` from domain plugin + registry

---

## Phase 2  -  Next

1. **Agent outcomes in assessment**  -  merge high-confidence agent findings into structured assessment (not trace-only).
2. **Cross-encoder rerank**  -  optional local model behind env flag `RERANK_MODEL_ENABLED`.
3. **Companies House live**  -  wire API key, rate limit, cache in Redis.
4. **Document extract**  -  connect to upload/OCR pipeline (`document_facts`).
5. **Feedback → optimizer**  -  batch export to `feedback_registry` / DSPy optimizer (read-only queue consumer).
6. **brain_traces immutability triggers**  -  verify UPDATE/DELETE blocked in prod DB.

---

## Phase 3  -  Hardening

- EU AI Act retention policy automation
- Multi-domain plugins (immigration, housing) behind `register_domain`
- E2E proof: orchestration stages visible in `/api/brain/trace/{id}`
- Load test tool-calling path under 10k concurrency target

---

## Verification Commands

```bash
# Unit tests (Phase 1 scaffolding)
pytest tests/test_agentic_foundation_phase1.py -q

# Orchestrator + brain imports
python -c "from backend.core.orchestrator import Orchestrator; from backend.core.tool_registry import get_tool_registry; print('ok')"

# Migration present
ls db/migrations/076_agentic_foundation.sql
```

---

## Non-negotiables (standing orders)

- Local Ollama default; no external LLM bypass
- CitationGuard / corpus grounding on generative paths
- UK employment law first; fail-closed on unsupported jurisdiction
- Scaffolds return honest errors  -  no fabricated legal data or citations
