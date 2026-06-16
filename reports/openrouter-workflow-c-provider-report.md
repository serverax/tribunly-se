# OpenRouter Workflow C Provider Plug  -  Report

**Date:** 2026-06-04 | **Status: DONE AND PROVEN (mocked, no owner key needed)**

Principle enforced: **LEGAL DB FIRST → RULES FIRST → CITATIONS FIRST → AI SECOND → FAIL-CLOSED ALWAYS.** OpenRouter is a *replaceable provider plug*, not the brain.

## Architecture (where the provider sits)
```
local DB + RAG + rules + algorithm  →  de-identify  →  provider plug interface
   →  OpenRouter (now) / Gemini / local (later)  →  4 AIA validators  →  accept only if all pass
```

## Files added
- `backend/core/llm_provider.py`  -  `LLMProvider` interface + `StubProvider`, `OpenRouterProvider`, `GeminiProvider` (placeholder), `LocalLLMProvider` (placeholder); `get_provider()` defaults to OpenRouter only when `OPENROUTER_ENABLED=true` AND a real key is present, else **StubProvider fail-closed (no crash)**.
- `backend/core/agentic/aia_validators.py`  -  the 4 gates: **AIA1 Citation** (cited authority must be in the RAG bundle), **AIA2 Rules** (deterministic values must equal the rules table), **AIA3 PII boundary** (no PII in outbound payload), **AIA4 Legal boundary/honesty** (no "guaranteed win"/"we will file"/solicitor implication; weaknesses required).
- `tests/test_openrouter_provider.py`  -  provider + AIA tests.
- `.env.example`  -  `OPENROUTER_ENABLED/API_KEY/BASE_URL/MODEL/TIMEOUT/MAX_TOKENS/TEMPERATURE/SITE_URL/APP_NAME` (all blank  -  **no secret**).
- `scripts/prove_openrouter_workflow_c.sh`.
- The OpenRouter call routes through `backend/core/agentic/litellm_adapter.py` (the **single** LiteLLM gateway) whose PII chokepoint fails closed.

## Proof (raw)
```
scripts/prove_openrouter_workflow_c.sh
  37 passed in 14.40s
  PASS: litellm only imported by the adapter/provider plug   (not hardwired)
  PASS: no real OpenRouter key in tracked files
  OPENROUTER WORKFLOW C PROOF: PASSED
```
Covered cases: provider disabled → Stub fail-closed; missing key → Stub, no crash; OpenRouter not available when disabled; cloud call fails closed when unavailable; provider swappable (gemini/local placeholders); **AIA1** hallucinated citation rejected / real accepted; **AIA2** altered deadline/cap rejected; **AIA3** raw PII rejected before call (NI/email/postcode/phone scrubbed by the gateway); **AIA4** reserved wording rejected + missing-weaknesses rejected.

## Key handling (safe)
- Key read from `os.environ/OPENROUTER_API_KEY` only; never hardcoded, never logged, never in frontend. `.env` is gitignored (proven). `/health` exposes `openrouter_configured: true|false` only.

## Remaining (honest)
- **IMPLEMENTED BUT NOT PROVEN (live):** an actual OpenRouter 200 OK round-trip  -  **BLOCKED BY OWNER** (no key in env; the founder will add `OPENROUTER_ENABLED=true` + key to `.env`). Mocked tests fully cover behaviour.
- **NOT STARTED:** wiring the provider plug into the live `/assess` pipeline (Workflow C currently uses the deterministic `pipeline.assess` + StubReasoningModel; the plug + validators are built and unit-proven, integration into the live endpoint is the next step).

**Verdict:** Provider plug + 4 AIA validators **DONE AND PROVEN** (mocked); live round-trip + pipeline integration are the only remaining items (owner key + integration).
