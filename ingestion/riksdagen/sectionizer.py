"""Split consolidated SFS text into stable section-level chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


SECTION_RE = re.compile(r"(?m)^(?P<section>\d+\s*[a-z]?\s*§)\s*(?P<body>.*?)(?=^\d+\s*[a-z]?\s*§|\Z)", re.S)
TRANSITION_RE = re.compile(r"(?m)^Övergångsbestämmelser\s*$")


@dataclass(frozen=True)
class SectionChunk:
    section_ref: str
    heading: str
    text: str
    order: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _trim_to_main_body(text: str) -> str:
    match = TRANSITION_RE.search(text)
    if match:
        return text[: match.start()].rstrip()
    return text.rstrip()


def split_sections(text: str) -> list[SectionChunk]:
    """Return the current consolidated sections only, excluding transitions."""
    body = _trim_to_main_body(text)
    chunks: list[SectionChunk] = []
    for order, match in enumerate(SECTION_RE.finditer(body)):
        section_ref = re.sub(r"\s+", " ", match.group("section")).strip()
        raw_text = match.group(0).strip()
        remainder = match.group("body").strip()
        first_line = remainder.splitlines()[0].strip() if remainder else ""
        chunks.append(
            SectionChunk(
                section_ref=section_ref,
                heading=first_line,
                text=raw_text,
                order=order,
            )
        )
    return chunks
