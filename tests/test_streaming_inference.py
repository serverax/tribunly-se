"""SSE streaming proof for the generative (REASONING) lane.

  - sse_frames formats text/event-stream correctly,
  - stream_chat fails soft ([MODEL_UNAVAILABLE]) when the endpoint is unreachable,
  - stream_chat yields REAL tokens from the local qwen2.5:3b (skipped if Ollama is
    not reachable from the test container).
"""
from __future__ import annotations

import os
import pytest

from backend.core.models import LocalInferenceReasoningModel
from backend.core.path_splitter import sse_frames

OLLAMA = os.environ.get("LAWAPP_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def _ollama_up() -> bool:
    import httpx
    try:
        r = httpx.get(f"{OLLAMA}/api/tags", timeout=3.0)
        r.raise_for_status()
        names = {m.get("name", "").split(":")[0] for m in r.json().get("models", [])}
        if "qwen2.5" not in names and not any("qwen" in n for n in names):
            return False
        probe = httpx.post(
            f"{OLLAMA}/v1/chat/completions",
            json={"model": "qwen2.5:3b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=10.0,
        )
        return probe.status_code == 200
    except Exception:
        return False


def test_sse_frames_format():
    out = list(sse_frames(iter(["Hello", " world"])))
    assert out[0] == "data: Hello\n\n"
    assert out[1] == "data:  world\n\n"
    assert out[-1] == "data: [DONE]\n\n"


def test_stream_chat_fail_soft_when_unreachable():
    m = LocalInferenceReasoningModel(base_url="http://127.0.0.1:1")
    chunks = list(m.stream_chat([{"role": "user", "content": "hi"}], max_tokens=8))
    assert chunks == ["[MODEL_UNAVAILABLE]"]


@pytest.mark.skipif(not _ollama_up(), reason="UNPROVEN  -  local Ollama not reachable from test container")
def test_stream_chat_real_tokens_from_qwen():
    m = LocalInferenceReasoningModel(base_url=OLLAMA, model_id="qwen2.5:3b")
    chunks = list(m.stream_chat([{"role": "user", "content": "Reply with the single word: yes"}], max_tokens=8))
    assert len(chunks) >= 1
    assert "[MODEL_UNAVAILABLE]" not in chunks
    assert len("".join(chunks).strip()) > 0
