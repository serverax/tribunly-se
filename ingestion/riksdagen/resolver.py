"""Resolver that cross-checks SFS number, title, and amendment metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .client import document_html_url, document_text_url, normalise_sfs_number
from .types import RiksdagenListingItem


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


@dataclass(frozen=True)
class ResolverCandidate:
    sfs_number: str
    title: str
    undertitel: str | None
    amended_to: str | None
    source_url: str


class RiksdagenAmbiguityError(RuntimeError):
    """Raised when a listing query produces more than one plausible match."""

    def __init__(
        self,
        *,
        expected_sfs: str,
        expected_title: str,
        candidates: Iterable[ResolverCandidate],
    ) -> None:
        self.expected_sfs = normalise_sfs_number(expected_sfs)
        self.expected_title = expected_title
        self.candidates = list(candidates)
        message = (
            f"Ambiguous Riksdagen match for {self.expected_sfs!r} / {expected_title!r}: "
            + ", ".join(f"{c.sfs_number} {c.title}" for c in self.candidates)
        )
        super().__init__(message)


def _candidate_from_item(item: dict[str, Any]) -> ResolverCandidate:
    return ResolverCandidate(
        sfs_number=str(item.get("beteckning") or item.get("id") or ""),
        title=str(item.get("titel") or ""),
        undertitel=(str(item["undertitel"]) if item.get("undertitel") else None),
        amended_to=_extract_amended_to(item),
        source_url=_source_url(item),
    )


def _extract_amended_to(item: dict[str, Any]) -> str | None:
    undertitel = item.get("undertitel") or ""
    match = re.search(r"(\d{4}:\d+)$", str(undertitel))
    if match:
        return match.group(1)
    sokdata = item.get("sokdata") or {}
    statusrad = sokdata.get("statusrad") or ""
    match = re.search(r"SFS\s+(\d{4}:\d+)", str(statusrad))
    return match.group(1) if match else None


def _source_url(item: dict[str, Any]) -> str:
    url = str(item.get("url") or "")
    if url:
        return url
    relurl = str(item.get("relurl") or "")
    if relurl:
        return relurl if relurl.startswith("http") else f"https://data.riksdagen.se{relurl}"
    return ""


def resolve_listing_item(
    listing: dict[str, Any],
    expected_sfs: str,
    expected_title: str,
) -> RiksdagenListingItem:
    """Pick exactly one listing item for a given SFS number and title."""
    expected_sfs = normalise_sfs_number(expected_sfs)
    candidates = listing.get("dokumentlista", {}).get("dokument", [])
    if isinstance(candidates, dict):
        candidates = [candidates]

    matched: list[ResolverCandidate] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_sfs = str(item.get("beteckning") or item.get("id") or "").strip()
        candidate_title = str(item.get("titel") or "").strip()
        if normalise_sfs_number(candidate_sfs) != expected_sfs:
            continue
        if _compact(candidate_title) != _compact(expected_title):
            continue
        matched.append(_candidate_from_item(item))

    if len(matched) == 1:
        selected = matched[0]
        return RiksdagenListingItem(
            sfs_number=selected.sfs_number,
            title=selected.title,
            undertitel=selected.undertitel,
            amended_to=selected.amended_to,
            document_url_text=document_text_url(selected.sfs_number),
            document_url_html=document_html_url(selected.sfs_number),
            source_url=selected.source_url,
            published_at=_published_at_from_item(candidates, expected_sfs),
            issued_at=_issued_at_from_item(candidates, expected_sfs),
        )

    if len(matched) > 1:
        raise RiksdagenAmbiguityError(
            expected_sfs=expected_sfs,
            expected_title=expected_title,
            candidates=matched,
        )

    fallback: list[ResolverCandidate] = []
    for item in candidates:
        if isinstance(item, dict) and normalise_sfs_number(str(item.get("beteckning") or item.get("id") or "0:0")) == expected_sfs:
            fallback.append(_candidate_from_item(item))

    raise RiksdagenAmbiguityError(
        expected_sfs=expected_sfs,
        expected_title=expected_title,
        candidates=fallback,
    )


def _published_at_from_item(items: list[dict[str, Any]], expected_sfs: str) -> str | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate_sfs = str(item.get("beteckning") or item.get("id") or "").strip()
        if normalise_sfs_number(candidate_sfs) != expected_sfs:
            continue
        value = item.get("publicerad") or item.get("systemdatum")
        return str(value) if value else None
    return None


def _issued_at_from_item(items: list[dict[str, Any]], expected_sfs: str) -> str | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate_sfs = str(item.get("beteckning") or item.get("id") or "").strip()
        if normalise_sfs_number(candidate_sfs) != expected_sfs:
            continue
        value = item.get("datum")
        return str(value) if value else None
    return None
