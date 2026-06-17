# ADR-000: LangGraph gate - single Brain runtime only

**Status:** ACCEPTED (enforced)  
**Date:** 2026-06-16  
**Branch:** `release/lawapp-clean-snapshot`  
**Supersedes:** `docs/architecture/LANGGRAPH_ORCHESTRATION_V1.md`, `docs/architecture/LEGAL_REASON_API_V1.md` (historical only)

## Context

LawApp's verification gate (CitationGuard, Legal Truth Validator, governance) is a security control. A second legal-reasoning orchestration runtime creates a bypass surface where generated text could reach users without the full 19-step Brain pipeline.

Owner decision (Agentic Foundation Q1, 16 June 2026): **Extend existing Python `backend/core/brain.py` + Orchestrator. No second orchestration runtime unless an ADR proves a hard requirement Python cannot meet.**

An experimental LangGraph stack (`backend/ai/graph/`, `backend/core/langgraph/`, `POST /api/v1/legal/reason`) was added in error and marked "Done" in `docs/checkpoint/INGESTION_LANGGRAPH_CHECKPOINT.md`. That violated the hard build order in `.cursor/rules/40-ai-gate.mdc`.

## Why blocked (analysis only)

| Risk | If LangGraph coexists with Brain |
|------|----------------------------------|
| **Verification gate bypass** | A second HTTP entry (`/api/v1/legal/reason`) can return legal text without traversing all 19 Brain steps, CitationGuard, and governance stages. |
| **Dual trace models** | Brain persists `brain_traces`; LangGraph used a separate `trace_id` contract. Auditors cannot prove one path was used. |
| **Adapter drift** | LangGraph duplicated retrieve, rules, and graph-enrich calls. Changes to Brain stages would not automatically apply to the graph path. |
| **Dependency surface** | `langgraph` / `langchain-core` add supply-chain and runtime weight unrelated to the DB-first, local-Ollama policy. |
| **Owner decision conflict** | Agentic Foundation Q1 (16 June 2026): extend Python Brain only; no second orchestration runtime without ADR + owner approval. |

**Coexistence is not a supported mode.** Partial rollback (docs say Brain-only but code or routes remain) is worse than full removal because it implies the gate still covers both paths when it does not.

## Decision

1. **Single reasoning runtime:** `backend/core/brain.py` is the only authorised entry to legal reasoning. All callers (chat, assess, tools, admin) delegate to Brain or its existing pipeline stages - never to a parallel graph.
2. **No LangGraph in production deps:** Remove `langgraph` and `langchain-core` from `pyproject.toml` and `Dockerfile`.
3. **No `/api/v1/legal/reason` route:** Remove `backend/api/legal_reason_routes.py` and unregister from `main.py`. Legal assessment continues via existing Brain-backed routes (`/assess`, brain trace APIs, etc.).
4. **Delete rolled-back code:** Remove `backend/ai/`, `backend/core/langgraph/`, and LangGraph-only tests.
5. **Enforcement test:** `tests/test_single_brain_architecture.py` fails CI if LangGraph paths or the legal-reason route reappear.

## Sidecar exception

The NestJS control-plane (`control-plane/`) is allowed **only** as a non-legal sidecar: retrieval metadata, queues (BullMQ), cache, and request validation. It is **not** a second reasoning runtime.

| Rule | Requirement |
|------|-------------|
| Legal answers | **Must** proxy `POST /assess` on the Python Brain (FastAPI monolith :8000). |
| CitationGuard | No bypass. Governance validates Brain responses; sidecar never serves legal text directly. |
| External LLM | Forbidden on legal paths when `ALLOW_EXTERNAL_LLM=false` (default). |
| LangGraph / Mastra | **Not allowed.** No second orchestration runtime, graph package tree, or `/api/v1/legal/reason`. |

Full sidecar spec: [`docs/architecture/CONTROL_PLANE_NESTJS_V1.md`](../architecture/CONTROL_PLANE_NESTJS_V1.md).

## Why LangGraph is blocked (build order)

Per `.cursor/rules/40-ai-gate.mdc`, legal answers must traverse: **rules → GraphRAG → local LLM → CitationGuard → fail-closed**. LangGraph was introduced as a parallel orchestration layer before that gate was proven on a single runtime. Build order requires one verification surface before adding alternate orchestrators.

## Coexistence risk analysis (not a proposal)

| Risk | Mechanism | Impact |
|------|-----------|--------|
| Dual runtime | Two orchestrators (`brain.py` vs LangGraph StateGraph) serving similar endpoints | Operators cannot know which path ran CitationGuard; traces diverge |
| CitationGuard bypass | Graph nodes calling `pipeline`/`llm` stages without full Brain step 12–14 sequence | Uncited or unverified citations could reach users |
| Drift | Duplicate retrieve/rules/reason adapters under `backend/ai/` | Bug fixes in Brain do not apply to graph nodes; behaviour diverges silently |
| Dependency creep | `langgraph` + `langchain-core` in production image | Larger attack surface; unrelated to UK employment law requirements |

**Acceptable alternatives (within gate):** extend `brain.py` internals; improve RAG retrieval (`backend.core.retrieve`); ingestion and corpus quality; strengthen CitationGuard and Legal Truth Validator. These preserve a single audit trail.

## Brain ↔ RAG reasoning spec mapping

`docs/04_RAG_REASONING_SPEC.md` pipeline:

| Spec stage | Brain implementation |
|------------|---------------------|
| CLASSIFY | `detect_claim_type`, path_splitter / `classify` |
| RETRIEVE | `retrieve_legal_evidence`, `run_rules_engine` |
| REASON | `generate_draft` via `orchestrator` / pipeline |
| SCORE | `evaluate_draft`, grounding/confidence in assessment |
| GOVERN | `verify_citations`, CitationGuard, `apply_safety_policy` |
| RESPOND | `return_answer` |

`POST /assess` enters via `MotherController`, which calls `backend.core.brain.orchestrator` for the generative lane (not LangGraph).

## Agentic Foundation reference

**Decision 1 (Mastra vs Python Brain):** Extend existing Python `backend/core/brain.py` + Orchestrator. No Mastra sidecar unless a future ADR proves a hard requirement Python cannot meet. Owner endorsement: second orchestration runtime increases CitationGuard bypass risk (`docs/architecture/AGENTIC_FOUNDATION_QUESTIONS.md`).

## Consequences

### Positive

- One gate, one trace model, one place to audit CitationGuard and governance.
- Aligns with owner decisions on Mastra/Python Brain, domain fail-closed, and DB-first legal truth.
- Removes duplicate retrieve/rules/reason adapters that drifted from Brain stages.

### Negative

- Any future need for graph-based orchestration must go through an ADR and owner approval, then extend Brain internals - not a new HTTP surface or package tree.

## Owner decisions resolved (build order)

| Area | Decision |
|------|----------|
| Orchestration | Python Brain only for legal reasoning; NestJS control-plane sidecar for retrieval/queues/cache only (see Sidecar exception); no LangGraph/Mastra/second runtime (Agentic Q1) |
| Graph engine | Postgres `legal_nodes` / `legal_edges`; no Neo4j container (Deployment Q2) |
| Knowledge schema | `provision` canonical; `corpus_chunks` as embedding layer (Q1, Feature §5 #2) |
| Embeddings | 1024-dim local model; re-embed corpus (Q5) |
| Domain scope | `employment_uk` only; fail closed elsewhere (Agentic Q5) |
| Verification gate | LLM proposes; DB + CitationGuard + human review promote (40-ai-gate) |
| K8s manifests | `infra/k8s/` canonical (Q8) |
| Admin reviewer UI | `lawapp-admin-service` port 8007 with SSO/MFA (Q9) |

## Remaining work (NOT LangGraph)

- **Migration 084:** `db/migrations/084_ingestion_jobs_dual_plane.sql` - dual-plane ingestion jobs.
- **Corpus:** seed, re-embed 1024, provision backfill per owner Q1/Q5.
- **Case OS beta:** matter bridge, hub Wave 2, honest module coverage API (Q13).

## References

- `.cursor/rules/40-ai-gate.mdc`
- `docs/decisions/OWNER_DECISIONS_2026-06-16.md`
- `docs/architecture/AGENTIC_FOUNDATION_QUESTIONS.md`
- `docs/architecture/CONTROL_PLANE_NESTJS_V1.md`
- `backend/core/brain.py`
