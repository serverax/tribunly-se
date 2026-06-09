from __future__ import annotations

import re


_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def extract_facts(message: str) -> dict:
    """Extract only explicit facts. Never invent missing facts."""
    facts: dict = {}
    dates = _DATE_RE.findall(message)
    if dates:
        if any(word in message.lower() for word in ("dismiss", "sacked", "fired", "terminated", "edt")):
            facts["dismissal_date"] = dates[-1]
        else:
            facts["date_mentions"] = dates

    service_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(years?|months?)\b", message.lower())
    if service_match:
        value = float(service_match.group(1))
        unit = service_match.group(2)
        facts["years_service"] = value / 12 if unit.startswith("month") else value

    pay_match = re.search(r"\b(?:£|gbp\s*)?(\d{2,6})(?:\s*(?:per|a)\s*week| weekly)\b", message.lower())
    if pay_match:
        facts["gross_weekly_pay"] = float(pay_match.group(1))

    age_match = re.search(r"\bage\s*(\d{2})\b|\b(\d{2})\s*years?\s*old\b", message.lower())
    if age_match:
        facts["age"] = int(age_match.group(1) or age_match.group(2))

    return facts
