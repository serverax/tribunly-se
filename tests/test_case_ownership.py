"""
Unit tests for case ownership enforcement.

Tests check_case_ownership and _require_case_owner in isolation (no live DB).
DB-connected integration tests live in tests/integration/test_phase6a_deployment.py.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

_DB_PATCH = "ingestion.db.get_connection"


def _make_conn(owner_id):
    """Mock psycopg2 connection whose cursor returns (owner_id,) as a row."""
    cursor = MagicMock()
    cursor.fetchone.return_value = (owner_id,) if owner_id else None
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ── check_case_ownership ──────────────────────────────────────────────────────

class TestCheckCaseOwnership:
    from backend.core.user_auth import check_case_ownership as _fn

    def test_none_user_bypasses_db(self):
        """user_id=None (auth mode 'none') must skip DB entirely."""
        from backend.core.user_auth import check_case_ownership
        with patch(_DB_PATCH) as mock_conn:
            check_case_ownership("case-1", None)
            mock_conn.assert_not_called()

    def test_admin_override_bypasses_db(self):
        """admin_override=True must skip DB entirely."""
        from backend.core.user_auth import check_case_ownership
        with patch(_DB_PATCH) as mock_conn:
            check_case_ownership("case-1", "user-uuid", admin_override=True)
            mock_conn.assert_not_called()

    def test_matching_owner_passes(self):
        """Caller is the case owner → no exception."""
        from backend.core.user_auth import check_case_ownership
        uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        with patch(_DB_PATCH, return_value=_make_conn(uid)):
            check_case_ownership("case-1", uid)   # must not raise

    def test_different_owner_raises_403(self):
        """Caller is NOT the case owner → HTTP 403."""
        from backend.core.user_auth import check_case_ownership
        caller = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        owner  = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        with patch(_DB_PATCH, return_value=_make_conn(owner)):
            with pytest.raises(HTTPException) as exc:
                check_case_ownership("case-1", caller)
        assert exc.value.status_code == 403
        assert "Access denied" in exc.value.detail

    def test_case_not_found_raises_404(self):
        """Row not in DB → HTTP 404."""
        from backend.core.user_auth import check_case_ownership
        conn = _make_conn(None)
        conn.cursor.return_value.fetchone.return_value = None
        with patch(_DB_PATCH, return_value=conn):
            with pytest.raises(HTTPException) as exc:
                check_case_ownership("case-1", "some-user")
        assert exc.value.status_code == 404

    def test_null_db_owner_passes_any_user(self):
        """Case with NULL user_id (legacy / unowned) allows any caller."""
        from backend.core.user_auth import check_case_ownership
        uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        # owner_id=None means case.user_id IS NULL in the DB row
        conn = _make_conn(None)
        conn.cursor.return_value.fetchone.return_value = (None,)
        with patch(_DB_PATCH, return_value=conn):
            check_case_ownership("case-1", uid)   # must not raise


# ── _require_case_owner FastAPI dependency ────────────────────────────────────

class TestRequireCaseOwnerDependency:

    def test_matching_owner_returns_uid(self):
        from backend.api.main import _require_case_owner
        uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        with patch(_DB_PATCH, return_value=_make_conn(uid)):
            with patch.dict("os.environ", {"LAWAPP_AUTH_MODE": "mock"}):
                result = _require_case_owner(
                    case_id="any-case",
                    x_user_id=uid,
                    x_admin_key=None,
                    authorization=None,
                )
        assert result == uid

    def test_mismatched_owner_raises_403(self):
        from backend.api.main import _require_case_owner
        caller = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        owner  = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        with patch(_DB_PATCH, return_value=_make_conn(owner)):
            with patch.dict("os.environ", {"LAWAPP_AUTH_MODE": "mock"}):
                with pytest.raises(HTTPException) as exc:
                    _require_case_owner(
                        case_id="any-case",
                        x_user_id=caller,
                        x_admin_key=None,
                        authorization=None,
                    )
        assert exc.value.status_code == 403

    def test_auth_none_mode_returns_none(self):
        from backend.api.main import _require_case_owner
        with patch.dict("os.environ", {"LAWAPP_AUTH_MODE": "none"}):
            result = _require_case_owner(
                case_id="any-case",
                x_user_id=None,
                x_admin_key=None,
                authorization=None,
            )
        assert result is None

    def test_admin_key_bypasses_ownership_check(self):
        from backend.api.main import _require_case_owner
        admin_key = "test-admin-key-xyz"
        valid_uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        with patch.dict("os.environ", {"LAWAPP_AUTH_MODE": "mock", "ADMIN_API_KEY": admin_key}):
            with patch(_DB_PATCH) as mock_conn:
                _require_case_owner(
                    case_id="any-case",
                    x_user_id=valid_uid,
                    x_admin_key=admin_key,
                    authorization=None,
                )
                mock_conn.assert_not_called()
