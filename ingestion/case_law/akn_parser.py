"""
Akoma Ntoso / LegalDocML XML parser for Find Case Law documents.

Namespace: http://docs.oasis-open.org/legaldocml/ns/akn/3.0
Proprietary TNA extensions: https://caselaw.nationalarchives.gov.uk/terms

Extracts:
  - document_uri, neutral_citation, fclid
  - case_name, court_code, decision_date
  - judges, parties
  - body text (chunked)
  - content_hash (from <uk:hash>)
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from lxml import etree

logger = logging.getLogger(__name__)

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
# Confirmed from live XML: xmlns:uk="https://caselaw.nationalarchives.gov.uk/akn"
# (NOT /terms  -  that was wrong and caused all uk: elements to return None)
UK_NS  = "https://caselaw.nationalarchives.gov.uk/akn"

NSMAP = {"akn": AKN_NS, "uk": UK_NS}


def _tag(local: str, ns: str = AKN_NS) -> str:
    return f"{{{ns}}}{local}"


@dataclass
class ParsedCase:
    document_uri: str
    xml_slug: str
    neutral_citation: Optional[str]
    fclid: Optional[str]
    case_name: Optional[str]
    court_code: str
    decision_date: Optional[date]
    judges: list[str]
    parties: list[str]
    chunks: list[str]              # body text split into chunks
    content_hash: str
    source_url: str
    published_date: Optional[date]
    updated_date: Optional[str]


def _extract_text(element: Optional[etree._Element]) -> str:
    if element is None:
        return ""
    parts = []

    def _walk(el: etree._Element) -> None:
        if el.text:
            parts.append(el.text)
        for child in el:
            _walk(child)
            if child.tail:
                parts.append(child.tail)

    _walk(element)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def parse_judgment_xml(
    xml_bytes: bytes,
    document_uri: str,
    xml_slug: str,
    source_url: str,
    chunk_size_chars: int = 3000,
    overlap_chars: int = 200,
) -> Optional[ParsedCase]:
    """
    Parse an Akoma Ntoso judgment XML and return a ParsedCase.
    Returns None if the XML is malformed or contains no usable content.
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        logger.error("AKN parse error for %s: %s", document_uri, exc)
        return None

    # Strip namespace for easier traversal
    judgment_el = root.find(f".//{_tag('judgment')}")
    if judgment_el is None:
        # Older format may have <doc> instead
        judgment_el = root.find(f".//{_tag('doc')}")
    if judgment_el is None:
        judgment_el = root  # fall back to root

    meta_el = judgment_el.find(f".//{_tag('meta')}")

    # ── Identifiers ──────────────────────────────────────────────────────────

    neutral_citation: Optional[str] = None
    fclid: Optional[str] = None
    content_hash: str = ""
    case_name: Optional[str] = None
    court_code: str = "eat"  # default; override from metadata if found
    decision_date: Optional[date] = None
    published_date: Optional[date] = None
    updated_date: Optional[str] = None

    judges: list[str] = []
    parties: list[str] = []

    if meta_el is not None:
        # ── Neutral citation ─────────────────────────────────────────────────
        # Primary: <uk:cite> in <proprietary> (uk: = UK_NS confirmed from live XML)
        cite_el = meta_el.find(f".//{_tag('cite', UK_NS)}")
        if cite_el is not None:
            neutral_citation = (cite_el.text or "").strip() or None
        if not neutral_citation:
            # Fallback: <neutralCitation> anywhere in document (AKN default NS)
            nc_el = root.find(f".//{_tag('neutralCitation')}")
            if nc_el is not None:
                neutral_citation = _extract_text(nc_el) or None

        # ── Content hash ─────────────────────────────────────────────────────
        hash_el = meta_el.find(f".//{_tag('hash', UK_NS)}")
        if hash_el is not None:
            content_hash = (hash_el.text or "").strip()

        # ── Case name ────────────────────────────────────────────────────────
        # <FRBRname value="H Rogers v Secretary of State for Justice"/> in FRBRWork
        frbrwork_el = meta_el.find(f".//{_tag('FRBRWork')}")
        if frbrwork_el is not None:
            name_el = frbrwork_el.find(f"{_tag('FRBRname')}")
            if name_el is not None:
                case_name = name_el.get("value", "").strip() or None

        # ── Court code ───────────────────────────────────────────────────────
        # Primary: <uk:court>EAT</uk:court> in <proprietary>
        court_el = meta_el.find(f".//{_tag('court', UK_NS)}")
        if court_el is not None and court_el.text:
            court_code = court_el.text.strip().lower()
        else:
            # Fallback: derive from FRBRExpression URI slug
            for uri_el in meta_el.findall(f".//{_tag('FRBRuri')}"):
                val = uri_el.get("value", "")
                path = val.split("nationalarchives.gov.uk")[-1].strip("/")
                parts = [p for p in path.split("/") if p not in ("id", "")]
                if parts:
                    court_code = parts[0]
                    break

        # ── FCLID ────────────────────────────────────────────────────────────
        for id_el in meta_el.findall(f".//{_tag('FRBRthis')}"):
            val = id_el.get("value", "")
            if val:
                fclid = val.rstrip("/").split("/")[-1]
                break

        # ── Decision date ────────────────────────────────────────────────────
        for date_el in meta_el.findall(f".//{_tag('FRBRdate')}"):
            if date_el.get("name", "") in ("judgment", "decision"):
                decision_date = _parse_date(date_el.get("date", ""))
                break

        # ── Judges and parties ───────────────────────────────────────────────
        # <TLCPerson eId="judge-..." showAs="JUDGE NAME"/> in <references>
        refs_el = meta_el.find(f".//{_tag('references')}")
        if refs_el is not None:
            _skip_eids = {"tna", "eat", "hmcts", "uksc", "ewca", "ewhc"}
            for person_el in refs_el.findall(f"{_tag('TLCPerson')}"):
                eid = person_el.get("eId", "")
                show_as = person_el.get("showAs", "").strip()
                if not show_as or eid in _skip_eids:
                    continue
                if eid.startswith("judge"):
                    judges.append(show_as)
                else:
                    parties.append(show_as)

    # ── Body text ────────────────────────────────────────────────────────────

    body_el = judgment_el.find(f".//{_tag('body')}")
    if body_el is None:
        body_el = judgment_el  # older format

    paragraphs: list[str] = []
    for para_el in body_el.iter(_tag("p"), _tag("paragraph"), _tag("content")):
        text = _extract_text(para_el)
        if text and len(text) > 30:
            paragraphs.append(text)

    if not paragraphs:
        full_text = _extract_text(body_el)
        if full_text:
            paragraphs = [full_text]

    if not paragraphs:
        logger.warning("No body text in %s", document_uri)
        return None

    full_body = "\n\n".join(paragraphs)

    # Compute hash from body text if not in metadata
    if not content_hash:
        content_hash = "sha256:" + hashlib.sha256(full_body.encode()).hexdigest()

    chunks = _chunk_paragraphs(paragraphs, chunk_size_chars, overlap_chars)

    return ParsedCase(
        document_uri=document_uri,
        xml_slug=xml_slug,
        neutral_citation=neutral_citation,
        fclid=fclid,
        case_name=case_name,
        court_code=court_code,
        decision_date=decision_date,
        judges=judges,
        parties=parties,
        chunks=chunks,
        content_hash=content_hash,
        source_url=source_url,
        published_date=published_date,
        updated_date=updated_date,
    )


def _chunk_paragraphs(paragraphs: list[str], max_chars: int, overlap_chars: int) -> list[str]:
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > max_chars and current:
            chunks.append("\n\n".join(current))
            last = current[-1] if current else ""
            current = [last] if last else []
            current_len = len(last)
        current.append(para)
        current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return chunks or [""]
