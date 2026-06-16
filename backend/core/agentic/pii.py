"""
Deterministic PII redaction for outbound model payloads (AC-013 / Phase 4).

Unlike ``deidentify`` (a structured-facts scrubber that drops unknown fields),
this redactor PRESERVES content while replacing PII tokens with placeholders,
so AEE can still process the evidence text  -  but no raw NI number, email, phone,
postcode, sort code or IBAN ever leaves the building.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

# (placeholder, pattern)  -  order matters (email before phone, etc.)
_REDACTORS: list[tuple[str, re.Pattern]] = [
    ("[EMAIL_REDACTED]",    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("[NINO_REDACTED]",     re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b", re.I)),
    ("[IBAN_REDACTED]",     re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,}\b")),
    ("[PHONE_REDACTED]",    re.compile(r"\b(?:0\d{9,10}|\+44\d{9,10})\b")),
    ("[POSTCODE_REDACTED]", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.I)),
    ("[SORTCODE_REDACTED]", re.compile(r"\b\d{2}-\d{2}-\d{2}\b")),
]


def redact_text(text: str) -> str:
    out = text
    for repl, pat in _REDACTORS:
        out = pat.sub(repl, out)
    return out


def scrub_payload(payload: Any) -> Any:
    """Recursively redact PII tokens in every string value, preserving shape."""
    if isinstance(payload, str):
        return redact_text(payload)
    if isinstance(payload, dict):
        return {k: scrub_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [scrub_payload(v) for v in payload]
    return payload


def residual_pii(payload: Any) -> Optional[str]:
    """Return the name of the first residual-PII type found, else None.
    Our own placeholders are stripped before scanning to avoid false positives."""
    s = json.dumps(payload, ensure_ascii=False, default=str)
    for repl, _ in _REDACTORS:
        s = s.replace(repl, "")
    for repl, pat in _REDACTORS:
        if pat.search(s):
            return repl.strip("[]")
    return None
