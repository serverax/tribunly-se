"""
Real Document Extraction Engine — Brain Step 11 (Document Intelligence).

Extracts structured facts from uploaded documents.
Supports: PDF (text-based), DOCX, plain text.
OCR for scanned PDFs requires tesseract (noted as external dependency).

GUARDRAIL: Raw document content is NEVER sent to a third-party LLM.
           All extraction is local: text parsing, regex, heuristics.
GUARDRAIL: All extracted facts start as status='unconfirmed'.
           No extracted fact affects the case until the user confirms it.
GUARDRAIL: Extracted text is never logged in its entirety (PII risk).
"""

from __future__ import annotations

import io
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pypdf as PyPDF2  # type: ignore
except Exception:  # pragma: no cover - optional dependency patch point
    PyPDF2 = None  # type: ignore


# ── Date patterns ─────────────────────────────────────────────────────────────

_DATE_PATTERNS = [
    # ISO: 2025-10-01
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),
    # UK: 1 October 2025, 01/10/2025, 01-10-2025
    re.compile(
        r"\b(\d{1,2})[/ -](January|February|March|April|May|June|July|August|"
        r"September|October|November|December)[/ -](\d{4})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(\d{1,2})[/ -](\d{1,2})[/ -](\d{4})\b"),
]

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _normalise_date(raw: str) -> Optional[str]:
    """Try to convert a raw date string to YYYY-MM-DD. Returns None on failure."""
    raw = raw.strip()
    for pattern in _DATE_PATTERNS:
        m = pattern.search(raw)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 3:
                    if any(g.lower() in _MONTH_MAP for g in groups):
                        day   = groups[0].zfill(2)
                        month = _MONTH_MAP.get(groups[1].lower(), "??")
                        year  = groups[2]
                    elif len(groups[2]) == 4:
                        day, month, year = groups[0].zfill(2), groups[1].zfill(2), groups[2]
                    else:
                        year, month, day = groups[0], groups[1].zfill(2), groups[2].zfill(2)
                    return f"{year}-{month}-{day}"
            except Exception:
                continue
    return None


# ── Field extractors ──────────────────────────────────────────────────────────

def _extract_dismissal_date(text: str) -> Optional[str]:
    """Look for dismissal / termination date in text."""
    patterns = [
        r"(?:effective date of termination|edt|date of dismissal|dismissed on|termination date)[:\s]+([^\n,]{6,30})",
        r"(?:your employment (?:is|was) terminated)[^\n]*?(\d{1,2}[/ -][^\n]{4,20}\d{4})",
        r"(?:with effect from)[:\s]+([^\n,]{6,30})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return _normalise_date(m.group(1).strip())
    return None


def _extract_reason(text: str) -> Optional[str]:
    """Extract reason for dismissal."""
    patterns = [
        r"(?:reason for (?:your )?dismissal|dismissed (?:for|due to|because of))[:\s]+([^\n.]{5,100})",
        r"(?:gross misconduct|redundancy|capability|performance|some other substantial reason)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            matched = m.group(0) if m.lastindex is None else m.group(1)
            return matched.strip()[:100]
    return None


def _extract_salary(text: str) -> Optional[str]:
    """Extract salary or weekly pay."""
    m = re.search(
        r"(?:salary|weekly pay|annual salary|gross pay)[:\s]+[£$]?([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE,
    )
    if m:
        return m.group(1).replace(",", "")
    return None


def _extract_employer(text: str) -> Optional[str]:
    """Extract employer name."""
    m = re.search(
        r"(?:from|by|employer)[:\s]+([A-Z][A-Za-z\s&.,()]{3,80}(?:Ltd|Limited|PLC|LLP|Co\.|Company)?)",
        text,
    )
    if m:
        return m.group(1).strip()[:80]
    return None


def _extract_appeal_deadline(text: str) -> Optional[str]:
    """Extract appeal deadline."""
    m = re.search(
        r"(?:appeal within|right to appeal)[^\n]{0,30}(\d+)[^\n]{0,20}(?:days?|working days?)",
        text, re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)} days from dismissal"
    return None


def _classify_document_type(text: str, filename: str = "") -> str:
    """Classify document type from content and filename."""
    fname_lower = filename.lower()
    text_lower  = text.lower()

    if any(k in fname_lower for k in ("dismissal", "termination", "p45")):
        return "dismissal_letter"
    if any(k in text_lower for k in ("notice of termination", "your employment is terminated",
                                      "effective date of termination")):
        return "dismissal_letter"
    if any(k in text_lower for k in ("employment contract", "contract of employment",
                                      "terms and conditions of employment")):
        return "employment_contract"
    if any(k in text_lower for k in ("payslip", "gross pay", "net pay", "national insurance")):
        return "payslip"
    if any(k in fname_lower for k in ("payslip", "salary", "wage")):
        return "payslip"
    if any(k in text_lower for k in ("grievance", "disciplinary", "investigation", "hearing")):
        return "disciplinary_letter"
    return "other"


# ── PDF extraction ────────────────────────────────────────────────────────────

def _extract_text_from_pdf(content: bytes) -> str:
    """
    Extract text from a PDF using pypdf (text-based PDFs only).
    For scanned/image PDFs, falls back to empty string.
    OCR requires external tesseract installation (documented separately).

    GUARDRAIL: Only text is extracted — no rendering, no JS execution.
    """
    try:
        if PyPDF2 is None:
            raise ImportError("pypdf unavailable")
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages[:20]:  # cap at 20 pages to limit PII exposure
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(pages)
    except ImportError:
        logger.warning("pypdf not installed. PDF text extraction unavailable. "
                       "Install: pip install pypdf")
        return ""
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return ""


def _extract_text_from_docx(content: bytes) -> str:
    """
    Extract text from a DOCX file using python-docx.

    GUARDRAIL: Only text is extracted — no macro execution.
    """
    try:
        import docx  # type: ignore
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(para.text for para in doc.paragraphs)
    except ImportError:
        logger.warning("python-docx not installed. DOCX extraction unavailable. "
                       "Install: pip install python-docx")
        return ""
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        return ""


# ── Main extraction entry point ───────────────────────────────────────────────

def extract_facts_from_document(
    content:        bytes,
    content_type:   str,
    filename:       str = "",
    doc_type_hint:  Optional[str] = None,
) -> dict:
    """
    Extract structured facts from an uploaded document.

    Args:
        content:       Raw file bytes
        content_type:  MIME type (application/pdf, application/vnd.openxmlformats...)
        filename:      Original filename (used for classification hint)
        doc_type_hint: Caller-provided document type hint

    Returns dict with:
      - "document_type": classified type
      - "extraction_method": "pdf_text" | "docx" | "plain_text" | "unavailable"
      - "text_length": int (chars extracted, not raw bytes)
      - "facts": list[dict] each with field, raw_value, normalised_value,
                 confidence, status="unconfirmed"
      - "warnings": list of extraction warnings

    GUARDRAIL: All facts have status="unconfirmed" — never auto-applied.
    GUARDRAIL: Raw extracted text is NOT stored in this response (PII protection).
    """
    warnings: list[str] = []
    extraction_method = "unavailable"
    text = ""

    # Extract text based on content type
    if "pdf" in content_type.lower():
        text = _extract_text_from_pdf(content)
        extraction_method = "pdf_text"
        if not text:
            warnings.append("PDF text extraction yielded empty result. File may be scanned/image-only. OCR not available.")
            extraction_method = "unavailable"

    elif "docx" in content_type.lower() or "wordprocessingml" in content_type.lower():
        text = _extract_text_from_docx(content)
        extraction_method = "docx"
        if not text:
            warnings.append("DOCX extraction yielded empty result.")

    elif "text/plain" in content_type.lower():
        try:
            text = content.decode("utf-8", errors="replace")
            extraction_method = "plain_text"
        except Exception as exc:
            warnings.append(f"Text decode failed: {exc}")

    else:
        warnings.append(f"Content type {content_type!r} not supported for text extraction.")

    # Classify document type
    doc_type = doc_type_hint or _classify_document_type(text, filename)

    # Extract fields
    raw_facts: dict[str, Optional[str]] = {}
    if text:
        raw_facts["dismissal_date"]    = _extract_dismissal_date(text)
        raw_facts["reason_for_dismissal"] = _extract_reason(text)
        raw_facts["employer_name"]     = _extract_employer(text)
        raw_facts["salary"]            = _extract_salary(text)
        raw_facts["appeal_deadline"]   = _extract_appeal_deadline(text)

    # Build structured facts list (all unconfirmed)
    facts = []
    for field_name, raw_value in raw_facts.items():
        if raw_value:
            facts.append({
                "field_name":       field_name,
                "raw_value":        raw_value,
                "normalised_value": raw_value,
                "confidence":       0.7 if raw_value else 0.0,
                "status":           "unconfirmed",  # GUARDRAIL: always unconfirmed
                "extraction_method": extraction_method,
            })

    return {
        "document_type":     doc_type,
        "extraction_method": extraction_method,
        "text_length":       len(text),
        "facts_count":       len(facts),
        "facts":             facts,
        "warnings":          warnings,
        "ocr_note": (
            "For scanned/image PDFs, install tesseract: "
            "apt-get install tesseract-ocr && pip install pytesseract"
        ) if extraction_method == "unavailable" else None,
    }


def extract_text_from_document(
    content:      bytes,
    content_type: str,
    filename:     str = "",
) -> tuple[Optional[str], Optional[str]]:
    """
    Extract plain text from a document for OCR.
    Returns: (extracted_text, document_type) or (None, None) if extraction fails.

    Supports PDF, DOCX, plain text, and images.
    For images and scanned PDFs: returns empty string and notes in warnings.
    """
    result = extract_facts_from_document(content, content_type, filename)

    if result.get("extraction_method") == "unavailable":
        # Extraction failed completely
        logger.warning("Document extraction unavailable: %s", result.get("warnings"))
        return None, result.get("document_type")

    # Return extracted text (reconstructed from context, not stored)
    # In this case, we just signal that extraction happened
    text_length = result.get("text_length", 0)
    doc_type = result.get("document_type")

    # For upload_routes, we need raw text, not just facts
    # So we re-extract it
    text = ""
    if "pdf" in content_type.lower():
        text = _extract_text_from_pdf(content)
    elif "docx" in content_type.lower() or "wordprocessingml" in content_type.lower():
        text = _extract_text_from_docx(content)
    elif "text/plain" in content_type.lower():
        try:
            text = content.decode("utf-8", errors="replace")
        except:
            pass

    if text:
        return text, doc_type
    return None, doc_type


def save_extracted_facts(
    upload_id:   str,
    case_id:     Optional[str],
    user_id:     Optional[str],
    facts:       list[dict],
) -> int:
    """
    Persist extracted facts to document_facts table.
    All records are inserted with status='unconfirmed'.

    Returns: number of facts saved.
    GUARDRAIL: Never overrides existing confirmed/rejected facts.
    """
    if not facts:
        return 0
    from ingestion.db import get_connection
    conn = get_connection()
    saved = 0
    try:
        with conn.cursor() as cur:
            for fact in facts:
                cur.execute(
                    """
                    INSERT INTO document_facts (
                        upload_id, case_id, user_id,
                        field_name, raw_value, normalised_value,
                        confidence, status, extraction_method
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        upload_id,
                        case_id,
                        user_id,
                        fact["field_name"],
                        fact["raw_value"],
                        fact.get("normalised_value", fact["raw_value"]),
                        fact.get("confidence", 0.7),
                        "unconfirmed",
                        fact.get("extraction_method", "pdf_text"),
                    ),
                )
                saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved
