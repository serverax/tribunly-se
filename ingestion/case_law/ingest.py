"""
Phase 1  -  Find Case Law ingestion (EAT decisions).

LICENCE GATE:
  - Bulk atom-feed pagination: BLOCKED until FCL_BULK_LICENCE_GRANTED=true.
    Submit: https://caselaw.nationalarchives.gov.uk/re-use-find-case-law-records/licence-application-process
    Contact: caselawlicence@nationalarchives.gov.uk
  - Per-document fetch: ALWAYS permitted under the Open Justice Licence.

Phase 1 runs in SAMPLE mode: fetches a small set of known EAT decisions
by URI to prove the pipeline, without triggering the bulk-licence requirement.

Usage:
    python -m ingestion.case_law.ingest --sample     # Phase 1: ingest sample URIs only
    python -m ingestion.case_law.ingest --bulk       # requires licence grant
"""

from __future__ import annotations

import argparse
import logging
import sys

from rich.console import Console

from ingestion.config import settings, FCL_BASE
from ingestion.db import transaction, upsert_case_law_document, upsert_case_law_chunk
from ingestion.case_law.client import fetch_document_xml, iter_atom_feed, lookup_document_uri_by_slug
from ingestion.case_law.akn_parser import parse_judgment_xml, ParsedCase

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s  -  %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()

# Sample decisions: (slug, stable_d_uuid) pairs confirmed from live atom feed 2026-05-29.
# slug:          eat/year/num   -  working fetch path (eat/year/num/data.xml returns 200)
# stable_d_uuid: d-{uuid}       -  stable identifier from atom feed <tna:uri>; stored as document_uri
#
# NOTE on d-{uuid}/data.xml: the API appendix says this form should work for fetching,
# but live tests show 404. The atom feed's explicit <link type="akn+xml"> href (the slug form)
# is what actually resolves. This discrepancy is flagged for confirmation with FCL team
# (caselaw@nationalarchives.gov.uk) before the change-detection refresh depends on it.
SAMPLE_EAT_DOCS: list[tuple[str, str | None]] = [
    ("eat/2026/78", "d-d7719042-c198-4514-b5da-74b3b100176b"),  # H Rogers v SoS Justice
    ("eat/2026/77", "d-ecd7280c-c0ce-4a19-89c6-e5b707b5154a"),  # LAS NHS Trust v Garrett
    ("eat/2026/76", "d-a982f877-66fd-4366-b65d-c6d45aa964d1"),  # Deans v RBL Law Ltd
    ("eat/2026/75", "d-cffe39f4-4281-4677-9381-53c12eb4e999"),  # Komeng v National Highways
    ("eat/2026/74", "d-e1929028-0d11-40e4-a9b5-d97bce09279c"),  # DHL v Ignatowicz
]


def _resolve_stable_document_uri(xml_slug: str, fallback_document_uri: str | None = None) -> str:
    """
    Resolve the stable decision identifier for a fetch slug.

    Manual/sample ingestion can start from slugs; we still persist the stable
    identifier (`d-{uuid}`) by using supplied mappings first and atom lookup when
    needed.
    """
    if fallback_document_uri:
        return fallback_document_uri
    return lookup_document_uri_by_slug(xml_slug) or xml_slug


def ingest_sample() -> None:
    """
    Ingest SAMPLE_EAT_DOCS to prove the pipeline. No bulk licence required.

    Each entry carries both the fetch slug (eat/year/num) and the stable d-{uuid}
    identifier confirmed from the atom feed. The d-uuid is stored as document_uri;
    the slug is used only for XML fetching and stored as fetch_url on the document row.
    """
    console.print("[bold green]Phase 1  -  EAT sample ingestion (per-document, no bulk licence needed)[/bold green]")
    console.print(f"Ingesting {len(SAMPLE_EAT_DOCS)} sample documents.")

    success = 0
    errors: list[str] = []

    for slug, fallback_document_uri in SAMPLE_EAT_DOCS:
        fetch_url = f"{FCL_BASE}/{slug}/data.xml"
        document_uri = _resolve_stable_document_uri(slug, fallback_document_uri)
        console.print(f"  {slug} ({document_uri[:20]}…)", end=" ")

        xml_bytes = fetch_document_xml(slug)
        if xml_bytes is None:
            console.print("[yellow]not found  -  skipped[/yellow]")
            errors.append(f"404: {slug}")
            continue

        parsed = parse_judgment_xml(
            xml_bytes,
            document_uri=document_uri,
            xml_slug=slug,
            source_url=fetch_url,
        )
        if parsed is None:
            console.print("[red]parse failed[/red]")
            errors.append(f"parse fail: {slug}")
            continue

        _store_case(parsed)
        console.print(f"[green]{parsed.neutral_citation or 'no citation'}  -  {len(parsed.chunks)} chunk(s)[/green]")
        success += 1

    console.print(f"\nDone. {success}/{len(SAMPLE_EAT_DOCS)} documents ingested. Errors: {len(errors)}")
    if errors:
        for e in errors:
            console.print(f"  [red]• {e}[/red]")


def ingest_bulk(max_pages: int = 10) -> None:
    """
    Bulk ingestion via atom feed pagination. Requires computational-analysis licence.
    Set FCL_BULK_LICENCE_GRANTED=true in .env after the licence is granted.
    """
    if not settings.fcl_bulk_licence_granted:
        console.print(
            "[bold red]BLOCKED: bulk ingestion requires FCL_BULK_LICENCE_GRANTED=true.[/bold red]\n"
            "Submit the computational-analysis application first:\n"
            "  https://caselaw.nationalarchives.gov.uk/re-use-find-case-law-records/licence-application-process\n"
            "Contact: caselawlicence@nationalarchives.gov.uk\n"
            "See docs/FCL_APPLICATION_PREP.md for draft answers."
        )
        sys.exit(1)

    console.print(f"[bold green]Phase 1  -  EAT bulk ingestion (max_pages={max_pages})[/bold green]")
    success = 0
    skipped = 0

    for entry in iter_atom_feed(max_pages=max_pages):
        doc_uri  = entry["document_uri"]
        xml_slug = entry.get("xml_slug") or ""
        if not doc_uri or not xml_slug:
            skipped += 1
            continue

        # Fetch via the atom feed's explicit XML link (slug form), store d-uuid as identifier
        xml_bytes = fetch_document_xml(xml_slug)
        if xml_bytes is None:
            skipped += 1
            continue

        source_url = f"{FCL_BASE}/{xml_slug}/data.xml"
        parsed = parse_judgment_xml(
            xml_bytes,
            document_uri=doc_uri,
            xml_slug=xml_slug,
            source_url=source_url,
        )
        if parsed is None:
            skipped += 1
            continue

        _store_case(parsed)
        console.print(f"  [green]{parsed.neutral_citation or doc_uri}[/green]")
        success += 1

    console.print(f"\nDone. Stored: {success}, Skipped: {skipped}")


def _store_case(parsed: ParsedCase) -> None:
    """Store a parsed decision into case_law_documents (one row) + case_law_chunks (one per chunk)."""
    with transaction() as cur:
        # 1. Upsert the document-level metadata row
        doc_id = upsert_case_law_document(cur, {
            "document_uri":     parsed.document_uri,
            "fetch_url":        parsed.source_url,
            "neutral_citation": parsed.neutral_citation,
            "fclid":            parsed.fclid,
            "case_name":        parsed.case_name,
            "court_code":       parsed.court_code,
            "decision_date":    parsed.decision_date,
            "judges":           parsed.judges or [],
            "parties":          parsed.parties or [],
            "content_hash":     parsed.content_hash,
            "published_date":   parsed.published_date,
            "updated_date":     parsed.updated_date,
        })
        # 2. Upsert each chunk with FK to the document
        for idx, chunk_text in enumerate(parsed.chunks):
            upsert_case_law_chunk(cur, doc_id, idx, chunk_text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Find Case Law (EAT decisions)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", action="store_true",
                       help="Ingest sample URIs only (Phase 1, no bulk licence needed)")
    group.add_argument("--bulk", action="store_true",
                       help="Full bulk ingestion via atom feed (requires FCL_BULK_LICENCE_GRANTED=true)")
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args()

    if args.sample:
        ingest_sample()
    else:
        ingest_bulk(max_pages=args.max_pages)


if __name__ == "__main__":
    main()
