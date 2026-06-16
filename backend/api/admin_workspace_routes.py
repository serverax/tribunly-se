"""Admin control center routes (JWT admin role, fail closed)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.core import admin_workspace_data as admin_data
from backend.core.user_auth import check_admin_role, get_current_user

router = APIRouter(tags=["admin-workspace"])


def _require_admin_jwt(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    user_id = get_current_user(x_user_id, authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not check_admin_role(user_id):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user_id


@router.get("/admin/cases")
def admin_cases(_admin: str = Depends(_require_admin_jwt)) -> dict:
    return admin_data.list_admin_cases()


@router.get("/admin/ai-logs")
def admin_ai_logs(_admin: str = Depends(_require_admin_jwt)) -> dict:
    return admin_data.list_admin_ai_logs()


@router.get("/admin/users")
def admin_users(_admin: str = Depends(_require_admin_jwt)) -> dict:
    return admin_data.list_admin_users()


@router.get("/admin/system-health")
def admin_system_health(_admin: str = Depends(_require_admin_jwt)) -> dict:
    return admin_data.get_admin_system_health()


@router.get("/admin/compliance")
def admin_compliance(_admin: str = Depends(_require_admin_jwt)) -> dict:
    return admin_data.get_admin_compliance()
