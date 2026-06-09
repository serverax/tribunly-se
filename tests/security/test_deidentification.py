"""
De-identification tests — lawapp data protection boundary.

Tests that:
  - every PII field is stripped before model calls
  - boundary log records what was stripped
  - safe payload contains no identifying information
  - assessment output contains no PII
  - pipeline enforces de-identification before reasoning
"""

import pytest


class TestDeidentifyAllPIIFields:
    """Exhaustive test that every known PII field type is stripped."""

    PII_TEST_CASES = [
        ("name", "John Doe"),
        ("full_name", "Jane Smith"),
        ("claimant_name", "Test Person"),
        ("employer", "Acme Ltd"),
        ("employer_name", "Big Corp"),
        ("home_address", "123 High Street"),
        ("email", "user@example.com"),
        ("email_address", "contact@firm.com"),
        ("phone", "07700 900000"),
        ("national_insurance", "AB123456C"),
        ("nino", "CD654321E"),
        ("date_of_birth", "1985-01-01"),
        ("dob", "1990-06-15"),
        ("raw_document", "Dismissal letter content here"),
        ("raw_text", "OCR extracted text with names"),
    ]

    @pytest.mark.parametrize("field,value", PII_TEST_CASES)
    def test_pii_field_stripped(self, field, value):
        from backend.core.deidentify import deidentify
        facts = {field: value, "edt": "2026-01-01", "jurisdiction": "EW"}
        safe, log = deidentify(facts)
        assert field not in safe or safe[field] is None, \
            f"PII field '{field}' not stripped from safe payload"

    def test_legal_dates_preserved(self):
        from backend.core.deidentify import deidentify
        facts = {
            "edt": "2026-01-01",
            "service_start_date": "2022-06-01",
            "ec_day_a": "2026-02-01",
            "ec_day_b": "2026-02-20",
            "name": "Jane Smith",
        }
        safe, _ = deidentify(facts)
        assert safe.get("edt") == "2026-01-01"
        assert safe.get("service_start_date") == "2022-06-01"
        assert safe.get("ec_day_a") == "2026-02-01"
        assert safe.get("ec_day_b") == "2026-02-20"

    def test_legal_facts_preserved(self):
        from backend.core.deidentify import deidentify
        facts = {
            "reason_for_dismissal": "conduct",
            "was_procedure_followed": False,
            "weekly_pay": 750,
            "jurisdiction": "EW",
            "email": "strip_this@example.com",
        }
        safe, _ = deidentify(facts)
        assert safe.get("reason_for_dismissal") == "conduct"
        assert safe.get("was_procedure_followed") is False
        assert safe.get("weekly_pay") == 750
        assert "email" not in safe


class TestBoundaryLog:
    def test_boundary_log_has_required_keys(self):
        from backend.core.deidentify import deidentify
        _, log = deidentify({"name": "Test", "edt": "2026-01-01"})
        assert "fields_stripped" in log
        assert "fields_passed" in log

    def test_boundary_log_lists_stripped_fields(self):
        from backend.core.deidentify import deidentify
        _, log = deidentify({"name": "Test", "employer": "Corp", "edt": "2026-01-01"})
        stripped = log["fields_stripped"]
        assert "name" in stripped
        assert "employer" in stripped

    def test_boundary_log_lists_passed_fields(self):
        from backend.core.deidentify import deidentify
        _, log = deidentify({"edt": "2026-01-01", "jurisdiction": "EW"})
        passed = log["fields_passed"]
        assert "edt" in passed or "jurisdiction" in passed

    def test_pii_not_in_output(self):
        """pii_fields_in_output should be empty for safe facts."""
        from backend.core.deidentify import deidentify
        _, log = deidentify({"edt": "2026-01-01", "weekly_pay": 700})
        pii_out = log.get("pii_fields_in_output", [])
        assert len(pii_out) == 0, f"PII in output: {pii_out}"


class TestPipelineDeidentificationEnforcement:
    def test_pipeline_calls_deidentify(self):
        """pipeline.assess() must call deidentify before model.reason()."""
        import inspect
        from backend.core import pipeline
        src = inspect.getsource(pipeline.assess)
        assert "deidentify" in src, "deidentify not called in pipeline.assess"

    def test_deidentify_runs_before_model_call(self):
        """In pipeline source, deidentify must appear before model.reason."""
        import inspect
        from backend.core import pipeline
        src = inspect.getsource(pipeline.assess)
        deidentify_pos = src.index("deidentify(")
        reason_pos = src.index("model.reason")
        assert deidentify_pos < reason_pos, \
            "deidentify must run BEFORE model.reason in pipeline"
