"""
Case timeline and escalation engine  -  Phase 4C.

Timeline events are generated deterministically from case data:
  - case.key_dates (EDT, deadlines, ACAS dates)
  - uploads (document_uploaded events)
  - generated bundle docs (document_generated events)
  - handoff leads (handoff_triggered events)
  - confirmed extracted facts ONLY (confirmed_extraction source)
  - manually added events from DB (user_entered)

GUARDRAILS:
  - Dates are never invented. Missing dates shown as missing_date=True.
  - Only user_confirmed / user_corrected extracted facts used.
  - Unconfirmed and rejected extracted facts are excluded.
  - Timeline and escalation never claim solicitor has accepted the case.
  - Timeline never implies the platform manages litigation.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from backend.domains.employment.reminders import compute_urgency

logger = logging.getLogger(__name__)

# ── Event type and source constants ───────────────────────────────────────────

VALID_EVENT_TYPES = frozenset({
    "employment_started", "dismissal", "appeal_submitted", "appeal_outcome",
    "acas_day_a", "acas_day_b", "et_deadline", "document_uploaded",
    "document_generated", "handoff_triggered", "custom_user_event",
})

VALID_SOURCES = frozenset({
    "user_entered", "rules_engine", "confirmed_extraction", "system_generated",
})

# ── Escalation state constants ─────────────────────────────────────────────────

ESCALATION_STATES = (
    "solicitor_recommended", "handoff_started",
    "urgent_deadline", "needs_review", "watch", "none",
)

ESCALATION_NEXT_ACTIONS: dict[str, str] = {
    "solicitor_recommended": (
        "Seek advice from a qualified employment solicitor before taking further steps. "
        "lawapp is not a solicitor and does not provide regulated legal advice."
    ),
    "handoff_started": (
        "You have requested a solicitor introduction. "
        "lawapp will contact you when a match is available. "
        "This is free to you. lawapp does not represent you."
    ),
    "urgent_deadline": (
        "Your tribunal deadline is near or has passed. "
        "Start ACAS Early Conciliation immediately if not yet done. "
        "Seek urgent solicitor advice."
    ),
    "needs_review": (
        "Your assessment has areas of uncertainty. "
        "Review your facts and consider seeking advice from a qualified solicitor."
    ),
    "watch": (
        "Your deadline is approaching within 30 days. "
        "Ensure ACAS Early Conciliation is in progress."
    ),
    "none": (
        "No immediate action required. Continue preparing your case documents."
    ),
}

# ── Date formatting ────────────────────────────────────────────────────────────

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _fmt(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    try:
        d = date.fromisoformat(s)
        return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"
    except (ValueError, IndexError):
        return s


# ── Auto-event builder ─────────────────────────────────────────────────────────

def _ev(
    event_type: str,
    event_date: Optional[str],
    title: str,
    description: str = "",
    source: str = "system_generated",
) -> dict:
    return {
        "event_id":     f"auto-{event_type}",
        "event_type":   event_type,
        "event_date":   event_date,
        "display_date": _fmt(event_date) if event_date else None,
        "title":        title,
        "description":  description,
        "source":       source,
        "status":       "active",
        "missing_date": event_date is None,
        "is_manual":    False,
    }


def build_timeline(
    assessment:     dict,
    key_dates:      dict,
    uploads:        list[dict],
    generated_docs: list[dict],
    handoff_leads:  list[dict],
    confirmed_facts: dict,
    db_events:      list[dict],
) -> dict:
    """
    Build the full timeline for a case.

    Returns {events: [...], missing_date_warnings: [...], event_count: int}.

    GUARDRAIL: confirmed_facts must already be filtered to user_confirmed/
    user_corrected non-placeholder values (use get_confirmed_facts() from bundle.py).
    GUARDRAIL: Missing dates are flagged, never invented.
    """
    events: list[dict] = []
    warnings: list[str] = []

    # ── Key dates from case record ─────────────────────────────────────────────
    edt        = key_dates.get("edt")
    start_date = key_dates.get("employment_start_date")
    day_a      = key_dates.get("ec_day_a")
    day_b      = key_dates.get("ec_day_b")
    deadline   = key_dates.get("deadline_date")

    # Employment started
    if start_date:
        events.append(_ev("employment_started", start_date,
                         "Employment commenced",
                         "Employment started with the respondent."))
    else:
        conf_start = confirmed_facts.get("employment_start_date")
        if conf_start:
            events.append(_ev("employment_started", conf_start,
                             "Employment commenced (from confirmed document)",
                             "Date confirmed from uploaded document.",
                             source="confirmed_extraction"))
        else:
            events.append(_ev("employment_started", None,
                             "Employment start date  -  not recorded",
                             "Add your employment start date to complete the timeline."))
            warnings.append("Employment start date not recorded.")

    # Dismissal / EDT
    if edt:
        events.append(_ev("dismissal", edt,
                         "Employment terminated (effective date of termination)",
                         "Your effective date of termination (EDT)."))
    else:
        conf_edt = confirmed_facts.get("edt_candidate")
        if conf_edt:
            events.append(_ev("dismissal", conf_edt,
                             "Dismissal date (confirmed from document)",
                             "EDT candidate confirmed from uploaded document. Verify against your dismissal letter.",
                             source="confirmed_extraction"))
        else:
            events.append(_ev("dismissal", None,
                             "Dismissal date  -  not recorded",
                             "Add your dismissal date (EDT) to complete the timeline."))
            warnings.append("Dismissal date (EDT) not recorded  -  essential for the timeline.")

    # ACAS
    if day_a:
        events.append(_ev("acas_day_a", day_a,
                         "ACAS Early Conciliation started (Day A)",
                         "Date you first contacted ACAS. The stop-clock under ERA 1996 s.207B starts."))
    if day_b:
        events.append(_ev("acas_day_b", day_b,
                         "ACAS EC certificate received (Day B)",
                         "Early Conciliation certificate received. Stop-clock ends."))
    elif day_a and not day_b:
        events.append(_ev("acas_day_b", None,
                         "ACAS EC certificate  -  not yet received",
                         "EC certificate (Day B) outstanding."))
        warnings.append("ACAS EC certificate date (Day B) not yet recorded.")

    # ET deadline  -  always rules_engine source
    if deadline:
        events.append(_ev("et_deadline", deadline,
                         "ET claim limitation date",
                         "Deterministic deadline from ERA 1996 s.111(2). "
                         "You must present your claim by this date.",
                         source="rules_engine"))
    else:
        warnings.append("Tribunal deadline not computed. Run assessment with EDT to compute.")

    # Document uploads
    for u in uploads:
        doc_label = u.get("doc_type", "document").replace("_", " ").title()
        filename  = u.get("original_filename", "[unnamed]")
        ev = _ev("document_uploaded", None,
                 f"Document uploaded: {doc_label}",
                 f"File: {filename}. Extraction status: {u.get('extraction_status','pending')}.")
        ev["event_id"] = f"auto-upload-{u.get('upload_id','')}"
        events.append(ev)

    # Generated documents (bundle / core)
    for doc in generated_docs:
        doc_label = doc.get("doc_type", "document").replace("_", " ").title()
        ev = _ev("document_generated", None,
                 f"Document generated: {doc_label}",
                 "Self-help draft created. Review before use.")
        ev["event_id"] = f"auto-doc-{doc.get('doc_id','')}"
        events.append(ev)

    # Handoff leads
    if handoff_leads:
        latest = handoff_leads[0]
        events.append(_ev("handoff_triggered", None,
                         "Solicitor introduction requested",
                         f"Trigger: {latest.get('trigger_reason','unknown')}. "
                         "lawapp will match with a qualified employment solicitor. "
                         "This is a referral only  -  no solicitor-client relationship created yet."))

    # ── Manual DB events ───────────────────────────────────────────────────────
    for ev in db_events:
        events.append({
            "event_id":     str(ev["id"]),
            "event_type":   ev["event_type"],
            "event_date":   ev["event_date"].isoformat() if ev["event_date"] else None,
            "display_date": _fmt(ev["event_date"].isoformat()) if ev["event_date"] else None,
            "title":        ev["title"],
            "description":  ev.get("description") or "",
            "source":       ev["source"],
            "status":       ev["status"],
            "missing_date": ev["event_date"] is None,
            "is_manual":    True,
        })

    # ── Sort by event_date (nulls last), then event_type priority ─────────────
    _TYPE_ORDER = {
        "employment_started": 0, "dismissal": 1,
        "acas_day_a": 2, "acas_day_b": 3, "et_deadline": 4,
        "appeal_submitted": 5, "appeal_outcome": 6,
        "document_uploaded": 7, "document_generated": 8,
        "handoff_triggered": 9, "custom_user_event": 10,
    }

    def sort_key(e: dict):
        ed = e.get("event_date") or "9999-99-99"
        return (ed, _TYPE_ORDER.get(e["event_type"], 99))

    events.sort(key=sort_key)

    return {
        "events":                events,
        "missing_date_warnings": warnings,
        "event_count":           len(events),
        "timeline_note": (
            "This timeline is informational only. "
            "lawapp is not a solicitor. Dates must be verified against your documents. "
            "Missing dates are flagged  -  lawapp never invents dates."
        ),
    }


# ── Escalation computation ─────────────────────────────────────────────────────

def compute_escalation(
    assessment:     dict,
    key_dates:      dict,
    has_handoff:    bool,
) -> dict:
    """
    Compute the escalation state deterministically from case data.

    Priority: solicitor_recommended > handoff_started > urgent_deadline
              > needs_review > watch > none

    GUARDRAIL: Never claims solicitor has accepted the case.
    GUARDRAIL: Purely deterministic  -  no model involvement.
    """
    rec_next     = assessment.get("recommended_next_step")
    insufficient = bool(assessment.get("insufficient_grounding"))
    strength     = assessment.get("strength", "uncertain")
    deadline_dt  = key_dates.get("deadline_date")

    # Deadline urgency
    urgency_info = compute_urgency(deadline_dt) if deadline_dt else None
    urgency      = urgency_info["urgency"] if urgency_info else None

    triggered: list[str] = []

    # 1. Handoff started
    if has_handoff:
        triggered.append("handoff_started")

    # 2. Solicitor recommended
    needs_solicitor = (
        rec_next == "seek_solicitor"
        or (insufficient and strength not in ("medium", "high"))
    )
    if needs_solicitor:
        triggered.append("solicitor_recommended")

    # 3. Deadline urgency
    if urgency in ("expired", "due_within_7", "due_within_14"):
        triggered.append("urgent_deadline")
    elif urgency == "due_within_30":
        triggered.append("watch")

    # 4. Needs review
    if insufficient or strength == "low":
        triggered.append("needs_review")

    # Compute primary state by priority
    state = "none"
    for candidate in ESCALATION_STATES:
        if candidate in triggered:
            state = candidate
            break

    return {
        "state":            state,
        "state_label":      state.replace("_", " ").title(),
        "triggered_states": triggered,
        "urgency":          urgency,
        "days_remaining":   urgency_info["days_remaining"] if urgency_info else None,
        "next_action":      ESCALATION_NEXT_ACTIONS[state],
        "escalation_note": (
            "Escalation state is computed deterministically from your case data. "
            "lawapp does not conduct litigation or represent you. "
            "No solicitor has been assigned."
        ),
    }
