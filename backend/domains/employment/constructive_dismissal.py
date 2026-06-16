"""
Constructive dismissal deterministic engine (Sovereign Trinity order Workflow B).

Agent ART logic  -  NO LLM, NO free prose. Applies a deterministic legal matrix
and returns a strict JSON-serialisable dict:

  breach classification -> Kaur last-straw -> affirmation trap -> causation -> action

Legal anchors (statutory authority is DB-verified from the legislation corpus;
case-law doctrine is encoded as deterministic matrix logic, not fabricated
citations, because Find Case Law bulk ingestion is licence-gated):
  * ERA 1996 s.95(1)(c)  -  constructive dismissal (employee resigns in response
    to the employer's repudiatory breach)
  * Western Excavating (ECC) Ltd v Sharp [1978]  -  contract (not "unreasonable")
    test  -> encoded in breach classification
  * Kaur v Leeds Teaching Hospitals NHS Trust [2018]  -  final-straw doctrine
    -> encoded in last-straw selection
  * affirmation / delay -> encoded in affirmation_risk

Output fails closed (viability "zero"/human_review) when statutory grounding or
core facts are missing  -  it never invents a favourable answer.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

# Affirmation delay thresholds (days between last repudiatory act and resignation).
_AFFIRM_LOW_MAX = 7
_AFFIRM_MED_MAX = 28


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _statutory_citations(conn=None) -> list[dict]:
    """DB-verified statutory citations for constructive dismissal (s.95, s.94).
    Returns [] if the corpus is unavailable  -  caller then fails closed."""
    own = conn is None
    try:
        if own:
            from ingestion.db import get_connection
            conn = get_connection()
        cites: list[dict] = []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT section_ref,
                       act_title || ' s.' || section_ref AS cite,
                       source_url
                FROM legislation
                WHERE act_title ILIKE '%Employment Rights Act 1996%'
                  AND section_ref IN ('95', '94')
                ORDER BY section_ref
                """
            )
            for section_ref, cite, url in cur.fetchall():
                note = ("constructive dismissal  -  resignation in response to a "
                        "repudiatory breach") if section_ref == "95" else \
                       "right not to be unfairly dismissed"
                cites.append({"cite": cite, "section_ref": section_ref,
                              "url": url, "note": note})
        return cites
    except Exception:
        return []
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def assess_constructive_dismissal(facts: dict, conn=None) -> dict:
    """
    Deterministic constructive-dismissal triage. ``facts`` may include:
      repudiatory_acts: [{date, event, breach_kind: express|implied_mtc}]
      resignation_date: ISO date the employee resigned
      pursuing_grievance: bool (affirmation mitigation)
      resignation_letter_cites_breach: bool

    Returns the strict Workflow-B schema.
    """
    acts_in = facts.get("repudiatory_acts") or []
    resignation = _parse_date(facts.get("resignation_date"))
    pursuing_grievance = bool(facts.get("pursuing_grievance"))
    letter_cites_breach = facts.get("resignation_letter_cites_breach")

    evidence_gaps: list[str] = []

    # statutory grounding (fail closed if absent)
    citations = _statutory_citations(conn)
    has_s95 = any(c["section_ref"] == "95" for c in citations)
    if not has_s95:
        return _fail_closed(
            "no_statutory_grounding",
            "Could not verify ERA 1996 s.95 (constructive dismissal) against the "
            "legal corpus. Refusing to assess without statutory grounding.",
            citations,
        )

    # normalise & validate repudiatory acts
    acts: list[dict] = []
    for a in acts_in:
        d = _parse_date(a.get("date"))
        if d is None:
            continue
        kind = a.get("breach_kind", "implied_mtc")
        if kind not in ("express", "implied_mtc"):
            kind = "implied_mtc"
        acts.append({"date": d, "event": str(a.get("event", "")).strip(), "breach_kind": kind})
    acts.sort(key=lambda x: x["date"])

    if not acts:
        evidence_gaps.append("repudiatory_acts")
    if resignation is None:
        evidence_gaps.append("resignation_date")

    # Cannot assess viability without at least one dated act and a resignation.
    if not acts or resignation is None:
        return _fail_closed(
            "insufficient_facts",
            "Need at least one dated repudiatory act and a resignation date to "
            "assess constructive dismissal.",
            citations,
            evidence_gaps=evidence_gaps,
        )

    # breach classification (Western Excavating: contract test)
    kinds = {a["breach_kind"] for a in acts}
    if kinds == {"express"}:
        breach_type = "express"
    elif kinds == {"implied_mtc"}:
        breach_type = "implied_mtc"
    else:
        breach_type = "both"

    # Kaur last-straw: most recent act is the final straw
    last = acts[-1]
    repudiatory_acts = []
    for idx, a in enumerate(acts):
        weight = "last_straw" if a is last else "contributing"
        repudiatory_acts.append({
            "date": a["date"].isoformat(),
            "event": a["event"],
            "breach_kind": a["breach_kind"],
            "weight": weight,
            "source_event_id": f"ev-{idx + 1:03d}",
        })

    # affirmation trap: delay between last act and resignation
    delay_days = (resignation - last["date"]).days
    if delay_days < 0:
        return _fail_closed(
            "resignation_before_breach",
            "Resignation date precedes the last repudiatory act  -  causation cannot "
            "be established on these facts.",
            citations,
            evidence_gaps=evidence_gaps,
        )
    if delay_days <= _AFFIRM_LOW_MAX:
        affirm_risk = "low"
    elif delay_days <= _AFFIRM_MED_MAX:
        affirm_risk = "medium"
    else:
        affirm_risk = "high"
    if pursuing_grievance and affirm_risk == "high":
        affirm_risk = "medium"  # active grievance can rebut affirmation
    mitigation = ("Employee was pursuing a grievance, which may rebut affirmation"
                  if pursuing_grievance else "")

    # causation
    if letter_cites_breach is None:
        evidence_gaps.append("resignation_letter_cites_breach")
    causation_established = bool(letter_cites_breach) and affirm_risk != "high"

    # viability matrix
    serious_breach = breach_type in ("express", "both") or len(acts) >= 2
    if affirm_risk == "high":
        viability = "low"
    elif serious_breach and affirm_risk == "low" and causation_established:
        viability = "high"
    elif serious_breach and affirm_risk in ("low", "medium"):
        viability = "medium"
    else:
        viability = "low"

    # recommended action
    human_review = affirm_risk == "high" or (viability == "high" and not letter_cites_breach)
    if evidence_gaps and viability != "low":
        recommended_action = "request_more_evidence"
    elif human_review:
        recommended_action = "human_review"
    elif viability in ("high", "medium"):
        recommended_action = "draft_et1_particulars"
    else:
        recommended_action = "do_not_proceed"

    # deterministic confidence + grounding scores
    grounding_score = round(min(1.0, 0.5 + 0.25 * len(citations)), 2)  # statutory-backed
    completeness = 1.0 - min(1.0, 0.2 * len(evidence_gaps))
    confidence_score = round(max(0.0, min(1.0, completeness * (0.9 if causation_established else 0.6))), 2)

    weaknesses: list[str] = []
    if affirm_risk != "low":
        weaknesses.append(f"affirmation risk is {affirm_risk} (delay {delay_days} days)")
    if not letter_cites_breach:
        weaknesses.append("resignation letter does not clearly cite the breach")
    if breach_type == "implied_mtc" and len(acts) == 1:
        weaknesses.append("single implied-term breach is harder to prove than an express breach")

    return {
        "claim_type": "constructive_dismissal",
        "claim_viability": viability,
        "breach_type": breach_type,
        "repudiatory_acts": repudiatory_acts,
        "affirmation_risk": {
            "delay_days": delay_days,
            "risk_level": affirm_risk,
            "mitigation": mitigation,
        },
        "causation_established": causation_established,
        "evidence_gaps": evidence_gaps,
        "recommended_action": recommended_action,
        "grounding_score": grounding_score,
        "confidence_score": confidence_score,
        "key_weaknesses": weaknesses,
        "human_review_required": human_review,
        "citations": citations,
        "legal_boundary": ("This is a self-help triage, not legal advice. lawapp is "
                           "not a solicitor and does not guarantee any outcome."),
        "status": "ok",
    }


def _fail_closed(reason: str, message: str, citations: list[dict],
                 evidence_gaps: Optional[list[str]] = None) -> dict:
    """Safe, non-committal fail-closed result  -  never a favourable assessment."""
    return {
        "claim_type": "constructive_dismissal",
        "claim_viability": "zero",
        "breach_type": "none",
        "repudiatory_acts": [],
        "affirmation_risk": {"delay_days": None, "risk_level": "unknown", "mitigation": ""},
        "causation_established": False,
        "evidence_gaps": evidence_gaps or [],
        "recommended_action": "human_review",
        "grounding_score": 0.0,
        "confidence_score": 0.0,
        "key_weaknesses": [message],
        "human_review_required": True,
        "citations": citations,
        "legal_boundary": ("This is a self-help triage, not legal advice. lawapp is "
                           "not a solicitor and does not guarantee any outcome."),
        "status": "fail_closed",
        "reason": reason,
    }
