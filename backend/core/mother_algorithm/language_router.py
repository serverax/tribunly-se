"""Mother algorithm language routing."""

from __future__ import annotations

import re
from typing import Optional

from backend.language_engine.ar.engine import ArabicLanguageEngine
from backend.language_engine.base_interface import LanguageEngine, RenderedAssessment
from backend.language_engine.en.engine import EnglishLanguageEngine
from backend.language_engine.shared.legal_types import DEFAULT_LOCALE, SUPPORTED_LOCALES

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")


def detect_language(
    preferred_language: Optional[str] = None,
    text: Optional[str] = None,
    accept_language: Optional[str] = None,
) -> str:
    """
    Resolve locale: explicit preference > Accept-Language > Arabic script in text > en.
    """
    pref = (preferred_language or "").strip().lower()
    if pref.startswith("ar"):
        return "ar"
    if pref.startswith("en"):
        return "en"

    if accept_language:
        first = accept_language.split(",")[0].strip().lower()
        if first.startswith("ar"):
            return "ar"
        if first.startswith("en"):
            return "en"

    if text and _ARABIC_RE.search(text):
        return "ar"

    return DEFAULT_LOCALE


class LanguageRouter:
    """Route neutral assessment cores to native locale engines."""

    def __init__(self) -> None:
        self._engines: dict[str, LanguageEngine] = {
            "en": EnglishLanguageEngine(),
            "ar": ArabicLanguageEngine(),
        }

    def get_engine(self, locale: str) -> LanguageEngine:
        loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
        return self._engines[loc]

    def route(
        self,
        assessment_core: dict,
        *,
        preferred_language: Optional[str] = None,
        text: Optional[str] = None,
        accept_language: Optional[str] = None,
    ) -> tuple[str, RenderedAssessment]:
        locale = detect_language(preferred_language, text, accept_language)
        engine = self.get_engine(locale)
        rendered = engine.render(assessment_core)
        return locale, rendered
