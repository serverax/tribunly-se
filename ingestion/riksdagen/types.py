"""Shared typing helpers for the Sweden Riksdagen parser."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class RiksdagenListingItem:
    sfs_number: str
    title: str
    undertitel: str | None
    amended_to: str | None
    document_url_text: str
    document_url_html: str
    source_url: str
    published_at: str | None
    issued_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiksdagenProvenance:
    sfs_number: str
    title: str
    amended_to: str | None
    issued_at: str | None
    published_at: str | None
    source_url: str
    document_url_text: str
    document_url_html: str
    amendment_effective_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiksdagenSectionChunk:
    sfs_number: str
    title: str
    section_ref: str
    order: int
    text: str
    source_url: str
    document_url_html: str
    amended_to: str | None
    amendment_effective_from: str | None
    published_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
