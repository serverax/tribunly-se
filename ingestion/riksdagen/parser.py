"""Parser entrypoint for Swedish Riksdagen SFS fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .provenance import extract_provenance
from .resolver import resolve_listing_item
from .sectionizer import split_sections


def load_fixture_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    root = Path(bundle_dir)
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    text = (root / "text.txt").read_text(encoding="utf-8")
    html = (root / "html.html").read_text(encoding="utf-8")
    listing = json.loads((root / "listing.json").read_text(encoding="utf-8"))
    return {
        "metadata": metadata,
        "text": text,
        "html": html,
        "listing": listing,
        "root": root,
    }


def parse_document(
    metadata: Mapping[str, Any],
    text: str,
) -> list[dict[str, Any]]:
    """Parse a consolidated Riksdagen text blob into JSON chunk structures."""
    provenance = extract_provenance(metadata)
    sections = split_sections(text)
    chunks: list[dict[str, Any]] = []
    for section in sections:
        chunks.append(
            {
                "source_system": "riksdagen",
                "source_kind": "sfs",
                "sfs_number": provenance.sfs_number,
                "title": provenance.title,
                "section_ref": section.section_ref,
                "section_heading": section.heading,
                "chunk_index": section.order,
                "text": section.text,
                "source_url": provenance.source_url,
                "document_url_text": provenance.document_url_text,
                "document_url_html": provenance.document_url_html,
                "amended_to_sfs": provenance.amended_to,
                "amendment_effective_from": provenance.amendment_effective_from,
                "issued_at": provenance.issued_at,
                "published_at": provenance.published_at,
            }
        )
    return chunks


def parse_fixture_bundle(bundle_dir: str | Path) -> list[dict[str, Any]]:
    bundle = load_fixture_bundle(bundle_dir)
    listing_item = resolve_listing_item(
        bundle["listing"],
        expected_sfs=bundle["metadata"]["beteckning"],
        expected_title=bundle["metadata"]["titel"],
    )
    bundle["metadata"]["dokument_url_text"] = listing_item.document_url_text
    bundle["metadata"]["dokument_url_html"] = listing_item.document_url_html
    return parse_document(bundle["metadata"], bundle["text"])
