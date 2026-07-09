"""Metadata parsing for Riksdagen SFS bundles."""

from __future__ import annotations

import re
from typing import Any, Mapping

from .client import normalise_sfs_number
from .types import RiksdagenProvenance


def _lookup(metadata: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value:
            return str(value)
    return None


def extract_provenance(metadata: Mapping[str, Any]) -> RiksdagenProvenance:
    """Extract the act provenance fields we need for draft and parser output."""
    sfs_number = normalise_sfs_number(
        str(metadata.get("beteckning") or metadata.get("id") or metadata.get("dok_id") or "")
    )
    title = str(metadata.get("titel") or "")
    undertitel = str(metadata.get("undertitel") or "")
    amended_to = None
    match = re.search(r"(\d{4}:\d+)$", undertitel)
    if match:
        amended_to = match.group(1)
    else:
        statusrad = str((metadata.get("sokdata") or {}).get("statusrad") or "")
        match = re.search(r"SFS\s+(\d{4}:\d+)", statusrad)
        if match:
            amended_to = match.group(1)

    return RiksdagenProvenance(
        sfs_number=sfs_number,
        title=title,
        amended_to=amended_to,
        issued_at=_lookup(metadata, "datum"),
        published_at=_lookup(metadata, "publicerad", "systemdatum"),
        source_url=f"https://data.riksdagen.se/dokument/sfs-{sfs_number.replace(':', '-')}.text",
        document_url_text=_lookup(metadata, "dokument_url_text") or "",
        document_url_html=_lookup(metadata, "dokument_url_html") or "",
        amendment_effective_from=str(metadata.get("amendment_effective_from"))
        if metadata.get("amendment_effective_from")
        else None,
    )
