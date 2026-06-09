from __future__ import annotations

from datetime import datetime, timedelta, timezone


def check_session_timeout(session: dict, timeout_hours: int = 24) -> bool:
    last = session.get("last_activity") or session.get("created_at")
    if not last:
        return False
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    if last.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(timezone.utc)
    return now - last <= timedelta(hours=timeout_hours)
