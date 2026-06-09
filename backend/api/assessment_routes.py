from __future__ import annotations

from backend.core import access


def get_assessment(case_id: str, user_id: str) -> dict:
    if not access.check_case_ownership(case_id, user_id):
        raise PermissionError("assessment access denied")
    return {"case_id": case_id, "assessment": {}}
