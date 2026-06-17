"""RAG 1024-dim retrieval repair tests (corpus_chunks canonical plane)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.core import retrieve as R
from ingestion.config import settings


def test_query_embedding_dimension_1024():
    """Query vectors must match configured bge-large-en-v1.5 dimension."""
    fake_vec = [0.01] * settings.embedding_dim
    with patch("ingestion.embeddings.embedder.embed_texts", return_value=[fake_vec]):
        vec = R.generate_query_embedding("unfair dismissal time limit")
    assert len(vec) == 1024
    assert len(vec) == settings.embedding_dim


def test_generate_query_embedding_rejects_dimension_mismatch():
    with patch("ingestion.embeddings.embedder.embed_texts", return_value=[[0.0] * 384]):
        with pytest.raises(RuntimeError, match="1024"):
            R.generate_query_embedding("test query")


def test_retrieve_semantic_gate_uses_corpus_chunks_not_legislation(monkeypatch):
    """Semantic path must probe corpus_chunks, not legislation.embedding."""
    executed: list[str] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            executed.append(sql.strip())

        def fetchone(self):
            sql = executed[-1] if executed else ""
            if "corpus_chunks WHERE embedding IS NOT NULL" in sql and "EXISTS" in sql:
                return [False]
            if "legislation WHERE embedding" in sql:
                pytest.fail("retrieve_semantic must not gate on legislation.embedding")
            return [False]

        def fetchall(self):
            return []

    fake_conn = MagicMock()
    fake_conn.cursor.return_value = FakeCursor()
    monkeypatch.setattr(R, "get_connection", lambda: fake_conn)
    monkeypatch.setattr(R, "retrieve_keyword", lambda *a, **k: [{"source_type": "legislation", "url": "http://x", "text": "t"}])

    results = R.retrieve_semantic("unfair dismissal", jurisdiction="EW", edt=date(2026, 1, 1))
    assert results
    assert any("corpus_chunks" in sql for sql in executed)
    assert not any("legislation WHERE embedding" in sql for sql in executed)


def test_retrieve_semantic_sql_targets_corpus_chunks(monkeypatch):
    """When embeddings exist, semantic search queries corpus_chunks."""
    calls: list[str] = []

    class SeqCursor:
        def __init__(self):
            self._step = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            calls.append(sql)

        def fetchone(self):
            if self._step == 0:
                self._step += 1
                return [True]
            if "vector_dims" in (calls[-1] if calls else ""):
                return [1024]
            return None

        def fetchall(self):
            return [
                {
                    "source_type": "primary_legislation",
                    "source_table": "legislation",
                    "cite": "ERA 1996 s.111",
                    "heading": "Time limit",
                    "text": "Proceedings ...",
                    "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/111",
                    "jurisdiction": "GB",
                    "effective_from": date(1996, 1, 1),
                    "effective_to": None,
                    "distance": 0.2,
                }
            ]

    fake_conn = MagicMock()
    fake_conn.cursor.side_effect = lambda *a, **k: SeqCursor()
    monkeypatch.setattr(R, "get_connection", lambda: fake_conn)
    monkeypatch.setattr(R, "_corpus_embeddings_present", lambda: True)
    monkeypatch.setattr(R, "_corpus_embedding_dim", lambda: 1024)
    monkeypatch.setattr(
        "ingestion.embeddings.embedder.embed_texts",
        lambda texts: [[0.01] * 1024 for _ in texts],
    )

    results = R.retrieve_semantic("unfair dismissal time limit", jurisdiction="EW", k=3)
    assert results
    assert results[0]["source_type"] == "legislation"
    assert results[0]["url"].startswith("https://")
    assert any("FROM corpus_chunks" in sql for sql in calls)



def test_rag_search_api_returns_results_for_canonical_queries():
    """Live /api/rag/search must return cited hits for employment-law queries."""
    import urllib.error
    import urllib.request

    queries = [
        "unfair dismissal time limit",
        "compensatory award cap",
        "qualifying period",
        "ACAS early conciliation",
    ]
    for q in queries:
        payload = f'{{"query": "{q}", "limit": 5}}'.encode()
        req = urllib.request.Request(
            "http://localhost:8017/api/rag/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode()
        except urllib.error.URLError as exc:
            pytest.skip(f"RAG service not reachable: {exc}")
        import json

        data = json.loads(body)
        assert data["total_found"] > 0, f"No results for query: {q}"
        for hit in data["results"]:
            assert hit.get("authority_ref") or hit.get("source_url"), (
                f"Missing citation metadata for {q}: {hit}"
            )
            assert hit.get("source_url"), f"Missing source_url for {q}: {hit}"
