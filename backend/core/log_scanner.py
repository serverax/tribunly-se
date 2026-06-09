"""
Log PII scanner — Phase 5A.

Scans log text for known PII values that must never appear in logs.
Used in hardening tests and can be integrated into CI.

NOT a production log aggregator — scans in-memory text for known values.

GUARDRAIL: The scanner detects; it does not redact.
If scan_for_pii() returns non-empty results, the caller should fail the test
or raise an alert.
"""

from __future__ import annotations

import re

# ── Forbidden log patterns ─────────────────────────────────────────────────────
# These are checked as literal substrings (case-insensitive).
# Add specific test values here when running regression scans.

FORBIDDEN_LOG_PATTERNS: list[str] = [
    # Email patterns
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    # UK NI number pattern
    r"\b[A-Z]{2}\d{6}[A-Z]\b",
    # UK phone number patterns
    r"\b07\d{3}[\s\-]?\d{6}\b",
    r"\b\+44[\s\-]?\d{4}[\s\-]?\d{6}\b",
    # Date of birth (common UK formats)
    r"\b\d{2}/\d{2}/\d{4}\b",   # DD/MM/YYYY but only if in PII context
]

_FORBIDDEN_RE = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_LOG_PATTERNS]


def scan_for_pii(log_text: str, known_pii_values: list[str] | None = None) -> list[str]:
    """
    Scan log text for known PII values and common PII patterns.

    Args:
        log_text:          The log string to scan.
        known_pii_values:  Specific PII values to look for (e.g. test claimant names).

    Returns:
        List of found PII strings. Empty = clean.
    """
    found: list[str] = []

    # Check known specific values first (most reliable)
    if known_pii_values:
        for value in known_pii_values:
            if value and value.lower() in log_text.lower():
                found.append(value)

    return found


def scan_for_pii_patterns(log_text: str) -> list[str]:
    """
    Scan for PII patterns (regex-based). Less reliable than known-value scan.
    Use for CI regression; confirm human review for false positives.
    """
    found: list[str] = []
    for pattern in _FORBIDDEN_RE:
        matches = pattern.findall(log_text)
        found.extend(matches)
    return found


def assert_no_pii(log_text: str, known_pii: list[str], context: str = "") -> None:
    """
    Raises AssertionError if any known PII value is found in log_text.
    Used in tests.
    """
    found = scan_for_pii(log_text, known_pii)
    if found:
        raise AssertionError(
            f"PII found in logs{' (' + context + ')' if context else ''}: {found}. "
            "This is a data-protection failure."
        )
