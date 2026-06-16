"""
CLML (Crown Legislation Markup Language) XML parser.

CLML is the format served by legislation.gov.uk. It uses the namespace:
  http://www.legislation.gov.uk/namespaces/legislation

Key structures parsed:
  - PrimaryPrelims / SecondaryPrelims → act metadata
  - P1, P2, P3 → paragraph levels within a section
  - Text, Emphasis, Term → inline text
  - TableText → tables (extracted as plain text)

Returns a list of ParsedChunk objects ready for DB insertion.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from datetime import date

from lxml import etree

logger = logging.getLogger(__name__)

# CLML primary namespace
NS = "http://www.legislation.gov.uk/namespaces/legislation"
NSMAP = {"leg": NS}


def _tag(local: str) -> str:
    return f"{{{NS}}}{local}"


@dataclass
class ParsedChunk:
    act_title: str
    leg_type: str
    year: int
    chapter: str
    section_ref: str
    jurisdiction: str
    heading: Optional[str]
    body_text: str
    chunk_index: int
    source_url: str
    version_date: Optional[date]
    effective_from: Optional[date]
    effective_to: Optional[date]
    is_prospective: bool = False


def _extract_text(element: etree._Element) -> str:
    """Recursively extract all text content from an element, collapsing whitespace."""
    parts = []

    def _walk(el: etree._Element) -> None:
        if el.text:
            parts.append(el.text.strip())
        for child in el:
            _walk(child)
            if child.tail:
                parts.append(child.tail.strip())

    _walk(element)
    text = " ".join(p for p in parts if p)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str[:10])
    except ValueError:
        return None


def _extract_metadata(root: etree._Element) -> dict:
    """Extract act-level metadata from the document root."""
    meta = {
        "act_title": "",
        "year": None,
        "chapter": None,
        "jurisdiction": "EW",
        "effective_from": None,
        "effective_to": None,
        "version_date": None,
        "is_prospective": False,
    }

    # Title
    for tag in ["Title", "ShortTitle"]:
        el = root.find(f".//{_tag(tag)}")
        if el is not None and el.text:
            meta["act_title"] = el.text.strip()
            break

    # Year
    year_el = root.find(f".//{_tag('Year')}")
    if year_el is not None and year_el.text:
        try:
            meta["year"] = int(year_el.text.strip())
        except ValueError:
            pass

    # Chapter
    num_el = root.find(f".//{_tag('Number')}")
    if num_el is not None and num_el.text:
        meta["chapter"] = num_el.text.strip()

    # Jurisdiction  -  look for Extent element
    extent_el = root.find(f".//{_tag('Extent')}")
    if extent_el is not None and extent_el.text:
        extent_text = extent_el.text.strip()
        if "Scotland" in extent_text and "England" not in extent_text:
            meta["jurisdiction"] = "S"
        elif "Northern Ireland" in extent_text and "Great Britain" not in extent_text:
            meta["jurisdiction"] = "NI"
        else:
            meta["jurisdiction"] = "EW"  # England & Wales (and usually Scotland for GB Acts)

    # Version / effective dates from the document attributes or ukm:DocumentMainType
    start_el = root.find(f".//{_tag('DocumentMainType')}")
    if start_el is not None:
        meta["effective_from"] = _parse_date(start_el.get("StartDate"))
        meta["effective_to"] = _parse_date(start_el.get("EndDate"))

    return meta


def parse_section_xml(
    xml_bytes: bytes,
    source_url: str,
    leg_type: str,
    is_prospective: bool = False,
    chunk_size_chars: int = 3000,
    overlap_chars: int = 200,
) -> list[ParsedChunk]:
    """
    Parse a CLML section XML response into one or more ParsedChunks.

    A single section rarely exceeds 3000 chars; chunking handles long sections
    (e.g. schedules). chunk_size_chars is a soft limit  -  splits at paragraph
    boundaries where possible.
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        logger.error("CLML parse error for %s: %s", source_url, exc)
        return []

    meta = _extract_metadata(root)

    # Find the section number and heading
    section_ref = None
    heading = None

    pnum_el = root.find(f".//{_tag('Pnumber')}")
    if pnum_el is not None:
        section_ref = _extract_text(pnum_el)

    head_el = root.find(f".//{_tag('Title')}")
    if head_el is not None:
        heading = _extract_text(head_el)

    # Extract paragraph-level text blocks
    paragraphs: list[str] = []
    for para_el in root.iter(_tag("P1"), _tag("P2"), _tag("P3"), _tag("Text")):
        text = _extract_text(para_el)
        if text and len(text) > 20:  # skip trivial fragments
            paragraphs.append(text)

    if not paragraphs:
        # Fallback: extract all text from the document
        full_text = _extract_text(root)
        if full_text:
            paragraphs = [full_text]

    full_body = "\n\n".join(paragraphs)

    if not full_body.strip():
        logger.warning("No text extracted from %s", source_url)
        return []

    # Chunk at paragraph boundaries
    chunks = _chunk_paragraphs(paragraphs, chunk_size_chars, overlap_chars)

    result = []
    for idx, chunk_text in enumerate(chunks):
        result.append(ParsedChunk(
            act_title=meta["act_title"],
            leg_type=leg_type,
            year=meta["year"] or 0,
            chapter=meta["chapter"] or "",
            section_ref=section_ref or "",
            jurisdiction=meta["jurisdiction"],
            heading=heading,
            body_text=chunk_text,
            chunk_index=idx,
            source_url=source_url,
            version_date=meta.get("version_date"),
            effective_from=meta.get("effective_from"),
            effective_to=meta.get("effective_to"),
            is_prospective=is_prospective,
        ))

    return result


def _chunk_paragraphs(
    paragraphs: list[str], max_chars: int, overlap_chars: int
) -> list[str]:
    """Split paragraphs into chunks respecting the character limit."""
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > max_chars and current_parts:
            chunks.append("\n\n".join(current_parts))
            # Overlap: carry the last paragraph into the next chunk
            last = current_parts[-1] if current_parts else ""
            current_parts = [last] if last else []
            current_len = len(last)
        current_parts.append(para)
        current_len += len(para)

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks or [""]
