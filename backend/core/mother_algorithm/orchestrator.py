"""Mother algorithm orchestrator with post-reasoning language rendering."""

from __future__ import annotations

from typing import Any, Optional

from backend.core.mother_algorithm.language_router import LanguageRouter, detect_language
from backend.language_engine.shared.reasoning_schema import build_assessment_core


def attach_language_layer(
    pipeline_result: dict[str, Any],
    *,
    preferred_language: Optional[str] = None,
    query: Optional[str] = None,
    accept_language: Optional[str] = None,
) -> dict[str, Any]:
    """
    After neutral reasoning/governance, render locale-native output.

    Returns the original result plus:
      - assessment_core: language-neutral structured data
      - rendered: locale-native phrasing (not client-translated)
      - locale, direction
    """
    core = build_assessment_core(pipeline_result)
    router = LanguageRouter()
    locale, rendered = router.route(
        core,
        preferred_language=preferred_language,
        text=query,
        accept_language=accept_language,
    )

    out = dict(pipeline_result)
    out["assessment_core"] = core
    out["rendered"] = rendered.to_dict()
    out["locale"] = locale
    out["direction"] = rendered.direction
    out["language_layer"] = {
        "version": "multi_native_v1",
        "detected_locale": locale,
        "engine": f"{locale}_native",
    }
    return out


def resolve_request_locale(
    *,
    body_language: Optional[str] = None,
    accept_language: Optional[str] = None,
    query: Optional[str] = None,
) -> str:
    return detect_language(body_language, query, accept_language)
