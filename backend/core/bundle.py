"""
Premium tribunal bundle generation  -  Phase 4B.

Generates four structured components:
  1. Witness statement structure
  2. Chronology of events
  3. Evidence checklist
  4. ET1 support notes

GUARDRAILS:
  - Only user_confirmed or user_corrected extracted facts are used.
  - extracted_unconfirmed and rejected facts are never included.
  - Placeholder values ("[Extracted from...") are excluded automatically.
  - Missing dates are flagged  -  never invented.
  - Every component includes the legal boundary notice verbatim.
  - No LLM involvement. Template generation only.
  - "we will file", "we will submit", "we will represent", "guaranteed" are
    blocked by safety_check before any component is returned.
  - Platform does not file, submit, or represent users in tribunal.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Legal boundary notice (bundle-specific) ────────────────────────────────────

BUNDLE_BOUNDARY_NOTICE = """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT  -  READ BEFORE USE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This document is a SELF-HELP DRAFT prepared using lawapp.
It is NOT legal advice. lawapp is not a solicitor or law firm.
This draft is based on information you provided and extracted facts
you have confirmed. It may be incomplete, inaccurate, or unsuitable.
You must review, verify, and correct every section before filing
or sending it to any party.
lawapp does not file, submit, represent you, or conduct litigation.
No outcome is guaranteed.
If you are unsure, seek advice from a qualified solicitor.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

# ── Confirmed-facts extraction ─────────────────────────────────────────────────

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _fmt(s: Optional[str]) -> str:
    """Format YYYY-MM-DD as '1 April 2026'. Return '[DATE NOT PROVIDED]' if None."""
    if not s:
        return "[DATE NOT PROVIDED]"
    try:
        from datetime import date
        d = date.fromisoformat(s)
        return f"{d.day} {_MONTH_NAMES[d.month - 1]} {d.year}"
    except (ValueError, IndexError):
        return s


def _val(d: dict, key: str, default: str = "[NOT PROVIDED]") -> str:
    return str(d.get(key) or default)


def get_confirmed_facts(uploads: list[dict]) -> dict:
    """
    Collect confirmed and corrected extracted facts from all uploads.

    Rules:
      - status must be 'user_confirmed' or 'user_corrected'
      - value must not start with '[Extracted' (placeholder  -  skip)
      - Later uploads override earlier ones for the same field
    """
    result: dict[str, str] = {}
    for upload in uploads:
        for field, fact in (upload.get("extracted_facts") or {}).items():
            if fact.get("status") not in ("user_confirmed", "user_corrected"):
                continue
            value = fact.get("value", "")
            if not value or str(value).startswith("[Extracted"):
                continue  # skip placeholder values
            result[field] = str(value)
    return result


def collect_warnings(assessment: dict, key_dates: dict, confirmed: dict) -> list[str]:
    """Return a list of warnings about missing data that the user should address."""
    warnings: list[str] = []
    if not key_dates.get("edt"):
        warnings.append("EDT (dismissal date) not recorded  -  essential for all bundle documents.")
    if not key_dates.get("deadline_date"):
        warnings.append("Tribunal deadline not stored  -  check /cases/{id}/deadline.")
    if not assessment.get("reasoning_summary"):
        warnings.append("Assessment summary missing  -  run /assess first.")
    if not confirmed.get("edt_candidate") and not key_dates.get("edt"):
        warnings.append("No confirmed dismissal date from uploaded documents.")
    return warnings


# ── 1. Witness Statement ───────────────────────────────────────────────────────

def generate_witness_statement(
    assessment: dict,
    key_dates: dict,
    confirmed: dict,
    uploads: list[dict],
) -> str:
    edt           = key_dates.get("edt") or confirmed.get("edt_candidate")
    start_date    = key_dates.get("employment_start_date") or confirmed.get("employment_start_date")
    employer      = confirmed.get("employer_name", "[YOUR EMPLOYER  -  add before filing]")
    employee      = confirmed.get("employee_name", "[YOUR FULL NAME  -  add before filing]")
    reason        = confirmed.get("dismissal_reason") or assessment.get("reason_for_dismissal", "")
    procedure_ok  = assessment.get("was_procedure_followed")
    weaknesses    = assessment.get("key_weaknesses") or []
    reasoning     = (assessment.get("reasoning_summary") or "").strip()
    vr            = assessment.get("value_range") or {}
    procedure_concerns = confirmed.get("key_procedure_concerns", "")

    procedure_para = ""
    if procedure_ok is False:
        procedure_para = (
            "   The Respondent did not follow a proper disciplinary procedure "
            "before dismissing me. No proper warning or opportunity to respond was given."
        )
    elif procedure_ok is True:
        procedure_para = (
            "   The Respondent followed a formal procedure, but I contend the "
            "dismissal was nonetheless unfair for the reasons set out below."
        )
    else:
        procedure_para = (
            "   I am not fully aware of the procedure the Respondent followed "
            "and reserve the right to particularise further upon disclosure."
        )

    if procedure_concerns:
        procedure_para += f"\n   {procedure_concerns}"

    weakness_block = ""
    if weaknesses:
        weakness_block = "\n" + "\n".join(f"   • {w}" for w in weaknesses)

    upload_list = ""
    if uploads:
        lines = []
        for u in uploads:
            lines.append(f"   • {u.get('doc_type','document').replace('_',' ').title()}: {u.get('original_filename','[unnamed]')}")
        upload_list = "\n" + "\n".join(lines)
    else:
        upload_list = "\n   No documents uploaded yet."

    vr_text = ""
    if vr:
        vr_text = (
            f"\n   My estimated losses range from £{vr.get('low',0):,.0f} to £{vr.get('high',0):,.0f}. "
            f"Basis: {vr.get('basis','from statutory rules')}. "
            "Actual compensation is for the tribunal to determine."
        )

    return f"""\
{BUNDLE_BOUNDARY_NOTICE}

─────────────────────────────────────────────────────────────────────────────
WITNESS STATEMENT  -  SELF-HELP DRAFT
─────────────────────────────────────────────────────────────────────────────
IN THE EMPLOYMENT TRIBUNAL

Claimant:   {employee}
Respondent: {employer}

I, {employee}, will say as follows:

─────────────────────────────────────────────────────────────────────────────
1. BACKGROUND
─────────────────────────────────────────────────────────────────────────────
   I was employed by {employer}{"from " + _fmt(start_date) if start_date else ""} until
   {_fmt(edt)} (my effective date of termination).

   [Add further background  -  role, department, duties  -  before filing.]

─────────────────────────────────────────────────────────────────────────────
2. EMPLOYMENT HISTORY
─────────────────────────────────────────────────────────────────────────────
   Employment start:   {_fmt(start_date)}
   Dismissal (EDT):    {_fmt(edt)}
   Reason given:       {reason if reason else "[ADD REASON GIVEN FOR DISMISSAL]"}

   [Expand with job title, reporting line, and contract terms before filing.]

─────────────────────────────────────────────────────────────────────────────
3. DISMISSAL TIMELINE
─────────────────────────────────────────────────────────────────────────────
   [Complete with specific dates and details before filing.]

   {_fmt(edt)}  -  Employment terminated (EDT).
   [Add any prior warnings, meetings, or correspondence here.]

─────────────────────────────────────────────────────────────────────────────
4. WHAT HAPPENED
─────────────────────────────────────────────────────────────────────────────
   Assessment summary:
   {reasoning if reasoning else "[Run assessment to populate this section.]"}

   [Expand in your own words. The witness statement must be in the first
   person and describe what you personally observed or experienced.]

─────────────────────────────────────────────────────────────────────────────
5. PROCEDURE CONCERNS
─────────────────────────────────────────────────────────────────────────────
{procedure_para}{weakness_block}

─────────────────────────────────────────────────────────────────────────────
6. IMPACT AND FINANCIAL LOSS
─────────────────────────────────────────────────────────────────────────────{vr_text}

   [Complete this section with actual losses since dismissal. Include:
   • Immediate loss of earnings
   • Future loss (if not yet re-employed)
   • Steps taken to mitigate (job applications, etc.)
   • Other financial impact]

─────────────────────────────────────────────────────────────────────────────
7. DOCUMENTS AND EVIDENCE
─────────────────────────────────────────────────────────────────────────────
   Uploaded documents associated with this case:{upload_list}

   [Reference documents by exhibit number (e.g. "Exhibit A  -  dismissal letter").]

─────────────────────────────────────────────────────────────────────────────
STATEMENT OF TRUTH
─────────────────────────────────────────────────────────────────────────────
I believe that the facts stated in this witness statement are true.
I understand that proceedings for contempt of court may be brought
against anyone who makes, or causes to be made, a false statement
in a document verified by a statement of truth.

Signed: ___________________________     Date: ____________________
Name (print): _____________________

─────────────────────────────────────────────────────────────────────────────
DOCUMENT INFORMATION
─────────────────────────────────────────────────────────────────────────────
Generated by: lawapp premium bundle tool
Method: template (no freeform AI drafting)

{BUNDLE_BOUNDARY_NOTICE}""".strip()


# ── 2. Chronology ──────────────────────────────────────────────────────────────

def generate_chronology(
    assessment: dict,
    key_dates: dict,
    confirmed: dict,
) -> str:
    edt        = key_dates.get("edt")
    start_date = key_dates.get("employment_start_date") or confirmed.get("employment_start_date")
    deadline   = key_dates.get("deadline_date")
    day_a      = key_dates.get("ec_day_a") or confirmed.get("edt_candidate")
    day_b      = key_dates.get("ec_day_b")

    # Build event list  -  never invent missing dates
    events: list[tuple[str, str, str]] = []

    if start_date:
        events.append((start_date, "Employment commenced", "case record"))
    else:
        events.append(("[DATE NOT CONFIRMED]", "Employment commenced", "not confirmed  -  do not invent"))

    if edt:
        events.append((edt, "Employment terminated  -  effective date of termination (EDT)", "case record"))
    else:
        events.append(("[DATE NOT CONFIRMED]", "Dismissal  -  EDT", "not confirmed  -  do not invent"))

    if key_dates.get("ec_day_a"):
        events.append((key_dates["ec_day_a"], "ACAS Early Conciliation started (Day A)", "case record"))
    if key_dates.get("ec_day_b"):
        events.append((key_dates["ec_day_b"], "ACAS EC certificate received (Day B)", "case record"))
    elif key_dates.get("ec_day_a") and not key_dates.get("ec_day_b"):
        events.append(("[PENDING]", "ACAS EC certificate (Day B)  -  not yet received", "pending"))

    if deadline:
        events.append((deadline, "ET claim limitation date (from rules  -  ERA 1996 s.111(2))", "rules-derived"))

    # Sort by date (ISO sort; non-dates sort to top/bottom)
    def sort_key(e):
        try:
            from datetime import date
            return date.fromisoformat(e[0]).isoformat()
        except (ValueError, AttributeError):
            return "0000-00-00"

    dated   = [(d, ev, src) for d, ev, src in events if not d.startswith("[")]
    undated = [(d, ev, src) for d, ev, src in events if d.startswith("[")]
    dated.sort(key=sort_key)
    events = dated + undated

    # Format table
    header = f"{'Date':<22} {'Event':<55} Source"
    rule   = "─" * 22 + " " + "─" * 55 + " " + "─" * 20
    rows   = []
    for d, ev, src in events:
        display_d = _fmt(d) if not d.startswith("[") else d
        rows.append(f"{display_d:<22} {ev:<55} {src}")

    # Missing confirmed dates warning
    missing = []
    if not start_date:
        missing.append("Employment start date  -  not confirmed from uploads or intake")
    if not edt:
        missing.append("EDT (dismissal date)  -  not confirmed")
    if missing:
        missing_block = "\nMissing dates (do not invent):\n" + "\n".join(f"  • {m}" for m in missing)
    else:
        missing_block = "\nAll key dates are recorded."

    return f"""\
{BUNDLE_BOUNDARY_NOTICE}

─────────────────────────────────────────────────────────────────────────────
CHRONOLOGY OF EVENTS  -  SELF-HELP DRAFT
─────────────────────────────────────────────────────────────────────────────
Claim type: Unfair Dismissal (ERA 1996 Part X)

IMPORTANT: Dates shown as [DATE NOT CONFIRMED] have not been confirmed from
uploaded documents or your intake form. Do NOT invent or estimate dates.
Add only dates you can verify from documents in your possession.

{header}
{rule}
{chr(10).join(rows)}
{missing_block}

[Add further events  -  e.g. disciplinary invite date, outcome date,
appeal date  -  with corresponding document references before filing.]

─────────────────────────────────────────────────────────────────────────────
DOCUMENT INFORMATION
─────────────────────────────────────────────────────────────────────────────
Generated by: lawapp premium bundle tool
Method: template (no freeform AI drafting)

{BUNDLE_BOUNDARY_NOTICE}""".strip()


# ── 3. Evidence Checklist ──────────────────────────────────────────────────────

def generate_evidence_checklist(
    assessment: dict,
    key_dates: dict,
    confirmed: dict,
    uploads: list[dict],
) -> str:
    upload_lines = ""
    if uploads:
        lines = []
        for u in uploads:
            status = u.get("extraction_status", "pending")
            lines.append(
                f"  [✓] {u.get('doc_type','').replace('_',' ').title()} "
                f" -  {u.get('original_filename','[unnamed]')} (extraction: {status})"
            )
        upload_lines = "\n".join(lines)
    else:
        upload_lines = "  [ ] No documents uploaded yet."

    return f"""\
{BUNDLE_BOUNDARY_NOTICE}

─────────────────────────────────────────────────────────────────────────────
EVIDENCE CHECKLIST  -  SELF-HELP DRAFT
─────────────────────────────────────────────────────────────────────────────
Claim type: Unfair Dismissal (ERA 1996 Part X)

This is a preparation checklist  -  not all items are required.
Gather what is available and relevant to your circumstances.

─────────────────────────────────────────────────────────────────────────────
CORE EMPLOYMENT DOCUMENTS
─────────────────────────────────────────────────────────────────────────────
  [ ] Employment contract (or written statement of particulars)
  [ ] Latest job description
  [ ] Recent payslips (last 3 months recommended)
  [ ] P60 (most recent year)

─────────────────────────────────────────────────────────────────────────────
DISMISSAL AND DISCIPLINARY DOCUMENTS
─────────────────────────────────────────────────────────────────────────────
  [ ] Dismissal letter
  [ ] Disciplinary invite letter(s)
  [ ] Disciplinary outcome letter(s)
  [ ] Appeal invite letter (if appeal was offered)
  [ ] Appeal outcome letter (if appeal taken)
  [ ] Any written warnings issued prior to dismissal
  [ ] Grievance letters (if any grievance was raised)

─────────────────────────────────────────────────────────────────────────────
COMMUNICATIONS
─────────────────────────────────────────────────────────────────────────────
  [ ] Relevant emails (disciplinary / dismissal / HR communications)
  [ ] Text messages or messaging app records (if relevant)
  [ ] Meeting notes or records

─────────────────────────────────────────────────────────────────────────────
ACAS EARLY CONCILIATION
─────────────────────────────────────────────────────────────────────────────
  [ ] ACAS Early Conciliation certificate (Day B document)
  [ ] ACAS correspondence

─────────────────────────────────────────────────────────────────────────────
WITNESSES
─────────────────────────────────────────────────────────────────────────────
  [ ] Names and contact details of potential witnesses
  [ ] Any written witness accounts (in your possession)

─────────────────────────────────────────────────────────────────────────────
MEDICAL / DISABILITY (ONLY IF RELEVANT TO YOUR CLAIM)
─────────────────────────────────────────────────────────────────────────────
  [ ] Medical evidence  -  only include if disability/health is directly
      relevant to the reason for dismissal or protected characteristics.
      Seek advice before including sensitive medical records.

─────────────────────────────────────────────────────────────────────────────
UPLOADED DOCUMENTS (ALREADY IN YOUR CASE)
─────────────────────────────────────────────────────────────────────────────
{upload_lines}

─────────────────────────────────────────────────────────────────────────────
DOCUMENT INFORMATION
─────────────────────────────────────────────────────────────────────────────
Generated by: lawapp premium bundle tool
Method: template (no freeform AI drafting)

{BUNDLE_BOUNDARY_NOTICE}""".strip()


# ── 4. ET1 Support Notes ───────────────────────────────────────────────────────

def generate_et1_support_notes(
    assessment: dict,
    key_dates: dict,
    confirmed: dict,
) -> str:
    edt         = key_dates.get("edt")
    start_date  = key_dates.get("employment_start_date") or confirmed.get("employment_start_date")
    deadline    = key_dates.get("deadline_date")
    employer    = confirmed.get("employer_name", "[YOUR EMPLOYER  -  required on ET1]")
    employee    = confirmed.get("employee_name", "[YOUR FULL NAME  -  required on ET1]")
    reasoning   = (assessment.get("reasoning_summary") or "").strip()
    vr          = assessment.get("value_range") or {}
    dl_auth     = (assessment.get("deadline_info") or {}).get("authority", "ERA 1996 s.111(2)")
    has_viable  = assessment.get("has_viable_claim", "uncertain")
    strength    = assessment.get("strength", "uncertain")
    weaknesses  = assessment.get("key_weaknesses") or []
    citations   = assessment.get("citations") or []

    vr_text = ""
    if vr:
        vr_text = (
            f"Estimated range: £{vr.get('low',0):,.0f} – £{vr.get('high',0):,.0f}. "
            f"Basis: {vr.get('basis','from statutory rules')}."
        )

    weakness_block = ""
    if weaknesses:
        weakness_block = "\n" + "\n".join(f"   • {w}" for w in weaknesses[:4])

    citation_block = ""
    if citations:
        citation_block = "\n   Authorities: " + "; ".join(
            c.get("cite", "") for c in citations[:4]
        )

    return f"""\
{BUNDLE_BOUNDARY_NOTICE}

─────────────────────────────────────────────────────────────────────────────
ET1 SUPPORT NOTES  -  SELF-HELP DRAFT
─────────────────────────────────────────────────────────────────────────────

⚠ IMPORTANT  -  READ CAREFULLY
These are support notes to help you complete ET1 sections.
lawapp does NOT file, submit, or send your ET1.
You must complete and submit the ET1 yourself, or instruct a solicitor.
No outcome is guaranteed.
Not legal advice.

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 3: TYPE OF CLAIM
─────────────────────────────────────────────────────────────────────────────
   Claim type:  Unfair Dismissal
   Statute:     Employment Rights Act 1996 Part X
{citation_block}

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 4: EMPLOYER DETAILS
─────────────────────────────────────────────────────────────────────────────
   Respondent name: {employer}
   [Complete full address, postcode, phone, and sector on the ET1 form.]

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 5: CLAIMANT DETAILS
─────────────────────────────────────────────────────────────────────────────
   Claimant: {employee}
   Employment start: {_fmt(start_date)}
   EDT:              {_fmt(edt)}

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 8: DETAILS OF CLAIM (PARTICULARS)
─────────────────────────────────────────────────────────────────────────────
   Summary for particulars section:
   {reasoning if reasoning else "[Run assessment to generate summary.]"}

   Claim viability: {has_viable}  |  Strength: {strength}

   Key issues:{weakness_block}

   [Expand with your full particulars. See your drafted Particulars of Claim
   document for the full version. Attach as a separate document if needed.]

─────────────────────────────────────────────────────────────────────────────
ET1 SECTION 10: REMEDY
─────────────────────────────────────────────────────────────────────────────
   Remedy sought: Reinstatement/re-engagement or compensation.
   {vr_text}

   [Complete the remedy section on ET1 with actual figures from your
   Schedule of Loss. Do not leave blank.]

─────────────────────────────────────────────────────────────────────────────
DEADLINE  -  CRITICAL
─────────────────────────────────────────────────────────────────────────────
   Your ET claim deadline: {_fmt(deadline)}
   Authority: {dl_auth}

   ⚠ You must complete ACAS Early Conciliation BEFORE submitting ET1.
   Missing the deadline is usually fatal to an unfair dismissal claim.
   Seek urgent advice if the deadline has passed or is imminent.

─────────────────────────────────────────────────────────────────────────────
REVIEW WARNING
─────────────────────────────────────────────────────────────────────────────
   These notes are a self-help aid only.
   Check every field against your actual documents before submitting ET1.
   lawapp does not verify the accuracy of these notes.
   lawapp is not a solicitor and does not provide regulated legal advice.

─────────────────────────────────────────────────────────────────────────────
DOCUMENT INFORMATION
─────────────────────────────────────────────────────────────────────────────
Generated by: lawapp premium bundle tool
Method: template (no freeform AI drafting)

{BUNDLE_BOUNDARY_NOTICE}""".strip()


# ── Full bundle orchestration ──────────────────────────────────────────────────

BUNDLE_COMPONENTS = (
    "witness_statement",
    "chronology",
    "evidence_checklist",
    "et1_support_notes",
)


def generate_full_bundle(
    assessment: dict,
    key_dates: dict,
    confirmed: dict,
    uploads: list[dict],
) -> dict[str, str]:
    """
    Generate all four bundle components.
    Returns {component_name: content_string}.
    """
    return {
        "witness_statement":  generate_witness_statement(assessment, key_dates, confirmed, uploads),
        "chronology":         generate_chronology(assessment, key_dates, confirmed),
        "evidence_checklist": generate_evidence_checklist(assessment, key_dates, confirmed, uploads),
        "et1_support_notes":  generate_et1_support_notes(assessment, key_dates, confirmed),
    }
