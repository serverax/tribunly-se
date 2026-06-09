"""HTTP proof for the Path-Splitter routes (ADR: Deterministic vs Generative).

  - /reasoning/route returns the correct lane,
  - /reasoning/stream FACTUAL returns deterministic JSON (no LLM),
  - /reasoning/stream REASONING is 503 when local inference is disabled,
  - /reasoning/stream REASONING returns a real text/event-stream (fail-soft frames)
    when enabled but the model is unreachable.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_route_factual_is_fast_lane():
    r = client.post("/reasoning/route", json={"query": "What is the time limit for unfair dismissal?"})
    assert r.status_code == 200
    body = r.json()
    assert body["lane"] == "FAST_DETERMINISTIC"
    assert body["invokes_llm"] is False


def test_route_reasoning_is_generative_lane():
    r = client.post("/reasoning/route", json={"query": "Do I have a claim for unfair dismissal?"})
    assert r.status_code == 200
    assert r.json()["lane"] == "STREAMING_GENERATIVE"


def test_stream_factual_returns_deterministic_json_no_llm():
    r = client.post("/reasoning/stream", json={"query": "What is the time limit for unfair dismissal?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["invokes_llm"] is False
    assert body["lane"] == "FAST_DETERMINISTIC"
    assert body["source"] == "rules_table"


def test_stream_reasoning_disabled_returns_503(monkeypatch):
    monkeypatch.delenv("LOCAL_INFERENCE_ENABLED", raising=False)
    r = client.post("/reasoning/stream", json={"query": "Do I have a claim for unfair dismissal?"})
    assert r.status_code == 503


def test_stream_reasoning_enabled_yields_event_stream_failsoft(monkeypatch):
    monkeypatch.setenv("LOCAL_INFERENCE_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")  # unreachable -> fail soft
    r = client.post("/reasoning/stream", json={"query": "Do I have a claim for unfair dismissal?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text
    assert "data:" in body
    assert "[DONE]" in body
    # CitationGuard institutionalised: an unreachable/ungrounded model must NOT leak
    # raw tokens; the governed stream returns the deterministic rules guide instead.
    assert "[MODEL_UNAVAILABLE]" not in body
    assert "rules" in body.lower() or "guide" in body.lower()
