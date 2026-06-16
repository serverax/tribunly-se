# Local Ollama for lawapp development

lawapp legal routes use **local Ollama only** (no external LLM bypass). Production targets the K8s service `ollama-inference.lawapp-ai.svc.cluster.local:11434`. For Docker Compose on a developer machine, use one of the options below.

## Option A  -  Ollama on the host (recommended on Windows/macOS)

1. Install [Ollama](https://ollama.com/) and pull the default model:
   ```bash
   ollama pull qwen2.5:3b
   ```
2. Compose defaults `LAWAPP_OLLAMA_BASE_URL` to `http://host.docker.internal:11434` so containers reach the host daemon.
3. Restart backend after changing env:
   ```bash
   docker compose up -d backend
   ```

## Option B  -  Compose Ollama profile

```bash
docker compose --profile ollama up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
```

Set on backend (`.env` or shell):

```
LAWAPP_OLLAMA_BASE_URL=http://ollama:11434
```

## Verification

| Check | Command | Expected |
|-------|---------|----------|
| Streaming test | `python -m pytest tests/test_streaming_inference.py::test_stream_chat_real_tokens_from_qwen -q` | PASS (not skipped) |
| Live legal accuracy | `python scripts/run_legal_accuracy.py --live` | PASS or `reports/legal_accuracy_live.txt` with `OLLAMA_NOT_REACHABLE` |
| Stub legal accuracy (CI) | `python scripts/run_legal_accuracy.py` | PASS  -  **does not** prove live model |

## Stub vs live gap (honesty)

- **`scripts/run_legal_accuracy.py`** (default) uses `StubReasoningModel`  -  deterministic rules/RAG path, fast CI.
- **`--live`** uses `LocalInferenceReasoningModel`  -  proves generative lane only when Ollama is up.
- Track A waiver on `test_stream_chat_real_tokens_from_qwen` closes when Ollama is reachable from the test environment.

Cluster DNS (`ollama-inference.lawapp-ai.svc.cluster.local`) is intentional for K8s deploys; override for local dev as above.
