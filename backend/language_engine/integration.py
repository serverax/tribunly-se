"""Wire language layer into HTTP responses without touching RAG/rules retrieval."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request

from backend.language_engine.router import render_assessment
from backend.language_engine.shared.detector import fetch_user_locale, resolve_locale


def enrich_assessment_response(
    result: dict[str, Any],
    request: Optional[Request] = None,
    *,
    locale: Optional[str] = None,
    user_id: Optional[str] = None,
    use_llm_phrasing: bool = False,
    model=None,
) -> dict[str, Any]:
    """Apply presentation layer after governed assessment is produced."""
    if not isinstance(result, dict):
        return result

    user_pref = fetch_user_locale(user_id)
    loc = locale or resolve_locale(request, user_preference=user_pref)
    if request is not None and not locale:
        q = request.query_params.get("locale")
        if q:
            loc = resolve_locale(request, query_locale=q, user_preference=user_pref)

    return render_assessment(
        result,
        loc,
        use_llm_phrasing=use_llm_phrasing,
        model=model,
    )
