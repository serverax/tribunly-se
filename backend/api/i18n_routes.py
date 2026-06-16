"""I18n locale preference API (presentation layer only)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, Field

from backend.language_engine.shared.detector import (
    LOCALE_COOKIE,
    fetch_user_locale,
    normalize_locale,
    resolve_locale,
)
from backend.language_engine.shared.types import SUPPORTED_LOCALES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/i18n", tags=["i18n"])


class LocaleSetRequest(BaseModel):
    locale: str = Field(..., description="Supported locale code: en | ar")


class RenderRequest(BaseModel):
    assessment: dict = Field(..., description="Pipeline result or assessment_core dict")
    language: Optional[str] = None
    query: Optional[str] = None


class LocaleDetectRequest(BaseModel):
    text: Optional[str] = None
    preferred_language: Optional[str] = None


@router.get("/locales")
def list_locales() -> dict:
    return {
        "supported": [
            {"code": "en", "label": "English", "direction": "ltr", "native": True},
            {"code": "ar", "label": "العربية", "direction": "rtl", "native": True},
        ],
        "default": "en",
        "mode": "multi_native",
    }


@router.post("/detect")
def detect_locale(
    req: LocaleDetectRequest,
    request: Request,
    accept_language: Optional[str] = Header(None, alias="Accept-Language"),
) -> dict:
    locale = resolve_locale(
        request,
        body_language=req.preferred_language,
        accept_language=accept_language,
        sample_text=req.text,
    )
    return {"locale": locale, "direction": "rtl" if locale == "ar" else "ltr"}


@router.post("/render")
def render_assessment_route(
    req: RenderRequest,
    request: Request,
    accept_language: Optional[str] = Header(None, alias="Accept-Language"),
) -> dict:
    from backend.language_engine.router import render_assessment

    locale = resolve_locale(
        request,
        body_language=req.language,
        accept_language=accept_language,
        sample_text=req.query,
    )
    return render_assessment(req.assessment, locale)


@router.get("/prompts/{locale}")
def get_native_prompts(locale: str) -> dict:
    if locale == "ar":
        from backend.language_engine.ar import prompts as ar_prompts

        return {
            "locale": "ar",
            "system": ar_prompts.SYSTEM_PROMPT,
            "unfair_dismissal": ar_prompts.UNFAIR_DISMISSAL_PROMPT,
            "explanation_style": ar_prompts.EXPLANATION_STYLE,
        }
    from backend.language_engine.en import prompts as en_prompts

    return {
        "locale": "en",
        "system": en_prompts.SYSTEM_PROMPT,
        "unfair_dismissal": en_prompts.UNFAIR_DISMISSAL_PROMPT,
        "explanation_style": en_prompts.EXPLANATION_STYLE,
    }


@router.get("/locale")
def get_locale(
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
) -> dict:
    user_pref = fetch_user_locale(x_user_id)
    locale = resolve_locale(request, user_preference=user_pref)
    return {
        "locale": locale,
        "dir": "rtl" if locale == "ar" else "ltr",
        "supported": sorted(SUPPORTED_LOCALES),
        "source": _locale_source(request, user_pref),
    }


@router.post("/locale")
def set_locale(
    body: LocaleSetRequest,
    response: Response,
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
) -> dict:
    loc = normalize_locale(body.locale)
    if not loc:
        return {"status": "error", "message": f"Unsupported locale: {body.locale}"}

    response.set_cookie(
        key=LOCALE_COOKIE,
        value=loc,
        httponly=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
    )

    if x_user_id:
        _persist_user_locale(x_user_id, loc)

    return {
        "status": "ok",
        "locale": loc,
        "dir": "rtl" if loc == "ar" else "ltr",
        "persisted": bool(x_user_id),
    }


def _locale_source(request: Request, user_pref: Optional[str]) -> str:
    if request.query_params.get("locale"):
        return "query"
    if user_pref:
        return "user_profile"
    if request.cookies.get(LOCALE_COOKIE):
        return "cookie"
    if request.headers.get("accept-language"):
        return "accept_language"
    return "default"


def _persist_user_locale(user_id: str, locale: str) -> None:
    try:
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_preferences (user_id, default_locale, updated_at)
                    VALUES (%s::uuid, %s, now())
                    ON CONFLICT (user_id) DO UPDATE
                    SET default_locale = EXCLUDED.default_locale,
                        updated_at = now()
                    """,
                    (user_id, locale),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("user_preferences persist skipped: %s", exc)
