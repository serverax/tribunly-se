"""
Conflict Detector.

Detects contradictions between:
  - user input
  - uploaded document facts
  - previous case facts
  - generated documents

GUARDRAIL: If a material conflict is detected, the Brain must flag it
           before generating a legal conclusion. A conflicted fact set
           must not be used to produce binding assessments.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _parse_date_safe(value: Any) -> _dt.date | None:
    if not value:
        return None
    if isinstance(value, _dt.date):
        return value
    try:
        s = str(value).strip()
        if len(s) == 10:
            return _dt.date.fromisoformat(s)
        return _dt.date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def detect_conflicts(
    user_facts: dict,
    document_facts: dict | None = None,
    stored_case_facts: dict | None = None,
) -> list[dict]:
    """
    Detect material conflicts between fact sources.

    Returns a list of conflict dicts:
    {
      "field": str,
      "source_a": str,
      "value_a": any,
      "source_b": str,
      "value_b": any,
      "severity": "critical" | "warning",
      "description": str,
    }
    """
    conflicts: list[dict] = []

    doc = document_facts or {}
    stored = stored_case_facts or {}

    # ── Date conflicts ────────────────────────────────────────────────────────
    date_fields = ["edt", "service_start_date", "wages_due_date"]
    for field in date_fields:
        user_val = _parse_date_safe(user_facts.get(field))
        doc_val = _parse_date_safe(doc.get(field))
        stored_val = _parse_date_safe(stored.get(field))

        if user_val and doc_val and user_val != doc_val:
            diff_days = abs((user_val - doc_val).days)
            severity = "critical" if diff_days > 7 else "warning"
            conflicts.append({
                "field": field,
                "source_a": "user_input",
                "value_a": str(user_val),
                "source_b": "uploaded_document",
                "value_b": str(doc_val),
                "severity": severity,
                "description": (
                    f"Date conflict: user says {field}={user_val}, "
                    f"document says {field}={doc_val} "
                    f"({diff_days} days apart)."
                ),
            })

        if user_val and stored_val and user_val != stored_val:
            diff_days = abs((user_val - stored_val).days)
            severity = "critical" if diff_days > 7 else "warning"
            conflicts.append({
                "field": field,
                "source_a": "user_input",
                "value_a": str(user_val),
                "source_b": "stored_case",
                "value_b": str(stored_val),
                "severity": severity,
                "description": (
                    f"Stored case conflict: user now says {field}={user_val}, "
                    f"but case record has {field}={stored_val}."
                ),
            })

    # ── Amount conflicts ──────────────────────────────────────────────────────
    amount_fields = ["weekly_pay", "unpaid_amount"]
    for field in amount_fields:
        user_val = user_facts.get(field)
        doc_val = doc.get(field)
        if user_val and doc_val:
            try:
                u = float(user_val)
                d = float(doc_val)
                diff_pct = abs(u - d) / max(u, d) if max(u, d) > 0 else 0
                if diff_pct > 0.05:  # >5% difference = conflict
                    conflicts.append({
                        "field": field,
                        "source_a": "user_input",
                        "value_a": u,
                        "source_b": "uploaded_document",
                        "value_b": d,
                        "severity": "warning",
                        "description": (
                            f"Amount conflict: user says {field}=£{u:.2f}, "
                            f"document says £{d:.2f} ({diff_pct:.1%} difference)."
                        ),
                    })
            except (ValueError, TypeError):
                pass

    # ── Logical conflicts ─────────────────────────────────────────────────────

    # Service start must be before EDT
    ssd = _parse_date_safe(user_facts.get("service_start_date"))
    edt = _parse_date_safe(user_facts.get("edt"))
    if ssd and edt and ssd >= edt:
        conflicts.append({
            "field": "service_start_date/edt",
            "source_a": "user_input",
            "value_a": str(ssd),
            "source_b": "user_input",
            "value_b": str(edt),
            "severity": "critical",
            "description": (
                f"Logical conflict: employment start date ({ssd}) is on or after "
                f"effective date of termination ({edt}). "
                f"Service cannot start after dismissal."
            ),
        })

    # EC Day B must be on or after EC Day A
    ec_a = _parse_date_safe(user_facts.get("ec_day_a"))
    ec_b = _parse_date_safe(user_facts.get("ec_day_b"))
    if ec_a and ec_b and ec_b < ec_a:
        conflicts.append({
            "field": "ec_day_a/ec_day_b",
            "source_a": "user_input",
            "value_a": str(ec_a),
            "source_b": "user_input",
            "value_b": str(ec_b),
            "severity": "critical",
            "description": (
                f"EC conflict: ACAS certificate date ({ec_b}) is before "
                f"ACAS contact date ({ec_a}). "
                f"EC certificate cannot be issued before contact was made."
            ),
        })

    return conflicts


def has_critical_conflicts(conflicts: list[dict]) -> bool:
    return any(c["severity"] == "critical" for c in conflicts)
