"""
Workflow A  -  evidence intake / AEE tests (Sovereign Trinity order Workflow A).

Proves:
  * AEE extracts at least one fact from a dismissal letter, ISO-normalised,
    with status='unconfirmed' (never auto-applied)
  * unsupported / empty content yields no facts (endpoint then fails closed)
  * the confirmation gate excludes unconfirmed facts from case data
  * the evidence_parsed outbox event runs the full pending->processed lifecycle
"""

from __future__ import annotations

import uuid

import pytest

from backend.core.document_extractor import extract_facts_from_document, _normalise_date
from backend.core.extraction import apply_confirmed_to_key_dates

_LETTER = (
    b"Dear John Smith,\n\n"
    b"We write to confirm the termination of your employment with ACME Ltd. "
    b"Your dismissal takes effect on 10 May 2026. "
    b"The reason for dismissal is gross misconduct. "
    b"You have the right to appeal within 5 days of this letter.\n\n"
    b"Yours sincerely, HR Department"
)


def test_aee_extracts_unconfirmed_normalised_facts():
    r = extract_facts_from_document(content=_LETTER, content_type="text/plain", filename="dismissal.txt")
    assert r["extraction_method"] == "plain_text"
    facts = r["facts"]
    assert isinstance(facts, list) and len(facts) >= 1, "AEE extracted no facts"
    # GUARDRAIL: every extracted fact starts unconfirmed
    for f in facts:
        assert f["status"] == "unconfirmed"
    # AEE normalises dates to ISO format (deterministic  -  proven directly)
    assert _normalise_date("10 May 2026") == "2026-05-10"


def test_unsupported_content_yields_no_facts():
    r = extract_facts_from_document(content=b"\x00\x01\x02zzz", content_type="application/octet-stream", filename="x.bin")
    assert r["facts"] == [] or len(r["facts"]) == 0   # endpoint fail-closes on zero facts


def test_confirmation_gate_excludes_unconfirmed():
    extracted = {
        "dismissal_date": {"value": "2026-05-10", "status": "extracted_unconfirmed"},
        "appeal_deadline": {"value": "2026-05-15", "status": "user_confirmed"},
    }
    _updated, applied = apply_confirmed_to_key_dates(extracted, {})
    assert "dismissal_date" not in applied, "unconfirmed fact must NOT be applied to the case"


def _db_available() -> bool:
    try:
        from ingestion.db import get_connection
        c = get_connection(); c.close(); return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="Postgres not reachable")
def test_evidence_parsed_outbox_lifecycle():
    from backend.core import outbox, outbox_worker
    from ingestion.db import get_connection
    tid = str(uuid.uuid4())
    key = f"evidence_parsed:test:{tid}"
    eid = outbox.publish(
        "evidence_parsed",
        {"case_id": "c-1", "upload_id": "u-1", "document_type": "dismissal_letter", "fact_count": 3},
        trace_id=tid, idempotency_key=key,
    )
    assert eid == key
    try:
        outbox_worker.run_once()
        c = get_connection()
        with c.cursor() as cur:
            cur.execute("SELECT status FROM outbox_events WHERE event_id=%s", (key,))
            status = cur.fetchone()[0]
        c.close()
        assert status == "processed"
    finally:
        try:
            c = get_connection()
            with c.cursor() as cur:
                cur.execute("DELETE FROM outbox_events WHERE trace_id=%s", (tid,))
            c.commit(); c.close()
        except Exception:
            pass
