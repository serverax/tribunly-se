from __future__ import annotations


class _AuthDBPatchPoint:
    def get_oauth_token(self, user_id: str):
        return None


db = _AuthDBPatchPoint()


def get_user_oauth_info(user_id: str) -> dict:
    token = db.get_oauth_token(user_id) or {}
    return {
        "user_id": user_id,
        "provider": token.get("provider"),
        "connected": bool(token),
    }
