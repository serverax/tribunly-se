"""
Deadline urgency and reminder state — Phase 3E.

Purely deterministic: urgency is computed from the stored limitation_date
versus a reference date. No model involvement.

Thresholds (in priority order):
  expired        — limitation_date is in the past
  due_within_7   — 0–7 days remaining
  due_within_14  — 8–14 days remaining
  due_within_30  — 15–30 days remaining
  safe           — more than 30 days remaining

GUARDRAIL: urgency state is computed by code from rules-derived dates only.
The LLM never computes, estimates, or recalls deadline information.
"""

from __future__ import annotations

from datetime import date
from typing import Optional


# Urgency threshold labels (ordered; first match wins)
_THRESHOLDS: list[tuple[int, str]] = [
    (-1,  "expired"),        # delta < 0
    (7,   "due_within_7"),   # 0 <= delta <= 7
    (14,  "due_within_14"),  # 8 <= delta <= 14
    (30,  "due_within_30"),  # 15 <= delta <= 30
]
_SAFE = "safe"

URGENCY_LABELS: dict[str, str] = {
    "expired":       "Deadline has passed",
    "due_within_7":  "Deadline within 7 days — act immediately",
    "due_within_14": "Deadline within 14 days — act soon",
    "due_within_30": "Deadline within 30 days — take action",
    "safe":          "No immediate urgency",
}


def compute_urgency(
    limitation_date_str: str,
    today_str: Optional[str] = None,
) -> dict:
    """
    Compute urgency state for a given limitation date.

    Args:
        limitation_date_str: YYYY-MM-DD string of the ET claim deadline.
        today_str: YYYY-MM-DD reference date (default: date.today()).
                   Accepts an explicit date for deterministic testing.

    Returns:
        {
          "urgency":          str,      # expired | due_within_7 | due_within_14 | due_within_30 | safe
          "urgency_label":    str,      # human-readable label
          "days_remaining":   int,      # negative = past
          "limitation_date":  str,      # YYYY-MM-DD (echoed)
          "as_of":            str,      # YYYY-MM-DD reference date used
          "is_urgent":        bool,     # True if <= 30 days OR expired
        }
    """
    today = date.fromisoformat(today_str) if today_str else date.today()
    limit = date.fromisoformat(limitation_date_str)
    days  = (limit - today).days

    urgency = _SAFE
    for threshold, label in _THRESHOLDS:
        if days <= threshold:
            urgency = label
            break

    return {
        "urgency":         urgency,
        "urgency_label":   URGENCY_LABELS[urgency],
        "days_remaining":  days,
        "limitation_date": limitation_date_str,
        "as_of":           today.isoformat(),
        "is_urgent":       days <= 30,
    }


def auto_reminder_types(urgency: str) -> list[str]:
    """
    Return the reminder_type values that should be created for an urgency state.
    Used when auto-creating reminder records on first deadline fetch.
    """
    if urgency == "expired":
        return ["deadline_expired"]
    if urgency in ("due_within_7", "due_within_14", "due_within_30"):
        return ["deadline_approaching"]
    return []
