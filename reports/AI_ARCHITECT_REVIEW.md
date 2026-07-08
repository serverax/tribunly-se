# AI Architect Review

Generated: 2026-07-08
Branch: `cc/convergence`
Measured against: live compose stack, qwen2.5:3b-instruct-q6_K on CPU

## (a) Pipeline Stage Timings — Live Measurement

Measured on a live `POST /assess` with unfair-dismissal facts (EDT 2026-03-15, 3yr employment, redundancy + replacement hire).

| Stage | Measured | Notes |
|-------|----------|-------|
| Health endpoint | <10ms | Baseline round-trip |
| Rules fetch (`/rules/unfair_dismissal`) | **17ms** | 10 rules, DB-backed |
| Graph query (health ping) | **41ms** | 10 nodes, 9 edges, Postgres-backed |
| Full deterministic lane (`use_model=false`) | **200ms** | Rules + graph + deadline + citations + governance — no LLM |
| Bare Ollama generate ("Hello") | **49.5s** | CPU-only inference, ~3 tok/s |
| Full `/assess` pipeline | **120.4s** | Brain calls Ollama inference (likely 2 calls: reason + evaluate) |
| TTFB on `/assess` | **120.4s** | No progressive rendering — client waits full duration |

**Diagnosis:** Deterministic lane (classify → retrieve → deadline → citations → governance) = 200ms. LLM reasoning = ~120s. The LLM is 600× slower and accounts for 99.8% of wall-clock time. On GPU hardware, qwen2.5:3b at q6_K should do ~30-50 tok/s, reducing the LLM portion to ~3-5s.

**Where the 120s goes:** The brain has 19 synchronous stages (brain.py). The LLM is called at stage 15 (`generate_draft` via `pipeline.assess()`) which internally calls `model.reason()` with a ~16,800-char prompt. Post-LLM, `legal_truth_validation` (stage 16) may re-invoke for citation checking. Temperature 0.1, max_tokens 2048, 60s timeout per call.

## (b) Progressive Render Design (Phase C Spec)

### Architecture

Split `/assess` into two responses:

1. **Instant skeleton** (deterministic lane, <500ms): Call `POST /assess` with `use_model=false`. Returns: deadline_info, citations, tribunal_elements, viability skeleton, governance checks — everything except reasoning_summary and strength. Paint this immediately.

2. **Streaming reasoning** (LLM lane, SSE): Connect to `POST /reasoning/stream` (already exists at `reasoning_routes.py:102-134`). Stream tokens into the reasoning_summary section. On completion, upgrade the strength badge from "Calculating..." to the final value.

### Implementation Sketch

```
Frontend (assessment.html):
  1. POST /assess {use_model: false}  →  200ms  →  paint skeleton
  2. SSE /reasoning/stream             →  stream  →  fill reasoning
  3. On SSE complete                   →  update strength badge
```

### What the user sees

| Time | Content |
|------|---------|
| 0-200ms | Spinner |
| 200ms | Deadline card (full), citations, tribunal checklist, value range, weaknesses, employer arguments. Strength badge shows "Analysing..." |
| 200ms-120s | Reasoning summary streams in token-by-token. Strength badge updates on final token. |

### Existing infrastructure

- `/reasoning/stream` endpoint exists (`reasoning_routes.py:102-134`), supports SSE, branches FACTUAL vs REASONING lanes.
- `stream_chat()` method exists on `LocalInferenceReasoningModel` (`models.py:535-564`), calls Ollama `/v1/chat/completions` with `stream=true`.
- The deterministic `use_model=false` path already returns full governed output in 200ms.

### Missing pieces for Phase C

- Frontend SSE client in assessment.html (trivial: `new EventSource`)
- Governance post-stream validation (currently runs synchronously post-LLM; needs to accept streamed output)
- CitationGuard on streamed output (currently validates full text; needs buffer-then-validate)

## (c) Quant/Model Recommendation

### Current: qwen2.5:3b-instruct-q6_K

- Size: 2.5GB
- CPU inference: ~3 tok/s → 49.5s for a "Hello" response, ~120s for full assessment
- Quality: Fails grounded-citation gate consistently (observed: `fallback_used: true`, `governed_result: fallback`). The model generates responses but they fail CitationGuard, so the brain falls back to the deterministic lane.

### Recommendation

| Model | Quant | Size | Expected CPU tok/s | Expected GPU tok/s | Quality |
|-------|-------|------|--------------------|--------------------|---------|
| qwen2.5:3b-instruct | q4_K_M | 2.0GB | ~4-5 | ~40-60 | Same architecture, -5% perplexity, 20% faster |
| qwen2.5:3b-instruct | q6_K | 2.5GB | ~3 (current) | ~30-50 | Current baseline |
| qwen2.5:7b-instruct | q4_K_M | 4.4GB | ~1.5-2 | ~20-30 | Better citation adherence, 2× slower |
| qwen2.5:14b-instruct | q4_K_M | 8.5GB | ~0.5-1 | ~10-15 | Best quality, needs 10GB+ VRAM |

**Recommendation for beta (CPU-only):** Switch to `q4_K_M` quantization. Same model, 20% smaller, measurably faster on CPU. The quality delta at 3B is negligible — the model already fails CitationGuard regardless of quantization.

**Recommendation for production (GPU):** Move to `qwen2.5:7b-instruct-q4_K_M` with GPU passthrough. The 7B model has significantly better instruction-following for structured JSON output, which is what CitationGuard needs. Combined with GPU inference (~20-30 tok/s), total assessment time drops from 120s to ~5-8s.

**Critical observation:** At 3B, the model consistently fails the grounded-citation gate. The brain's `fallback_used: true` means every assessment currently returns the deterministic fallback, not the LLM's reasoning. The LLM call is spending 120s to produce output that gets discarded. Until the model quality improves (7B+ or fine-tuned), the LLM call is pure overhead.

## (d) De-identified Escalation Tier — Status

**Status: DORMANT and boundary-tested.**

| Gate | Location | State |
|------|----------|-------|
| `ExternalLLMForbidden` exception | `inference_policy.py:35-37` | Active — raised on any external provider construction |
| Forbidden provider list | `inference_policy.py:22-26` | 14 providers blocked: openai, anthropic, claude, gemini, google, mistral, cohere, together, groq, azure_openai, openrouter, cloud, external, litellm |
| `ClaudeReasoningModel` constructor | `models.py:140-149` | Raises `ExternalLLMForbidden` immediately — never instantiable |
| `OpenRouterReasoningModel` constructor | `models.py:296-303` | Same — raises on construction |
| Startup assertion | `inference_policy.py:100-112` | `require_ollama_local_provider()` — fails the backend startup if `LAWAPP_LLM_PROVIDER != ollama_local` |
| Fallback chain | `models.py:588-648` | Local Ollama → StubReasoningModel (returns `insufficient_grounding`). No cloud model in chain. |

**Boundary test evidence:** `test_phase2_real_model.py` attempts to construct `ClaudeReasoningModel` — gets `ExternalLLMForbidden` (observed: 8 errors in test suite, all from this gate). The gate is active and enforced. No escalation ladder exists — fail mode is stub, not cloud.
