"""Locale detection: Accept-Language, cookie, query param, user preference, Arabic script."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import Request

from backend.language_engine.shared.types import SUPPORTED_LOCALES

LOCALE_COOKIE = "lawapp_locale"
_QUERY_RE = re.compile(r"^[a-z]{2}$")
_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")


def normalize_locale(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    loc = value.strip().lower().split(",")[0].split("-")[0].split("_")[0]
    if not _QUERY_RE.match(loc):
        return None
    return loc if loc in SUPPORTED_LOCALES else None


def detect_arabic_script(text: Optional[str]) -> bool:
    return bool(text and _ARABIC_SCRIPT_RE.search(text))


def resolve_locale(
    request: Optional[Request] = None,
    *,
    query_locale: Optional[str] = None,
    cookie_locale: Optional[str] = None,
    user_preference: Optional[str] = None,
    accept_language: Optional[str] = None,
    body_language: Optional[str] = None,
    sample_text: Optional[str] = None,
) -> str:
    """
    Priority: body language > explicit query > user profile > cookie >
    Accept-Language > Arabic script in sample_text > en.
    """
    for candidate in (
        normalize_locale(body_language),
        normalize_locale(query_locale),
        normalize_locale(user_preference),
        normalize_locale(cookie_locale),
        _from_accept_language(accept_language),
    ):
        if candidate:
            return candidate

    if request is not None:
        q = request.query_params.get("locale")
        found = normalize_locale(q)
        if found:
            return found
        cookie = request.cookies.get(LOCALE_COOKIE)
        found = normalize_locale(cookie)
        if found:
            return found
        al = request.headers.get("accept-language")
        found = _from_accept_language(al)
        if found:
            return found

    if detect_arabic_script(sample_text):
        return "ar"

    return "en"


def _from_accept_language(header: Optional[str]) -> Optional[str]:
    if not header:
        return None
    for part in header.split(","):
        token = part.strip().split(";")[0].lower()
        loc = normalize_locale(token)
        if loc:
            return loc
    return None


def fetch_user_locale(user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    try:
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT default_locale FROM user_preferences WHERE user_id = %s::uuid",
                    (user_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return normalize_locale(str(row[0]))
        finally:
            conn.close()
    except Exception:
        return None
    return None
