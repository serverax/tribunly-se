"""
Tests for the de-identification boundary.

These prove that PII fields are stripped before model calls.
The boundary_log is what we show as the proof for the Phase 2
acceptance criterion: "no personal data in third-party payloads."
"""

from backend.core.deidentify import deidentify, _PII_FIELDS, _SAFE_FIELDS


def test_pii_fields_stripped():
    facts = {
        "claimant_name": "Jane Smith",
        "employer_name": "Acme Ltd",
        "email": "jane@example.com",
        "edt": "2026-05-01",
        "reason_for_dismissal": "conduct",
    }
    safe, log = deidentify(facts)

    # PII must not appear in output
    assert "claimant_name" not in safe
    assert "employer_name" not in safe
    assert "email" not in safe

    # Legal facts must survive
    assert safe["edt"] == "2026-05-01"
    assert safe["reason_for_dismissal"] == "conduct"

    # Log must record what was stripped
    assert "claimant_name" in log["fields_stripped"]
    assert "employer_name" in log["fields_stripped"]
    assert "email" in log["fields_stripped"]


def test_no_pii_in_output_keys():
    facts = {
        "name": "John Doe",
        "date_of_birth": "1985-03-15",
        "national_insurance": "AB123456C",
        "edt": "2026-04-01",
        "weekly_pay": 500,
        "service_start_date": "2023-01-01",
    }
    safe, log = deidentify(facts)

    # Verify none of the known PII field names appear in output keys
    for key in safe:
        assert key.lower().replace("-", "_") not in _PII_FIELDS, \
            f"PII field '{key}' found in de-identified output"

    # Verify the log is non-empty for the PII fields
    assert len(log["fields_stripped"]) >= 3


def test_boundary_log_has_required_fields():
    _, log = deidentify({"edt": "2026-05-01"})
    assert "fields_stripped" in log
    assert "fields_passed" in log
    assert "pii_fields_in_output" in log
    assert log["pii_fields_in_output"] == []  # must always be empty


def test_safe_facts_only_when_no_pii():
    facts = {
        "edt": "2026-05-01",
        "service_start_date": "2023-06-01",
        "weekly_pay": 600,
        "reason_for_dismissal": "redundancy",
        "was_procedure_followed": False,
        "jurisdiction": "EW",
    }
    safe, log = deidentify(facts)
    assert len(log["fields_stripped"]) == 0
    assert safe == facts  # everything passes through unchanged


def test_all_pii_fields_documented():
    """
    Regression test: if a new PII field is added to _PII_FIELDS,
    this test ensures we have at least one test case that strips it.
    """
    sample_pii = {field: f"test_{field}" for field in _PII_FIELDS}
    sample_pii["edt"] = "2026-05-01"  # add one safe field

    safe, log = deidentify(sample_pii)
    assert "edt" in safe
    # All PII fields should be stripped
    for field in _PII_FIELDS:
        if field in sample_pii:
            assert field not in safe, f"PII field '{field}' was not stripped"
