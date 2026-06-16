# Agentic Foundation  -  Open Questions

Documented defaults let Phase 1 proceed without blocking. Revisit before Phase 2+.

## Architecture

### Mastra (TypeScript) vs Python Brain

**Question:** Mastra is TypeScript; LawApp is Python  -  extend existing Brain vs add Mastra sidecar?

**Default (Phase 1):** Extend the existing Python `backend/core/brain.py` + `Orchestrator`. No Mastra sidecar unless a future ADR proves a hard requirement (e.g. Mastra-specific workflow UI).

**Rationale:** Brain already enforces 19-step pipeline, CitationGuard, local Ollama routing, and `brain_traces` audit. A second orchestration runtime would duplicate guardrails and increase bypass risk.

---

## Learning & Feedback

### RLHF / fine-tuning policy

**Question:** Local-only fine-tune policy vs feedback queue only for now?

**Default (Phase 1):** Feedback queue only  -  `agent_feedback` table + `feedback_registry` for post-outcome signals. No model weight updates, no external training APIs.

**Rationale:** Standing orders require local Ollama default and fail-closed legal grounding. RLHF without provenance controls risks citation drift.

---

## External integrations

### Companies House API

**Question:** Is a Companies House API key available for production?

**Default (Phase 1):** Stub tool registered with `COMPANIES_HOUSE_API_KEY` env gate; returns `experimental: true` + honest unavailable message when key absent. No fabricated company data.

**Action needed:** Owner to provision key and confirm rate limits / licence terms before enabling live lookups.

---

## Compliance

### EU AI Act logging retention

**Question:** What retention period applies to brain traces, audit logs, and agent feedback under EU AI Act / UK AI regulatory posture?

**Default (Phase 1):** Persist immutable `brain_traces` + `audit_events` + new `agent_feedback` rows with existing retention migration (`012_phase6_encryption_retention.sql`) as baseline. No automatic purge in Phase 1.

**Action needed:** Legal/compliance owner to set explicit retention windows (e.g. 7y employment records vs shorter telemetry) and map to `audit_events` / `brain_traces` policies.

---

## Domain expansion

### Beyond employment_uk

**Question:** When to register immigration/housing domain plugins?

**Default:** `employment` remains the only **enabled** domain in `backend/domains/registry.py`. `domains/employment_uk/` is the first domain plugin pack; others stay disabled until rules + corpus + tests exist.

---

## Tool calling

### Orchestrator tool path vs preview tools

**Question:** Should public `/api/tools/*` preview endpoints share the agent tool registry?

**Default (Phase 1):** Separate surfaces  -  preview tools stay in `backend/core/tools.py` (anonymous funnel). Agent tool registry (`backend/core/tool_registry/`) is for orchestrator/brain tool-calling only. Shared implementations (e.g. deadline) delegate to the same deterministic functions.
