"""
Prompt Injection and Jailbreak Guard.

Screens user input and retrieved source text for:
- instruction-override attacks ("ignore previous instructions")
- system-prompt exfiltration attempts
- data exfiltration patterns
- legal source manipulation
- tool-abuse patterns

Every check is logged to injection_guard_log for audit.

GUARDRAIL: This guard runs BEFORE the Brain processes any user message.
           Brain.run_brain() calls check_user_input() as the first step.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Detection patterns ───────────────────────────────────────────────────────

_PATTERNS: list[tuple[str, list[str]]] = [
    ("instruction_override", [
        r"ignore\s+(all\s+)?(previous|prior|above|your)\s+instructions",
        r"disregard\s+(all\s+)?instructions",
        r"forget\s+(everything|all)\s+(you('ve)?\s+been\s+told|above)",
        r"you\s+are\s+now\s+a\s+different\s+(ai|model|assistant)",
        r"override\s+(system|safety|legal)\s+(prompt|instructions|rules)",
        r"act\s+as\s+(if|though)\s+you\s+have\s+no\s+restrictions",
        r"(pretend|simulate|roleplay)\s+(you\s+are\s+)?a\s+solicit",
    ]),
    ("exfiltration", [
        r"(print|output|repeat|show|reveal)\s+(the\s+)?(system\s+prompt|api\s+key|secret)",
        r"what\s+(are|is)\s+(your\s+)?(system\s+prompt|instructions|configuration)",
        r"(send|email|post|upload)\s+(this|the|all)\s+(case|data|document)\s+to",
    ]),
    ("legal_manipulation", [
        r"make\s+up\s+(a\s+)?(citation|case|statute|law|precedent)",
        r"fabricate\s+(a?\s*)?(legal\s+)?(source|authority|citation)",
        r"(tell|say)\s+(the\s+)?user\s+(they\s+)?will\s+(definitely\s+)?win",
        r"guarantee\s+(a\s+)?(legal\s+)?outcome",
    ]),
    ("tool_abuse", [
        r"(call|invoke|execute)\s+all\s+(available\s+)?tools",
        r"bypass\s+(the\s+)?(tool|connector|permission|allowlist)",
        r"(access|read|download)\s+all\s+(user\s+)?(cases|data|documents)",
    ]),
]

_COMPILED: list[tuple[str, list[re.Pattern]]] = [
    (cat, [re.compile(p, re.IGNORECASE | re.DOTALL) for p in pats])
    for cat, pats in _PATTERNS
]


def _scan(text: str) -> tuple[bool, Optional[str], Optional[str]]:
    for category, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                return False, category, pat.pattern
    return True, None, None


# ── Result object ─────────────────────────────────────────────────────────────

class InjectionResult:
    __slots__ = ("clean", "category", "pattern", "duration_ms")

    def __init__(self, clean: bool, category: Optional[str], pattern: Optional[str], duration_ms: float):
        self.clean = clean
        self.category = category
        self.pattern = pattern
        self.duration_ms = duration_ms

    def to_dict(self) -> dict:
        return {
            "clean": self.clean,
            "category": self.category,
            "pattern_excerpt": (self.pattern or "")[:80],
            "duration_ms": self.duration_ms,
        }


# ── Public API ────────────────────────────────────────────────────────────────

def check_user_input(
    message: str,
    user_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> InjectionResult:
    """
    Screen user-supplied message before Brain processing.
    Called as first step in run_brain().
    """
    t0 = time.monotonic()
    clean, category, pattern = _scan(message)
    ms = round((time.monotonic() - t0) * 1000, 2)
    result = InjectionResult(clean, category, pattern, ms)
    _write_log(message[:200], result, user_id, trace_id, "user_input")
    if not clean:
        logger.warning("injection_guard blocked user_input | cat=%s user=%s trace=%s",
                       category, user_id, trace_id)
    return result


def check_retrieved_chunk(
    chunk_text: str,
    source_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> InjectionResult:
    """
    Screen a retrieved legal chunk for indirect injection before context assembly.
    Called by retrieve.py.
    """
    t0 = time.monotonic()
    clean, category, pattern = _scan(chunk_text)
    ms = round((time.monotonic() - t0) * 1000, 2)
    result = InjectionResult(clean, category, pattern, ms)
    if not clean:
        logger.warning("injection_guard flagged chunk | source=%s cat=%s trace=%s",
                       source_id, category, trace_id)
        _write_log(chunk_text[:200], result, None, trace_id, f"chunk:{source_id}")
    return result


def _write_log(
    text_excerpt: str,
    result: InjectionResult,
    user_id: Optional[str],
    trace_id: Optional[str],
    source: str,
) -> None:
    """Persist result to injection_guard_log. Fails silently."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO injection_guard_log
                        (trace_id, user_id, source, text_excerpt, clean, category,
                         pattern_excerpt, duration_ms)
                    VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s)
                    """,
                    (trace_id, user_id, source, text_excerpt,
                     result.clean, result.category,
                     (result.pattern or "")[:80], result.duration_ms),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("injection_guard_log write skipped: %s", exc)
