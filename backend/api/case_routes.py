from __future__ import annotations

from backend.core import access


def update_case(case_id: str, changes: dict, user_id: str) -> dict:
    if not access.check_case_ownership(case_id, user_id):
        raise PermissionError("case access denied")
    return {"case_id": case_id, "updated": changes}


def list_user_cases(user_id: str) -> list[dict]:
    return list(access.db.list_cases_by_user(user_id) or [])
