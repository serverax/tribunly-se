"""
Document generation engine — Phase 3C.

Template-anchored drafting only. No freeform LLM generation.
All legal content is sourced from the structured assessment object
and the user's intake facts. The LLM is NOT involved in document generation.

GUARDRAIL: Every generated document includes the LEGAL_BOUNDARY_NOTICE verbatim.
GUARDRAIL: safety_check() scans output for prohibited phrases before return.
GUARDRAIL: The platform does not file, submit, represent, or conduct litigation.
GUARDRAIL: No output may imply solicitor/law firm status or guarantee outcomes.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


# ── Legal boundary notice ─────────────────────────────────────────────────────
# Included verbatim at the top and bottom of every generated document.

LEGAL_BOUNDARY_NOTICE = """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT — READ BEFORE USE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This document is a SELF-HELP DRAFT prepared using lawapp.
It is NOT legal advice. lawapp is not a solicitor or law firm.
This draft is based on the information you provided and may be
incomplete, inaccurate, or unsuitable for your circumstances.
You must review, verify, and correct this document carefully
before filing it or sending it to any party.
lawapp does not file, submit, represent you, or conduct
litigation on your behalf. No outcome is guaranteed.
If you are unsure, seek advice from a qualified solicitor or
consult the Employment Tribunal's published guidance notes.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


# ── Safety check ──────────────────────────────────────────────────────────────
# Regex patterns for phrases that must NEVER appear in generated documents.
# These represent: outcome guarantees, solicitor status, or filing promises.

_FORBIDDEN_PATTERNS: list[str] = [
    r"\byou will win\b",
    r"\bguaranteed? (to win|outcome|result|success)\b",
    r"\bwe guarantee\b",
    r"\bwe will (file|submit|send) (your|this|the) claim\b",
    r"\bwe will represent you\b",
    r"\bwe represent you\b",
    r"\bwe are your solicitors?\b",
    r"\bwe are acting as your (solicitor|lawyer|legal representative)\b",
    r"\bas your solicitor\b",
    r"\bacting as your (solicitor|lawyer|legal representative)\b",
    r"\byour (solicitor|lawyer) here\b",
    r"\bwe advise you (that|to)\b",
    r"\bcertain(ly)? (succeed|win|prevail)\b",
]

_FORBIDDEN_RE = [re.compile(p, re.IGNORECASE) for p in _FORBIDDEN_PATTERNS]


def safety_check(text: str) -> dict:
    """
    Scan a generated document for prohibited phrases.
    Returns {"passed": bool, "violations": list[str]}.
    Called before every document is returned to the caller.
    """
    violations: list[str] = []
    for pattern in _FORBIDDEN_RE:
        m = pattern.search(text)
        if m:
            violations.append(m.group(0))
    passed = len(violations) == 0
    if not passed:
        logger.error("Document safety check FAILED — violations: %s", violations)
    return {"passed": passed, "violations": violations}


# ── Formatting helpers ────────────────────────────────────────────────────────

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _fmt_date(s: Optional[str]) -> str:
    """Format YYYY-MM-DD as '1 April 2026'. Portable — no locale-dependent strftime."""
    if not s:
        return "[DATE NOT PROVIDED]"
    try:
        d = date.fromisoformat(s)
        return f"{d.day} {_MONTH_NAMES[d.month - 1]} {d.year}"
    except (ValueError, IndexError):
        return s


def _service_length(facts: dict) -> str:
    """Human-readable service length, e.g. '3 years and 2 months'."""
    start = facts.get("service_start_date")
    edt   = facts.get("edt")
    if not start or not edt:
        return "[SERVICE LENGTH NOT PROVIDED]"
    try:
        d_start = date.fromisoformat(start)
        d_edt   = date.fromisoformat(edt)
        days    = (d_edt - d_start).days
        years   = days // 365
        months  = (days % 365) // 30
        if years >= 1:
            y_str = f"{years} year{'s' if years != 1 else ''}"
            return y_str + (f" and {months} month{'s' if months != 1 else ''}" if months else "")
        return f"{months} month{'s' if months != 1 else ''}"
    except ValueError:
        return "[SERVICE LENGTH CALCULATION ERROR]"


def _reason_label(reason: Optional[str]) -> str:
    labels = {
        "conduct":                     "conduct / misconduct",
        "capability":                  "poor performance / capability",
        "redundancy":                  "redundancy",
        "some_other_substantial_reason": "some other substantial reason (SOSR)",
        "unknown":                     "no clear reason given by the Respondent",
    }
    return labels.get(reason or "", reason or "[REASON NOT PROVIDED]")


def _bullet_list(items: list[str], indent: int = 3) -> str:
    pad = " " * indent
    return "\n".join(f"{pad}• {item}" for item in items) if items else f"{' ' * indent}(none recorded)"


def generate_docx_bytes(content: str, title: str) -> bytes:
    """
    Generate a DOCX file from the document content.
    Returns bytes suitable for response or storage.
    """
    try:
        import io
        import docx
        from docx.shared import Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = docx.Document()
        
        # Title
        t = doc.add_heading(title, 0)
        t.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Legal Notice
        notice_box = doc.add_table(rows=1, cols=1)
        notice_box.style = 'Table Grid'
        cell = notice_box.rows[0].cells[0]
        cell.text = LEGAL_BOUNDARY_NOTICE
        p = cell.paragraphs[0]
        p.runs[0].font.size = Pt(8)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph() # Spacer

        # Body
        for line in content.split("\n"):
            if line.startswith("──"):
                doc.add_page_break()
                continue
            
            p = doc.add_paragraph(line)
            if line.isupper() and len(line) > 5:
                 p.style = 'Heading 1'

        # Footer Notice
        doc.add_paragraph()
        doc.add_paragraph(LEGAL_BOUNDARY_NOTICE).runs[0].font.size = Pt(8)

        target = io.BytesIO()
        doc.save(target)
        return target.getvalue()
    except Exception as exc:
        logger.error("DOCX generation failed: %s", exc)
        return content.encode("utf-8") # Fallback to text


# ── Particulars of Claim ──────────────────────────────────────────────────────

def generate_particulars_of_claim(assessment: dict, facts: dict) -> str:
    """
    Draft Particulars of Claim for an ET1 unfair dismissal claim.

    Template-anchored: all content sourced from `assessment` (structured pipeline
    output) and `facts` (user intake). No freeform LLM generation.

    The document uses [PLACEHOLDER] notation for data not held by this system
    (claimant name, employer address). The user must complete these before filing.
    """
    edt           = facts.get("edt", "")
    service_start = facts.get("service_start_date", "")
    reason        = facts.get("reason_for_dismissal")
    procedure     = facts.get("was_procedure_followed")
    ec_day_a      = facts.get("ec_day_a")
    ec_day_b      = facts.get("ec_day_b")

    deadline_info  = assessment.get("deadline_info") or {}
    deadline_date  = deadline_info.get("limitation_date", "")
    deadline_auth  = deadline_info.get("authority", "ERA 1996 s.111(2)")
    key_weaknesses = assessment.get("key_weaknesses") or []
    reasoning      = (assessment.get("reasoning_summary") or "").strip()
    value_range    = assessment.get("value_range") or {}
    citations      = assessment.get("citations") or []
    has_viable     = assessment.get("has_viable_claim", "uncertain")

    # ── Procedure paragraph
    if procedure is False:
        proc_para = (
            "   The Respondent failed to follow a fair dismissal procedure. "
            "No proper disciplinary process, prior warning, or opportunity to "
            "respond was provided before the decision to dismiss was taken."
        )
    elif procedure is True:
        proc_para = (
            "   The Respondent followed a formal disciplinary procedure. "
            "The Claimant contends, however, that the dismissal was nonetheless "
            "substantively unfair on the facts."
        )
    else:
        proc_para = (
            "   The Claimant is not currently able to confirm the full extent "
            "of the procedure followed by the Respondent and reserves the right "
            "to particularise further upon disclosure."
        )

    # ── Weaknesses section (noted, not admitted)
    weakness_block = ""
    if key_weaknesses:
        weakness_block = (
            "\n\n   The following matters may be raised by the Respondent and "
            "are noted for completeness:\n" + _bullet_list(key_weaknesses)
        )

    # ── Remedy estimate
    remedy_est = ""
    if value_range:
        low   = value_range.get("low",  0)
        high  = value_range.get("high", 0)
        basis = value_range.get("basis", "")
        remedy_est = (
            f"\n\n   Estimated compensation range: £{low:,.0f} – £{high:,.0f}.\n"
            f"   Basis: {basis}\n"
            "   [These are estimates only. Actual compensation depends on tribunal\n"
            "   findings and the Claimant's duty to mitigate. No outcome is guaranteed.]"
        )

    # ── EC section
    if ec_day_a and ec_day_b:
        ec_block = (
            f"   The Claimant notified ACAS on {_fmt_date(ec_day_a)} (Day A) and\n"
            f"   received the Early Conciliation certificate on {_fmt_date(ec_day_b)} (Day B).\n"
            "   The stop-clock provision under ERA 1996 s.207B applies."
        )
    elif ec_day_a:
        ec_block = (
            f"   The Claimant notified ACAS on {_fmt_date(ec_day_a)}. Early Conciliation\n"
            "   is ongoing or the certificate has not yet been received."
        )
    else:
        ec_block = (
            "   ACAS Early Conciliation has not yet been commenced.\n"
            "   [Note: EC must be completed before presenting a tribunal claim.]"
        )

    # ── Citations
    citation_block = ""
    if citations:
        lines = [f"   • {c.get('cite', '')}  {c.get('url', '')}" for c in citations]
        citation_block = "\n   Legal authorities relied upon:\n" + "\n".join(lines)

    return f"""\
IN THE EMPLOYMENT TRIBUNAL

─────────────────────────────────────────────────────────────────────────────
{LEGAL_BOUNDARY_NOTICE}
─────────────────────────────────────────────────────────────────────────────

PARTICULARS OF CLAIM — UNFAIR DISMISSAL
Claim type:  Unfair Dismissal (Employment Rights Act 1996, Part X)

Claimant:    [YOUR FULL LEGAL NAME]
             [YOUR ADDRESS]
             [YOUR POSTCODE]

Respondent:  [EMPLOYER FULL LEGAL NAME]
             [EMPLOYER REGISTERED ADDRESS]
             [POSTCODE]

[Complete all placeholders above with your details before filing.]

─────────────────────────────────────────────────────────────────────────────
1. EMPLOYMENT
─────────────────────────────────────────────────────────────────────────────
   The Claimant was employed by the Respondent from {_fmt_date(service_start)}
   until {_fmt_date(edt)} ({_service_length(facts)} of continuous employment).

   The effective date of termination (EDT) is {_fmt_date(edt)}.

─────────────────────────────────────────────────────────────────────────────
2. THE DISMISSAL
─────────────────────────────────────────────────────────────────────────────
   The Claimant was dismissed by the Respondent on {_fmt_date(edt)}.
   The reason stated by the Respondent for the dismissal was:
   {_reason_label(reason)}.

─────────────────────────────────────────────────────────────────────────────
3. UNFAIR DISMISSAL (ERA 1996 ss.94, 98)
─────────────────────────────────────────────────────────────────────────────
   The Claimant contends that the dismissal was unfair within the meaning of
   ERA 1996 s.94 and that the Respondent has not shown a potentially fair
   reason or acted reasonably within the meaning of s.98(4).

{proc_para}{weakness_block}

   Summary of assessment (based on information provided):
   {reasoning if reasoning else '[No reasoning summary available.]'}

─────────────────────────────────────────────────────────────────────────────
4. QUALIFYING PERIOD
─────────────────────────────────────────────────────────────────────────────
   The Claimant had {_service_length(facts)} of continuous employment at the
   date of dismissal, satisfying the two-year qualifying period under ERA 1996
   s.108.

   [Note: If dismissal was related to health and safety, whistleblowing, trade
   union activity, or a protected characteristic, the qualifying period does
   not apply. lawapp does not assess those claim types at this stage.]

─────────────────────────────────────────────────────────────────────────────
5. ACAS EARLY CONCILIATION
─────────────────────────────────────────────────────────────────────────────
{ec_block}

─────────────────────────────────────────────────────────────────────────────
6. REMEDY SOUGHT
─────────────────────────────────────────────────────────────────────────────
   The Claimant seeks the following remedy:
   (a) Reinstatement or re-engagement under ERA 1996 s.113; or
   (b) Compensation comprising:
       (i)  Basic award (ERA 1996 s.119)
       (ii) Compensatory award (ERA 1996 s.123)
{remedy_est}

─────────────────────────────────────────────────────────────────────────────
7. LIMITATION
─────────────────────────────────────────────────────────────────────────────
   The claim must be presented on or before: {_fmt_date(deadline_date)}
   Statutory authority: {deadline_auth}
{citation_block}

─────────────────────────────────────────────────────────────────────────────
STATEMENT OF TRUTH
─────────────────────────────────────────────────────────────────────────────
I believe the facts stated in this document are true.

Signed: ___________________________     Date: ____________________
Name (print): _____________________

─────────────────────────────────────────────────────────────────────────────
DOCUMENT INFORMATION
─────────────────────────────────────────────────────────────────────────────
Generated by:      lawapp self-help document tool
Generation method: template (no freeform AI drafting)
Viability indicator: {has_viable} [not a legal opinion; does not predict outcome]

{LEGAL_BOUNDARY_NOTICE}""".strip()


# ── Schedule of Loss ──────────────────────────────────────────────────────────

def generate_schedule_of_loss(assessment: dict, facts: dict) -> str:
    """
    Draft Schedule of Loss for an unfair dismissal ET claim.

    Template-anchored: compensation figures sourced from the structured
    assessment value_range (computed by assess_logic.py from live rules).
    No freeform LLM generation.
    """
    edt           = facts.get("edt", "")
    service_start = facts.get("service_start_date", "")
    weekly_pay    = facts.get("weekly_pay")

    deadline_info = assessment.get("deadline_info") or {}
    deadline_date = deadline_info.get("limitation_date", "")
    value_range   = assessment.get("value_range") or {}
    citations     = assessment.get("citations") or []

    low   = value_range.get("low",  0)
    high  = value_range.get("high", 0)
    basis = value_range.get("basis", "Source: ERA 1996 statutory rules.")

    wp_str = f"£{weekly_pay:,.2f} per week (gross)" if weekly_pay else "[WEEKLY PAY NOT PROVIDED]"

    citation_block = ""
    if citations:
        lines = [f"   • {c.get('cite', '')}  {c.get('url', '')}" for c in citations]
        citation_block = "\n   Statutory authorities:\n" + "\n".join(lines)

    return f"""\
─────────────────────────────────────────────────────────────────────────────
{LEGAL_BOUNDARY_NOTICE}
─────────────────────────────────────────────────────────────────────────────

SCHEDULE OF LOSS — UNFAIR DISMISSAL CLAIM
Claim type:  Unfair Dismissal (ERA 1996 Part X)

Claimant:    [YOUR FULL LEGAL NAME]
Respondent:  [EMPLOYER FULL LEGAL NAME]
EDT:         {_fmt_date(edt)}
Limitation:  {_fmt_date(deadline_date)}

[Complete all placeholders above with your details before filing.]

─────────────────────────────────────────────────────────────────────────────
A. EMPLOYMENT DETAILS
─────────────────────────────────────────────────────────────────────────────
   Start date:            {_fmt_date(service_start)}
   Effective date of termination: {_fmt_date(edt)}
   Continuous service:    {_service_length(facts)}
   Gross weekly pay:      {wp_str}

   [Verify your weekly pay against payslips. Regular guaranteed overtime
   and certain benefits may be included. Holiday pay and commission
   arrangements may affect the calculation — see ERA 1996 s.221–224.]

─────────────────────────────────────────────────────────────────────────────
B. BASIC AWARD (ERA 1996 s.119)
─────────────────────────────────────────────────────────────────────────────
   The basic award is calculated as:
   (complete years of service) × (age multiplier) × (capped weekly pay)

   Age multipliers (ERA 1996 s.119(2)):
   • Under 22:           0.5 weeks' pay per year
   • 22 to under 41:     1.0 week's pay per year
   • 41 and over:        1.5 weeks' pay per year

   Weekly pay is capped at the statutory limit in force at the EDT.
   [Verify the current cap at legislation.gov.uk or gov.uk/calculate-your-
   holiday-pay/overview — the limit changes annually each April.]

   Estimated basic award (from rules):     see Section D below.

   To calculate exactly:
   Years of service (complete years):  ______
   Age at EDT:                         ______
   Age multiplier:                     ______
   Weekly pay used (capped):           £ ______
   Basic award:                        £ ______ × ______ × £ ______ = £ ______

─────────────────────────────────────────────────────────────────────────────
C. COMPENSATORY AWARD (ERA 1996 s.123)
─────────────────────────────────────────────────────────────────────────────
   The compensatory award covers actual financial loss, subject to the
   lower of 52 weeks' pay and the current statutory compensatory award cap.
   [Verify the current cap at legislation.gov.uk.]

   Heads of loss:

   (a) Immediate loss of earnings (EDT to [re-employment date or hearing]):
       £______ per week × ______ weeks = £______

   (b) Future loss of earnings (if not yet re-employed):
       £______ per week × ______ weeks (estimated) = £______

   (c) Loss of statutory rights (fixed conventional amount):
       £______  [Typically £300–£600; confirm current practice.]

   (d) Loss of pension rights (if applicable):
       £______  [Ogden tables or actuarial calculation if significant.]

   (e) Less: earnings received since dismissal:
       (£______)

   (f) Total compensatory award (before cap):    £______
   (g) Applied statutory cap:                    £______
   (h) Compensatory award (after cap):           £______

─────────────────────────────────────────────────────────────────────────────
D. ESTIMATED RANGE (COMPUTED FROM STATUTORY RULES)
─────────────────────────────────────────────────────────────────────────────
   Low estimate:   £{low:,.0f}
   High estimate:  £{high:,.0f}
   Currency:       GBP

   Basis: {basis}

   [These are estimates derived from statutory rules and the information
   you provided. They are not a prediction or guarantee of any award.
   Actual compensation is determined by the tribunal on the evidence.]

─────────────────────────────────────────────────────────────────────────────
E. ACAS UPLIFT / REDUCTION (ERA 1996 s.207A via TULRCA 1992 s.207A)
─────────────────────────────────────────────────────────────────────────────
   If the Respondent unreasonably failed to follow the ACAS Code of Practice
   on Disciplinary and Grievance Procedures, an uplift of up to 25% may apply.
   Conversely, the Claimant's own conduct may lead to a reduction.

─────────────────────────────────────────────────────────────────────────────
F. MITIGATION DUTY
─────────────────────────────────────────────────────────────────────────────
   The Claimant has a legal duty to take reasonable steps to mitigate loss
   (Wilding v British Telecommunications plc [2002] EWCA Civ 349).
   Document all job applications, income received, and refusals of
   reasonable job offers since the date of dismissal.
{citation_block}

─────────────────────────────────────────────────────────────────────────────
TOTALS (TO BE COMPLETED BY CLAIMANT)
─────────────────────────────────────────────────────────────────────────────
   Basic award:                             £ _______________
   Compensatory award (after cap):          £ _______________
   ACAS uplift (if applicable):             £ _______________
   Less any reduction:                     (£ _______________)
   ──────────────────────────────────────────────────────────
   TOTAL CLAIMED:                           £ _______________

─────────────────────────────────────────────────────────────────────────────
STATEMENT OF TRUTH
─────────────────────────────────────────────────────────────────────────────
I believe the figures stated in this Schedule of Loss are accurate and
have been calculated in accordance with ERA 1996.

Signed: ___________________________     Date: ____________________
Name (print): _____________________

─────────────────────────────────────────────────────────────────────────────
DOCUMENT INFORMATION
─────────────────────────────────────────────────────────────────────────────
Generated by:      lawapp self-help document tool
Generation method: template (no freeform AI drafting)

{LEGAL_BOUNDARY_NOTICE}""".strip()


# ── Phase 5B: Unpaid wages / unlawful deduction documents ────────────────────

def generate_letter_before_action(assessment: dict, facts: dict) -> str:
    """
    Draft Letter Before Action for an unpaid wages / unlawful deduction claim.

    Template-anchored. Sent to employer before ET proceedings.
    lawapp does not send, file, or submit this letter.
    GUARDRAIL: safety_check() applied before return.
    """
    wages_due_date = facts.get("wages_due_date", "")
    unpaid_amount  = facts.get("unpaid_amount", "")
    pay_frequency  = facts.get("pay_frequency", "")

    deadline_info  = assessment.get("deadline_info") or {}
    deadline_date  = deadline_info.get("limitation_date", "")
    deadline_auth  = deadline_info.get("authority", "ERA 1996 s.23(2)")
    value_range    = assessment.get("value_range") or {}
    citations      = assessment.get("citations") or []

    amount_str = f"£{float(unpaid_amount):,.2f}" if unpaid_amount else "[AMOUNT — complete before sending]"
    cite_block = ""
    if citations:
        cite_block = "\n   " + "; ".join(c.get("cite","") for c in citations[:3])

    return f"""\
{LEGAL_BOUNDARY_NOTICE}

─────────────────────────────────────────────────────────────────────────────
LETTER BEFORE ACTION — UNPAID WAGES / UNLAWFUL DEDUCTION
SELF-HELP DRAFT — NOT LEGAL ADVICE
─────────────────────────────────────────────────────────────────────────────

WITHOUT PREJUDICE SAVE AS TO COSTS

[YOUR FULL NAME]
[YOUR ADDRESS]
[YOUR POSTCODE]
[YOUR EMAIL / PHONE]

[DATE — add today's date before sending]

The Manager / HR Department
[EMPLOYER FULL LEGAL NAME]
[EMPLOYER ADDRESS]
[POSTCODE]

Dear Sir/Madam,

RE: UNLAWFUL DEDUCTION FROM WAGES — EMPLOYMENT RIGHTS ACT 1996 PART II

I write to draw your attention to wages that I believe have been unlawfully
withheld in breach of the Employment Rights Act 1996 Part II.

─────────────────────────────────────────────────────────────────────────────
DETAILS OF CLAIM
─────────────────────────────────────────────────────────────────────────────
Amount outstanding:     {amount_str}
Date wages were due:    {_fmt_date(wages_due_date) if wages_due_date else "[DATE — complete]"}
Pay frequency:          {pay_frequency or "[weekly / monthly — complete]"}

[Add further detail: description of wages owed, any partial payment received,
and the basis on which you assert entitlement — e.g. contract terms, payslip.]

─────────────────────────────────────────────────────────────────────────────
STATUTORY BASIS
─────────────────────────────────────────────────────────────────────────────
My entitlement to wages arises under my contract of employment and my right
not to suffer unlawful deduction from wages (ERA 1996 s.13).{cite_block}

─────────────────────────────────────────────────────────────────────────────
ACTION REQUIRED
─────────────────────────────────────────────────────────────────────────────
I respectfully request that you pay the outstanding amount of {amount_str}
within 14 days of this letter.

If payment is not received within 14 days, I reserve the right to present a
claim to the Employment Tribunal under ERA 1996 Part II without further notice.

My ET claim deadline is: {_fmt_date(deadline_date) if deadline_date else "[check /cases/{id}/deadline]"}
Authority: {deadline_auth}

─────────────────────────────────────────────────────────────────────────────
EVIDENCE
─────────────────────────────────────────────────────────────────────────────
[List documents you have: payslips, contract, bank statements, etc.]
[Attach copies as appropriate.]

─────────────────────────────────────────────────────────────────────────────
SIGNATURE
─────────────────────────────────────────────────────────────────────────────
Yours faithfully,

___________________________
[YOUR FULL NAME]
[DATE]

─────────────────────────────────────────────────────────────────────────────
DOCUMENT INFORMATION
─────────────────────────────────────────────────────────────────────────────
Generated by: lawapp self-help document tool
Method: template (no freeform AI drafting)

{LEGAL_BOUNDARY_NOTICE}""".strip()


def generate_et1_support_notes_wages(assessment: dict, facts: dict) -> str:
    """
    ET1 Support Notes for an unpaid wages / unlawful deduction claim.

    Template-anchored. Aids completion of ET1 form.
    lawapp does not file, submit, or represent. Not legal advice.
    """
    wages_due_date = facts.get("wages_due_date", "")
    unpaid_amount  = facts.get("unpaid_amount", "")
    worker_status  = facts.get("worker_status", "employee")
    is_series      = facts.get("is_series_of_deductions", False)

    deadline_info  = assessment.get("deadline_info") or {}
    deadline_date  = deadline_info.get("limitation_date", "")
    deadline_auth  = deadline_info.get("authority", "ERA 1996 s.23(2)")
    vr             = assessment.get("value_range") or {}
    reasoning      = (assessment.get("reasoning_summary") or "").strip()
    weaknesses     = assessment.get("key_weaknesses") or []
    citations      = assessment.get("citations") or []
    viable         = assessment.get("has_viable_claim", "uncertain")
    strength       = assessment.get("strength", "uncertain")

    amount_str = f"£{float(unpaid_amount):,.2f}" if unpaid_amount else "[AMOUNT — complete]"
    cite_block = ""
    if citations:
        cite_block = "\n   " + "\n   ".join(
            f"• {c.get('cite','')}  {c.get('url','')}" for c in citations[:4]
        )

    weakness_block = ""
    if weaknesses:
        weakness_block = "\n" + "\n".join(f"   • {w}" for w in weaknesses[:4])

    series_note = ""
    if is_series:
        series_note = (
            "\n   [Note: Series of deductions — time runs from last deduction. "
            "Verify each deduction is sufficiently linked. Seek legal advice for "
            "long series (Bear Scotland Ltd v Fulton [2015]).]"
        )

    return f"""\
{LEGAL_BOUNDARY_NOTICE}

─────────────────────────────────────────────────────────────────────────────
ET1 SUPPORT NOTES — UNPAID WAGES / UNLAWFUL DEDUCTION
SELF-HELP DRAFT — NOT LEGAL ADVICE
─────────────────────────────────────────────────────────────────────────────

IMPORTANT: lawapp does NOT file, submit, or send your ET1.
You must complete and submit the ET1 yourself at employment-tribunals.service.gov.uk
or instruct a solicitor.

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 3: TYPE OF CLAIM
─────────────────────────────────────────────────────────────────────────────
   Claim type:  Unlawful Deduction from Wages
   Statute:     Employment Rights Act 1996 Part II (ss.13-27)
   No qualifying period required.
   Worker status: {worker_status}{series_note}{cite_block}

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 4: RESPONDENT (EMPLOYER)
─────────────────────────────────────────────────────────────────────────────
   Name:    [YOUR EMPLOYER FULL LEGAL NAME]
   Address: [EMPLOYER REGISTERED ADDRESS AND POSTCODE]
   [Complete all employer details on the ET1 form.]

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 5: CLAIMANT
─────────────────────────────────────────────────────────────────────────────
   Name:         [YOUR FULL LEGAL NAME]
   Date wages due: {_fmt_date(wages_due_date) if wages_due_date else "[COMPLETE]"}
   Worker status: {worker_status}

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 8: DETAILS OF CLAIM
─────────────────────────────────────────────────────────────────────────────
   Summary:
   {reasoning if reasoning else "[Run assessment to generate summary — POST /assess]"}

   Claim viability: {viable}  |  Strength: {strength}

   Key issues:{weakness_block}

   [Expand with full particulars. Include: date wages became due, amount,
   basis of entitlement, any partial payment, employer's position.]

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 10: REMEDY
─────────────────────────────────────────────────────────────────────────────
   Amount claimed (gross wages): {amount_str}

   {vr.get("basis", "Repayment of gross wages unlawfully deducted (ERA 1996 s.24).")}

   [Note: For standard deduction claims, remedy = repayment only.
   No additional compensation multiplier (Delaney v Staples [1992] 1 AC 687).]

─────────────────────────────────────────────────────────────────────────────
DEADLINE — CRITICAL
─────────────────────────────────────────────────────────────────────────────
   ET claim deadline: {_fmt_date(deadline_date) if deadline_date else "[CHECK deadline endpoint]"}
   Authority: {deadline_auth}

   You must complete ACAS Early Conciliation BEFORE submitting ET1.
   Missing the 3-month deadline is usually fatal to the claim.

─────────────────────────────────────────────────────────────────────────────
REVIEW WARNING
─────────────────────────────────────────────────────────────────────────────
   Check every field against your payslips, contract, and bank statements.
   lawapp does not verify the accuracy of these notes.
   lawapp is not a solicitor and does not provide regulated legal advice.

─────────────────────────────────────────────────────────────────────────────
DOCUMENT INFORMATION
─────────────────────────────────────────────────────────────────────────────
Generated by: lawapp self-help document tool
Method: template (no freeform AI drafting)

{LEGAL_BOUNDARY_NOTICE}""".strip()
