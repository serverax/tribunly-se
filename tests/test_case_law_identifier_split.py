from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from ingestion.case_law import client, ingest
from ingestion.case_law.akn_parser import ParsedCase
from ingestion.config import FCL_BASE


def _parsed_case(document_uri: str, xml_slug: str) -> ParsedCase:
    return ParsedCase(
        document_uri=document_uri,
        xml_slug=xml_slug,
        neutral_citation="[2026] EAT 77",
        fclid="fclid-77",
        case_name="Example v Example",
        court_code="eat",
        decision_date=date(2026, 1, 1),
        judges=[],
        parties=[],
        chunks=["chunk one"],
        content_hash="sha256:test",
        source_url=f"{FCL_BASE}/{xml_slug}/data.xml",
        published_date=None,
        updated_date=None,
    )


def test_fetch_document_xml_uses_slug_path(monkeypatch):
    captured: dict[str, str] = {}

    class _Resp:
        status_code = 200
        content = b"<xml/>"

    def fake_get(url: str, params=None):
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr(client, "_get", fake_get)

    data = client.fetch_document_xml("eat/2026/77")

    assert data == b"<xml/>"
    assert captured["url"] == f"{FCL_BASE}/eat/2026/77/data.xml"


def test_ingest_bulk_fetches_by_slug_and_stores_stable_identifier(monkeypatch):
    monkeypatch.setattr(ingest.settings, "fcl_bulk_licence_granted", True, raising=False)
    monkeypatch.setattr(
        ingest,
        "iter_atom_feed",
        lambda max_pages: iter([{"document_uri": "d-abc123", "xml_slug": "eat/2026/77"}]),
    )

    fetched: list[str] = []
    stored: list[ParsedCase] = []

    def fake_fetch(xml_slug: str):
        fetched.append(xml_slug)
        return b"<xml/>"

    def fake_parse(xml_bytes: bytes, document_uri: str, xml_slug: str, source_url: str):
        return _parsed_case(document_uri=document_uri, xml_slug=xml_slug)

    monkeypatch.setattr(ingest, "fetch_document_xml", fake_fetch)
    monkeypatch.setattr(ingest, "parse_judgment_xml", fake_parse)
    monkeypatch.setattr(ingest, "_store_case", lambda parsed: stored.append(parsed))

    ingest.ingest_bulk(max_pages=1)

    assert fetched == ["eat/2026/77"]
    assert len(stored) == 1
    assert stored[0].document_uri == "d-abc123"
    assert stored[0].xml_slug == "eat/2026/77"


def test_ingest_sample_resolves_stable_identifier_from_slug(monkeypatch):
    monkeypatch.setattr(ingest, "SAMPLE_EAT_DOCS", [("eat/2026/77", None)])
    monkeypatch.setattr(ingest, "fetch_document_xml", lambda xml_slug: b"<xml/>")
    monkeypatch.setattr(ingest, "lookup_document_uri_by_slug", lambda xml_slug: "d-sample-777")

    seen: dict[str, str] = {}

    def fake_parse(xml_bytes: bytes, document_uri: str, xml_slug: str, source_url: str):
        seen["document_uri"] = document_uri
        seen["xml_slug"] = xml_slug
        return _parsed_case(document_uri=document_uri, xml_slug=xml_slug)

    monkeypatch.setattr(ingest, "parse_judgment_xml", fake_parse)
    monkeypatch.setattr(ingest, "_store_case", lambda parsed: None)

    ingest.ingest_sample()

    assert seen["document_uri"] == "d-sample-777"
    assert seen["xml_slug"] == "eat/2026/77"


def test_store_case_persists_xml_slug_separately(monkeypatch):
    captured_docs: list[dict] = []
    captured_chunks: list[tuple[str, int, str]] = []

    @contextmanager
    def fake_transaction():
        yield object()

    def fake_upsert_document(cur, row: dict):
        captured_docs.append(row)
        return "doc-uuid-1"

    def fake_upsert_chunk(cur, document_id: str, chunk_index: int, body_text: str):
        captured_chunks.append((document_id, chunk_index, body_text))

    monkeypatch.setattr(ingest, "transaction", fake_transaction)
    monkeypatch.setattr(ingest, "upsert_case_law_document", fake_upsert_document)
    monkeypatch.setattr(ingest, "upsert_case_law_chunk", fake_upsert_chunk)

    ingest._store_case(_parsed_case(document_uri="d-store-1", xml_slug="eat/2026/77"))

    assert len(captured_docs) == 1
    assert captured_docs[0]["document_uri"] == "d-store-1"
    assert captured_docs[0]["fetch_url"] == f"{FCL_BASE}/eat/2026/77/data.xml"
    assert captured_chunks == [("doc-uuid-1", 0, "chunk one")]
