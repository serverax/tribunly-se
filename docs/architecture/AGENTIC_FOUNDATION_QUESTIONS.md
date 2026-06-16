# Agentic Foundation  -  Open Questions

**Status:** RESOLVED 16 June 2026. Owner endorsements: [`docs/decisions/OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md) (Agentic Foundation section).

Documented defaults let Phase 1 proceed. Owner endorsed all six items on 2026-06-16.

## Architecture

### Mastra (TypeScript) vs Python Brain  -  RESOLVED

**Decision:** Extend existing Python `backend/core/brain.py` + `Orchestrator`. No Mastra sidecar unless a future ADR proves a hard requirement Python cannot meet.

**Owner:** Endorse strongly. Second orchestration runtime increases CitationGuard bypass risk.

---

## Learning & Feedback

### RLHF / fine-tuning policy  -  RESOLVED

**Decision:** Feedback queue only (`agent_feedback` + `feedback_registry`). No model weight updates. Phase 2 DSPy optimizer as read-only queue consumer through eval harness. Never RLHF the generator.

**Owner:** Endorse.

---

## External integrations

### Companies House API  -  RESOLVED (stub until owner key)

**Decision:** Stub tool with `COMPANIES_HOUSE_API_KEY` env gate; honest unavailable when absent.

**Owner action:** Register free API key; confirm ~600 req/5min limits and terms. Cache in Redis. Public data, low privacy risk.

---

## Compliance

### EU AI Act logging retention  -  RESOLVED

**Decision:** No auto-purge Phase 1. Immutable traces store metadata, decisions, hashes only (never raw special-category content). Case data: limitation-driven erase/anonymise. PII-free audit/traces: 12+ months.

**Owner:** Endorse with UK GDPR storage-limitation correction.

---

## Domain expansion

### Beyond employment_uk  -  RESOLVED

**Decision:** `employment` only enabled domain in `backend/domains/registry.py`. New domains gated on corpus, verification, tests. Fail-closed on unsupported jurisdiction.

**Owner:** Endorse strongly.

---

## Tool calling

### Orchestrator tool path vs preview tools  -  RESOLVED

**Decision:** Separate surfaces; shared deterministic implementations. Public preview enforces no anonymous special-category persistence. Agent registry tools carry auth and audit.

**Owner:** Endorse.
