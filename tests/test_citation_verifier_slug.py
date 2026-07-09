from __future__ import annotations

import re

from backend.core.citation_verifier import verify_citation


class _FakeCursor:
    def __init__(self, source_urls: list[str]) -> None:
        self._source_urls = source_urls
        self._result = None

    def execute(self, sql: str, params: tuple[str, str] | tuple[str, ...] | None = None) -> None:
        params = params or ()
        if "source_url LIKE" in sql:
            self._result = (1,) if self._any_like_match(params) else None
        else:
            self._result = None

    def _any_like_match(self, params: tuple[str, ...]) -> bool:
        patterns = [str(p) for p in params if p is not None]
        return any(
            any(_sql_like(source_url, pattern) for pattern in patterns)
            for source_url in self._source_urls
        )

    def fetchone(self):
        return self._result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, source_urls: list[str]) -> None:
        self._source_urls = source_urls

    def cursor(self):
        return _FakeCursor(self._source_urls)

    def close(self) -> None:
        pass


def _sql_like(value: str, pattern: str) -> bool:
    regex = "^" + re.escape(pattern).replace(r"\%", ".*").replace(r"\_", ".") + "$"
    return re.fullmatch(regex, value) is not None


def _install_fake_db(monkeypatch, source_urls: list[str]) -> None:
    fake_db = _FakeConnection(source_urls)
    monkeypatch.setattr(
        "ingestion.db.get_connection",
        lambda: fake_db,
        raising=True,
    )


def test_slug_exact_match_verifies(monkeypatch):
    _install_fake_db(monkeypatch, ["https://data.riksdagen.se/dokument/ukpga/1996/18/contents"])
    result = verify_citation("ukpga/1996/18")
    assert result["verified"] is True
    assert result["method"] == "source_url_slug"


def test_slug_prefix_does_not_false_verify(monkeypatch):
    _install_fake_db(monkeypatch, ["https://data.riksdagen.se/dokument/ukpga/2010/15/contents"])
    result = verify_citation("ukpga/2010/1")
    assert result["verified"] is False


def test_slug_full_chapter_verifies(monkeypatch):
    _install_fake_db(monkeypatch, ["https://data.riksdagen.se/dokument/ukpga/2010/15/contents"])
    result = verify_citation("ukpga/2010/15")
    assert result["verified"] is True
    assert result["method"] == "source_url_slug"
