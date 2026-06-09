"""Reverse data flow — deterministic narrative → employment variables (Test Case A).

DELIBERATELY deterministic (regex/keyword), NOT LLM-generated: extracted legal
profile variables must not be hallucinated. The LLM may optionally enrich, but the
authoritative extraction here is rule-based and reproducible.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Callable, Optional

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_start_date(text: str) -> Optional[date]:
    # "since January 2025" / "since 1 Jan 2025" / "from March 2024"
    m = re.search(r"(?:since|from)\s+(?:\d{1,2}(?:st|nd|rd|th)?\s+)?([A-Za-z]{3,})\s+(\d{4})", text, re.I)
    if m:
        mon = _MONTHS.get(m.group(1).lower()[:3])
        if mon:
            try:
                return date(int(m.group(2)), mon, 1)
            except ValueError:
                return None
    # ISO "since 2025-01-15"
    m = re.search(r"(?:since|from)\s+(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _tenure_months(start: date, today: date) -> int:
    return max(0, (today.year - start.year) * 12 + (today.month - start.month))


def extract_employment_vars(raw_text: str, today: Optional[date] = None) -> dict:
    """Deterministically extract employment variables from a narrative."""
    today = today or date.today()
    low = (raw_text or "").lower()

    if "zero hour" in low or "zero-hour" in low:
        employment_type = "zero_hours"
    elif "fixed term" in low or "fixed-term" in low:
        employment_type = "fixed_term"
    elif "contractor" in low or "self-employed" in low or "self employed" in low:
        employment_type = "contractor"
    elif "permanent" in low:
        employment_type = "permanent"
    else:
        employment_type = "unknown"

    if (("cancel" in low and "shift" in low)
            or "not to come" in low or "don't come" in low or "do not come" in low
            or "dont come" in low):
        recent_incident = "short_notice_cancellation"
    elif any(w in low for w in ("fired", "dismissed", "sacked", "let go", "made redundant", "terminated")):
        recent_incident = "dismissal"
    elif "grievance" in low:
        recent_incident = "grievance"
    elif "discriminat" in low:
        recent_incident = "discrimination"
    else:
        recent_incident = None

    start = _parse_start_date(raw_text)
    return {
        "employment_type": employment_type,
        "tenure_months": _tenure_months(start, today) if start else 0,
        "has_probation_clause": "probation" in low,
        "recent_incident": recent_incident,
        "start_date": start.isoformat() if start else None,
    }


def _get_conn():
    from ingestion.db import get_connection
    return get_connection()


def write_user_profile(user_id: str, variables: dict, jurisdiction_code: str = "EW",
                       get_conn: Optional[Callable] = None) -> None:
    """Upsert the extracted variables into user_legal_profiles (idempotent per user)."""
    conn = (get_conn or _get_conn)()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_legal_profiles
                    (user_id, employment_type, tenure_months, has_probation_clause,
                     recent_incident, start_date, jurisdiction_code, updated_at)
                VALUES (%s::uuid,%s,%s,%s,%s,%s,%s, now())
                ON CONFLICT (user_id) DO UPDATE SET
                    employment_type      = EXCLUDED.employment_type,
                    tenure_months        = EXCLUDED.tenure_months,
                    has_probation_clause = EXCLUDED.has_probation_clause,
                    recent_incident      = EXCLUDED.recent_incident,
                    start_date           = EXCLUDED.start_date,
                    jurisdiction_code    = EXCLUDED.jurisdiction_code,
                    updated_at           = now()
                """,
                (user_id, variables["employment_type"], variables["tenure_months"],
                 variables["has_probation_clause"], variables.get("recent_incident"),
                 variables.get("start_date"), jurisdiction_code),
            )
        conn.commit()
    finally:
        conn.close()
