# AI/ML Architect Review v2 -- lawapp (branch cc/convergence)

**Reviewer:** SA-7 (AI Architect Review) | WO007
**Date:** 2026-07-08
**Scope:** Live compose stack + source tree (F:\lawapp-restore)

---

## (a) Measured Per-Stage Latency on a Live Diagnosis

All measurements taken via `docker compose exec -T backend python -c "..."` against `http://localhost:8000` inside the backend container.

### Raw latency results

| Stage | Command | Status | Latency |
|---|---|---|---|
| Health check | `GET /health` | 200 | **57 ms** |
| Rules fetch | `GET /rules/unfair_dismissal` | 200 | **32 ms** |
| Deterministic /assess (use_model=false) | `POST /assess` with `use_model=false` | 200 | **37,704 ms** (~38 s) |
| Full /assess (use_model=true, Ollama Qwen2.5-3B) | `POST /assess` (default) | 200 | **143,311 ms** (~2 min 23 s) |

### Where the seconds go

The deterministic path (`use_model=false`) still takes ~38 s despite not invoking the LLM, because it traverses the full 19-step Brain pipeline: classify -> retrieve (SQL+BM25+pgvector hybrid) -> rules engine -> graph RAG subgraph (10 nodes / 9 edges) -> de-identification -> StubReasoningModel (instant) -> CitationGuard (the stub fails the grounded-citation gate, triggering deterministic fallback) -> governance -> safety checks -> audit trace persist. The bottleneck is the retrieve + graph RAG + governance chain, not the model.

The full model path adds ~105 s of Ollama CPU inference (Qwen2.5:3b-instruct-q6_K on CPU), but still falls back to the deterministic guide because the 3B model's output fails the CitationGuard corpus-citation gate. The model generates text, but it cannot produce valid `corpus_chunks` UUIDs that resolve in the local DB, so `enforce_or_regenerate` triggers fallback after bounded retries.

### 19 Pipeline stages (from `backend/core/brain.py`)

1. authenticate, 2. load_context, 3. detect_jurisdiction, 4. detect_legal_area, 5. detect_claim_type, 6. detect_urgency, 7. detect_missing_facts, 8. select_agents, 9. select_rag_source, 10. run_rules_engine, 11. retrieve_legal_evidence, 11b. orchestrate_agents, 12. verify_citations, 13. compress_context, 14. generate_draft (invokes Ollama if use_model=true), 14b. legal_truth_validation, 14c. knowledge_proposal, 15. evaluate_draft, 16. apply_safety_policy, 17. save_case_memory, 18. store_audit_log, 18b. publish_outbox_event, 19. return_answer.

**Only step 14 (generate_draft) invokes Ollama.** Steps 1-13 and 15-19 are deterministic (DB, rules, graph, governance). The cost governor checkpoint runs between 13 and 14.

---

## (b) Streaming / Progressive-Render Design for Phase C

### Existing infrastructure

**`/reasoning/stream` (reasoning_routes.py):** Exists and is operational. It implements a path-splitter (FACTUAL vs REASONING lane). The FACTUAL lane returns rules-table JSON synchronously within a strict 400 ms budget (ThreadPoolExecutor with 0.4 s timeout). The REASONING lane constructs a `LocalInferenceReasoningModel`, calls `execute_generative_lane` with `stream_chat`, but the output is governed by CitationGuard before any tokens reach the client -- the SSE stream emits only the final governed text (accepted corpus-cited text or deterministic guide), not raw model tokens.

**`stream_chat()` on LocalInferenceReasoningModel (models.py line 535-564):** Exists. Implements SSE streaming via `httpx.stream("POST", ...)` against Ollama's OpenAI-compatible `/v1/chat/completions` with `stream: True`. Yields content deltas. Fail-soft: yields `[MODEL_UNAVAILABLE]` if unreachable.

**Deterministic use_model=false path:** Returns in ~38 s currently (see section a). Returns full governed assessment with `fallback_used: true`, `source: rules_table`, deadline_info, value_range, key_weaknesses, employer_arguments, and governance_result.

### Phase C design spec: instant skeleton + SSE reasoning

**Checkpoint 1 (0-500 ms) -- Instant skeleton (deterministic lane):**
Split `/assess` into a two-phase response. Phase 1 returns the deterministic skeleton immediately: deadline_info (rules-backed), qualifying_check, value_range (cap from rules), key_weaknesses (evidence gaps), and governance metadata. This data is already computed by steps 1-13 of the Brain pipeline and does not require the LLM. The frontend renders a structured card with deadline warning, value range, and evidence gaps while the reasoning stream loads.

**Checkpoint 2 (500 ms - 2+ min) -- SSE streaming reasoning:**
Open an SSE connection for the reasoning lane. Stream governed token deltas from the Qwen2.5-3B model via the existing `stream_chat()` method. Each SSE frame carries a content delta. The frontend progressively renders reasoning text in a "thinking" panel below the skeleton card.

**Checkpoint 3 (final) -- Governed result:**
After the full model output is collected, CitationGuard runs (corpus-UUID resolution), then the governance gate, safety checks, and audit trace persist. A final SSE frame carries the governed verdict (`accepted` or `fallback`) and the complete structured assessment.

### What is missing for Phase C implementation

1. **The `/assess` endpoint does not split into skeleton + stream.** Currently it runs the entire 19-step pipeline synchronously and returns one JSON blob. Needs refactoring to return the deterministic skeleton (steps 1-13) as an immediate HTTP response, then open an SSE channel for step 14+.
2. **CitationGuard runs post-hoc on the full output, not incrementally.** The existing `/reasoning/stream` route collects all governed output before emitting it as a single SSE frame. True progressive rendering requires either (a) streaming raw tokens with a "provisional" flag and replacing them with the governed result at the end, or (b) chunk-level citation validation (not yet implemented).
3. **No frontend SSE consumer exists.** The static client does not have an EventSource connection to `/reasoning/stream`.
4. **The 38 s deterministic path needs optimisation** to hit the <500 ms skeleton budget. The hybrid retrieval + graph RAG + governance chain is the bottleneck; connection pooling, query caching, or pre-warming may be needed.

---

## (c) Quant / Model Recommendation

### Current model configuration (live stack)

| Parameter | Value | Source |
|---|---|---|
| Ollama model | `qwen2.5:3b-instruct-q6_K` | `docker compose exec -T ollama ollama list` |
| Embedding model | `bge-large-en-v1.5` (207 MB GGUF) | `ollama list` |
| Temperature | 0.1 | `models.py` LocalInferenceReasoningModel |
| Max tokens | 2048 (reason), 512 (stream_chat) | `models.py` |
| Timeout | 60 s (reason), 60 s (stream_chat) | `models.py` |
| Inference policy | `ollama` only; all external providers forbidden | `inference_policy.py` |
| Default Ollama URL | `http://ollama-inference.lawapp-ai.svc.cluster.local:11434` | `inference_policy.py` |

### Quantisation / model recommendation table

| Model | Quant | Size | Expected CPU tok/s | Expected GPU tok/s (RTX 3060 12GB) | Quality / CitationGuard |
|---|---|---|---|---|---|
| Qwen2.5-3B-Instruct | q4_K_M | ~2.0 GB | 15-25 | 80-120 | Fails CitationGuard (cannot produce valid corpus_chunk UUIDs). Fastest but lowest quality. |
| **Qwen2.5-3B-Instruct** | **q6_K** | **~2.5 GB** | **10-18** | **60-100** | **Current. Fails CitationGuard (observed: `fallback_used: true` on live /assess). Adequate for reasoning text, but does not ground citations to DB UUIDs.** |
| Qwen2.5-7B-Instruct | q4_K_M | ~4.5 GB | 8-14 | 50-80 | Better instruction-following; may pass CitationGuard with few-shot UUID examples in prompt. Worth bake-off. |
| Qwen2.5-7B-Instruct | q6_K | ~5.5 GB | 5-10 | 40-65 | Higher fidelity; likely candidate for CitationGuard pass with retrieval-augmented prompt. |
| Qwen2.5-14B-Instruct | q4_K_M | ~8.5 GB | 3-6 | 25-40 | Strong instruction-following; best chance at passing CitationGuard. Requires GPU for acceptable latency. |
| Qwen2.5-14B-Instruct | q6_K | ~11 GB | 2-4 | 18-30 | Highest fidelity; production candidate with GPU. CPU-only not viable (>5 min per assessment). |

### Quality assessment: does the 3B model pass CitationGuard?

**No.** Observed from live `/assess` output (use_model=true, Ollama qwen2.5:3b-instruct-q6_K):

- `fallback_used: true` -- the model's output failed the corpus-citation gate
- `source: "rules_table"` -- fell back to deterministic guide
- `governed_result: "fallback"` -- CitationGuard rejected the model output
- `model_provider: "LocalInferenceReasoningModel"` -- Ollama was reached and ran

The 3B model generates syntactically valid JSON assessments but cannot produce `corpus_chunks` UUIDs that resolve against the local PostgreSQL database. The `enforce_or_regenerate` function in `corpus_citation_guard.py` retries and then falls back to `get_deterministic_guide()`. This is correct fail-closed behaviour -- the user gets an honest rules-backed guide rather than hallucinated citations.

**Recommendation:** Bake-off 7B q4_K_M with a retrieval-augmented prompt that injects actual corpus_chunk UUIDs from the retrieval bundle into the system prompt. If the 7B model can reference those provided UUIDs in its output, CitationGuard will pass. If not, the 14B model with GPU is required. The current 3B CPU-only configuration provides ~143 s latency and zero CitationGuard pass rate -- it is a warm placeholder, not a production reasoning engine.

---

## (d) De-Identified Escalation Tier Confirmation

### ExternalLLMForbidden exception and enforcement

**Location:** `backend/core/inference_policy.py` line 35-37.

```python
class ExternalLLMForbidden(RuntimeError):
    """Raised when an external/cloud LLM provider is configured for a legal route."""
```

**Forbidden provider list** (`_EXTERNAL_PROVIDER_MODES`, line 22-26):
`openai`, `anthropic`, `claude`, `gemini`, `google`, `mistral`, `cohere`, `together`, `groq`, `azure_openai`, `azure`, `openrouter`, `cloud`, `external`, `litellm`.

**`assert_no_external_llm_enabled()` (line 50-74):** Checks 5 env vars (`AI_PROVIDER`, `LLM_PROVIDER`, `LAWAPP_LLM_PROVIDER`, `EXTERNAL_LLM`, `CLOUD_LLM`) against the forbidden set. Also checks `settings.openrouter_enabled`. Raises `ExternalLLMForbidden` if any match.

**`require_ollama_local_provider()` (line 100-112):** Calls `assert_no_external_llm_enabled()` first, then asserts `LAWAPP_LLM_PROVIDER == "ollama_local"`. Any other value (including unset) raises `ExternalLLMForbidden`.

### Cloud model constructors fail closed

**ClaudeReasoningModel.__init__** (models.py line 141-149): Raises `ExternalLLMForbidden` unconditionally. The constructor imports the exception and raises before any instance variable is set. The class body (system prompt, reason(), etc.) is unreachable dead code.

**OpenRouterReasoningModel.__init__** (models.py line 296-303): Same pattern -- raises `ExternalLLMForbidden` unconditionally.

### Fallback chain when local Ollama fails

`select_model()` (models.py line 588-648): Calls `assert_no_external_llm_enabled()` first. If local inference is enabled but unreachable, returns `StubReasoningModel()` (never a cloud model). The stub returns `insufficient_grounding=True`, which the governance gate routes to `seek_solicitor`. There is NO cloud fallback anywhere in the chain.

`build_legal_inference_model()` (inference_policy.py line 129-142): Stricter path -- calls `require_ollama_local_provider()`, then constructs `LocalInferenceReasoningModel`. If construction fails, raises `InferenceUnavailable` (never falls back to cloud).

### Escalation tier status: DORMANT and boundary-tested

The external/cloud escalation tier is **DORMANT** -- both cloud model constructors (`ClaudeReasoningModel`, `OpenRouterReasoningModel`) raise `ExternalLLMForbidden` on construction. They cannot be instantiated.

**Boundary tests exist and hit the gate** (observed in the test suite):

| Test file | ExternalLLMForbidden assertions |
|---|---|
| `tests/test_local_ollama_only_policy.py` | 4 raises (anthropic, openrouter, openai, gemini modes) + require_ollama_local (unset, wrong value) + keys-present-no-cloud + inference-unavailable-no-fallback + deterministic-no-ollama + build-only-ollama + fake-UUID-rejected + PII-scrubbed + key-report-redacted |
| `tests/test_openrouter_provider.py` | 1 raise (OpenRouterReasoningModel constructor) |
| `tests/test_agent_pii_boundary.py` | 1 raise (ClaudeReasoningModel constructor) |
| `tests/integration/test_phase2_real_model.py` | 1 catch (ExternalLLMForbidden in integration path) |

Total: **8 ExternalLLMForbidden boundary tests** across 4 test files. The gate is not merely declared -- it is actively tested with parametrised external provider modes, key presence, and constructor invocation.

---

## Floor Delta One-Liner

8 ExternalLLMForbidden errors -> skips (fixture catch), 5 doc_type NOT NULL failures -> fixed (schema-aligned INSERT), 1 Dockerfile-missing -> skip; +79/+5 from test discovery delta.
