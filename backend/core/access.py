"""Access control module  -  User/tenant isolation and permission enforcement.

Stub implementation for testability. Provides:
- User isolation checks (owns case / has workspace access)
- Role-based access control
- Payment entitlement checks
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class _AccessDBPatchPoint:
    def get_case_owner(self, case_id):
        return None

    def list_cases_by_user(self, user_id):
        return []


db = _AccessDBPatchPoint()


def user_owns_case(user_id: str | UUID, case_id: str | UUID) -> bool:
    """
    Check if a user owns (created) a case.

    Args:
        user_id: User UUID
        case_id: Case UUID

    Returns:
        True if the user is the case's owner
    """
    if not user_id or not case_id:
        logger.warning("user_owns_case: missing user_id or case_id")
        return False
    try:
        owner = db.get_case_owner(str(case_id))
        if owner is not None:
            return str(owner) == str(user_id)
    except Exception:
        logger.debug("access db patch point unavailable", exc_info=True)

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM cases WHERE id = %s::uuid AND user_id = %s::uuid "
                    "AND deleted_at IS NULL",
                    (str(case_id), str(user_id)),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("user_owns_case check failed: %s (fail-closed)", exc)
        return False


def check_case_ownership(case_id: str | UUID, user_id: str | UUID) -> bool:
    """Compatibility wrapper used by security tests and route helpers."""
    return user_owns_case(user_id, case_id)


def user_has_workspace_access(user_id: str | UUID, workspace_id: str | UUID) -> bool:
    """
    Check if a user has access to a workspace.

    Args:
        user_id: User UUID
        workspace_id: Workspace UUID

    Returns:
        True if user is a member of the workspace
    """
    if not user_id or not workspace_id:
        logger.warning("user_has_workspace_access: missing user_id or workspace_id")
        return False

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # Check direct membership
                cur.execute(
                    "SELECT 1 FROM workspace_members WHERE workspace_id = %s::uuid "
                    "AND user_id = %s::uuid",
                    (str(workspace_id), str(user_id)),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("user_has_workspace_access check failed: %s (fail-closed)", exc)
        return False


def user_can_generate_documents(user_id: str | UUID, case_id: str | UUID) -> bool:
    """
    Check if a user can generate documents for a case.

    Requires:
    1. User owns the case
    2. Case has payment_status='paid' (if payment is enabled)

    Args:
        user_id: User UUID
        case_id: Case UUID

    Returns:
        True if generation is allowed
    """
    if not user_owns_case(user_id, case_id):
        logger.info("user_can_generate_documents: user does not own case")
        return False

    # Check payment status if payment is enabled
    from backend.core.payment import is_case_paid, get_payment_mode
    if get_payment_mode() != "disabled":
        if not is_case_paid(case_id):
            logger.info("user_can_generate_documents: case is not paid")
            return False

    logger.debug("user_can_generate_documents: allowed for user %s, case %s", user_id, case_id)
    return True


def user_can_view_assessment(user_id: str | UUID, case_id: str | UUID) -> bool:
    """
    Check if a user can view a case's assessment.

    Requires: user owns the case

    Args:
        user_id: User UUID
        case_id: Case UUID

    Returns:
        True if view is allowed
    """
    return user_owns_case(user_id, case_id)


def user_has_admin_role(user_id: str | UUID) -> bool:
    """
    Check if a user has admin role.

    Args:
        user_id: User UUID

    Returns:
        True if user is an admin
    """
    if not user_id:
        return False

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM users WHERE id = %s::uuid AND is_admin = true",
                    (str(user_id),),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("user_has_admin_role check failed: %s (fail-closed)", exc)
        return False


class AccessDenied(Exception):
    """Raised when access control check fails."""
    pass


def enforce_case_ownership(user_id: str | UUID, case_id: str | UUID) -> None:
    """
    Enforce that user owns case; raise AccessDenied if not.

    Args:
        user_id: User UUID
        case_id: Case UUID

    Raises:
        AccessDenied: If user does not own case
    """
    if not user_owns_case(user_id, case_id):
        logger.warning("enforce_case_ownership: denied for user %s, case %s", user_id, case_id)
        raise AccessDenied(f"User {user_id} does not own case {case_id}")


def enforce_document_generation(user_id: str | UUID, case_id: str | UUID) -> None:
    """
    Enforce that user can generate documents; raise AccessDenied if not.

    Args:
        user_id: User UUID
        case_id: Case UUID

    Raises:
        AccessDenied: If generation is not allowed
    """
    if not user_can_generate_documents(user_id, case_id):
        logger.warning("enforce_document_generation: denied for user %s, case %s", user_id, case_id)
        raise AccessDenied(f"User {user_id} cannot generate documents for case {case_id}")
