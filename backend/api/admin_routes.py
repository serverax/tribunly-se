"""Admin route helpers.

These functions intentionally fail closed unless the caller has an admin role.
They are lightweight helpers for existing tests; the deployed admin service
continues to provide the real dashboard API.
"""

from __future__ import annotations

def _require_admin(user_id: str) -> None:
    from backend.core import user_auth
    if not user_auth.check_admin_role(user_id):
        raise PermissionError("Admin role required")


def list_all_users(user_id: str):
    _require_admin(user_id)
    return []


def get_dashboard(user_id: str):
    _require_admin(user_id)
    return {}


def override_payment_status(case_id: str, status: str, user_id: str):
    _require_admin(user_id)
    return {"case_id": case_id, "status": status}


def export_audit_logs(user_id: str):
    _require_admin(user_id)
    return []
