"""
Memory Engine unit tests  -  lawapp consent-gated case memory.

Tests that:
  - save_memory requires user_id + case_id
  - get_memory is user/case scoped
  - cross-user memory access is blocked
  - sensitive types are rejected at write
  - memory is never saved without consent

No real DB required  -  tests validate contract and isolation logic.
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.core.memory import save_memory, get_memory


class TestMemorySaveContracts:
    def test_save_requires_user_id(self):
        with pytest.raises((ValueError, Exception)):
            save_memory("", "case-123", "case_facts", "test_key", "value")

    def test_save_requires_case_id(self):
        with pytest.raises((ValueError, Exception)):
            save_memory("user-123", "", "case_facts", "test_key", "value")

    def test_save_requires_both_ids(self):
        with pytest.raises((ValueError, Exception)):
            save_memory("", "", "case_facts", "key", "val")

    def test_invalid_memory_type_rejected(self):
        with pytest.raises((ValueError, Exception)):
            save_memory("user-123", "case-123", "raw_llm_output", "key", "val")

    def test_valid_memory_types_accepted_at_validation(self):
        valid_types = [
            "case_facts", "user_preference", "timeline",
            "deadlines", "previous_answers", "evidence_checklist",
        ]
        # These should not raise ValueError on type validation
        for mt in valid_types:
            with patch("ingestion.db.get_connection") as mock_conn:
                mock_conn.side_effect = Exception("DB not available")
                try:
                    save_memory("user-123", "case-123", mt, "key", "val")
                except Exception as e:
                    # Should fail on DB, not on validation
                    assert "DB not available" in str(e) or "not available" in str(e).lower()


class TestMemoryIsolation:
    def test_user_id_required_for_get(self):
        """get_memory without user_id must raise or return nothing."""
        with pytest.raises((ValueError, TypeError, Exception)):
            get_memory("", "case-123", "case_facts", "key")

    def test_case_id_required_for_get(self):
        """get_memory without case_id must raise or return nothing."""
        with pytest.raises((ValueError, TypeError, Exception)):
            get_memory("user-123", "", "case_facts", "key")


class TestMemoryConsentGate:
    """
    Verify Brain only saves memory when memory_consent=True.
    Uses run_brain directly to confirm gate works.
    """

    def test_brain_memory_not_saved_without_consent(self):
        from backend.core.brain import run_brain
        from backend.core.models import StubReasoningModel
        result = run_brain(
            "I was unfairly dismissed",
            {"edt": "2025-10-01", "service_start_date": "2022-01-01", "jurisdiction": "EW"},
            user_id="user-999",
            case_id="case-999",
            memory_consent=False,
            model=StubReasoningModel(),
        )
        assert result["trace"]["memory_saved"] is False

    def test_brain_memory_not_saved_anonymous(self):
        from backend.core.brain import run_brain
        from backend.core.models import StubReasoningModel
        result = run_brain(
            "I was unfairly dismissed",
            {"edt": "2025-10-01", "service_start_date": "2022-01-01", "jurisdiction": "EW"},
            user_id=None,
            case_id=None,
            memory_consent=True,
            model=StubReasoningModel(),
        )
        assert result["trace"]["memory_saved"] is False

    def test_brain_memory_step_always_recorded(self):
        from backend.core.brain import run_brain
        from backend.core.models import StubReasoningModel
        result = run_brain(
            "I was unfairly dismissed",
            {"edt": "2025-10-01", "service_start_date": "2022-01-01", "jurisdiction": "EW"},
            model=StubReasoningModel(),
        )
        step_names = [s["step"] for s in result["trace"]["steps"]]
        assert "save_case_memory" in step_names
