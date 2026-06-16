"""
Phase 1  -  legislation.gov.uk ingestion job.

Fetches sections listed in config.LEGISLATION_TARGETS, parses CLML XML,
stores chunks in the `legislation` table. For sections amended by ERA 2025,
also fetches the /prospective version.

Usage:
    python -m ingestion.legislation.ingest
    python -m ingestion.legislation.ingest --section ukpga/1996/18/111  # single section
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from rich.console import Console
from rich.table import Table

from ingestion.config import settings, LEGISLATION_BASE, LEGISLATION_TARGETS
from ingestion.db import transaction, upsert_legislation
from ingestion.legislation.client import (
    resolve_title, fetch_section_xml, section_canonical_url
)
from ingestion.legislation.clml_parser import parse_section_xml

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s  -  %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()

# Sections where we must also fetch the /prospective version
# because ERA 2025 has enacted (but not yet commenced) changes.
PROSPECTIVE_SECTIONS: dict[tuple[str, int, str], list[str]] = {
    ("ukpga", 1996, "18"): ["108", "111", "124"],  # ERA 1996 sections amended by ERA 2025 s.25/s.152
}


def _resolve_targets() -> list[tuple]:
    """Targets come from the domain pack (domains/employment_uk/sources.yaml) so the
    source list is not hardcoded only in Python. Fall back to config.LEGISLATION_TARGETS
    if the pack cannot be loaded (keeps CI green if domains/ is absent)."""
    try:
        from ingestion.domain_loader import load_domain_pack
        pack = load_domain_pack("employment_uk")
        targets = pack.legislation_targets()
        if targets:
            console.print(f"[dim]Legislation targets loaded from domain pack: {pack.root}[/dim]")
            return targets
    except Exception as exc:  # pragma: no cover  -  pack-missing fallback
        console.print(f"[yellow]domain pack targets unavailable ({exc}); using config fallback[/yellow]")
    return list(LEGISLATION_TARGETS)


def ingest_all() -> None:
    """Run the full legislation ingestion."""
    console.print("[bold green]Phase 1  -  Legislation ingestion starting[/bold green]")

    total_chunks = 0
    errors: list[str] = []

    for act_title, leg_type, year, chapter, sections in _resolve_targets():
        console.print(f"\n[bold]{act_title}[/bold] ({leg_type}/{year}/{chapter})")

        # Verify chapter number via title resolution before fetching.
        resolved = resolve_title(act_title)
        if resolved:
            # legislation.gov.uk title resolution returns the Identifier URI form:
            #   /id/{type}/{year}/{chapter}
            # The Document URI (used for fetching) strips the /id prefix:
            #   /{type}/{year}/{chapter}
            # Both are correct; normalise before comparing so we catch genuine
            # mismatches (wrong chapter number) without rejecting the /id prefix.
            expected_suffix = f"/{leg_type}/{year}/{chapter}"
            resolved_normalised = resolved.replace("/id/", "/", 1)
            if not resolved_normalised.startswith(expected_suffix):
                msg = (
                    f"MISMATCH: '{act_title}' resolved to {resolved}, "
                    f"expected type/year/chapter {leg_type}/{year}/{chapter}. Flagging  -  not ingesting."
                )
                logger.error(msg)
                errors.append(msg)
                console.print(f"  [red]FLAG: {msg}[/red]")
                continue
            console.print(f"  Chapter verified: {resolved} ✓")
        else:
            console.print(f"  [yellow]Warning: could not resolve title for {act_title}  -  proceeding with configured chapter[/yellow]")

        for section in sections:
            _ingest_section(leg_type, year, chapter, section, act_title, False, total_chunks, errors)

            # Fetch prospective version for ERA 2025 amended sections
            prospective_key = (leg_type, year, chapter)
            if section in PROSPECTIVE_SECTIONS.get(prospective_key, []):
                _ingest_section(leg_type, year, chapter, section, act_title, True, total_chunks, errors)

        total_chunks += 1  # approximate count; real count accumulated in _ingest_section

    console.print(f"\n[bold]Done.[/bold] Errors: {len(errors)}")
    if errors:
        console.print("[red]Errors encountered (flag, do not proceed without resolving):[/red]")
        for e in errors:
            console.print(f"  • {e}")
        sys.exit(1)


def _ingest_section(
    leg_type: str, year: int, chapter: str, section: str,
    act_title: str, is_prospective: bool,
    _counter: int, errors: list[str],
) -> int:
    version = "prospective" if is_prospective else None
    label = f"  s.{section}" + (" [prospective]" if is_prospective else "")
    console.print(f"{label}", end=" ")

    source_url = section_canonical_url(leg_type, year, chapter, section, version)

    xml_bytes = fetch_section_xml(leg_type, year, chapter, section, version)
    if xml_bytes is None:
        console.print("[yellow]not found  -  skipped[/yellow]")
        return 0

    chunks = parse_section_xml(
        xml_bytes,
        source_url=source_url,
        leg_type=leg_type,
        is_prospective=is_prospective,
    )

    if not chunks:
        msg = f"No text extracted from {source_url}"
        errors.append(msg)
        console.print(f"[red]no text extracted[/red]")
        return 0

    with transaction() as cur:
        for chunk in chunks:
            upsert_legislation(cur, {
                # Always use the configured act_title: the CLML parser reads the
                # Part-level <Title> ("Unfair dismissal") rather than the Act name.
                # The configured value ("Employment Rights Act 1996") is authoritative.
                "act_title": act_title,
                "leg_type": chunk.leg_type or leg_type,
                "year": chunk.year or year,
                "chapter": chunk.chapter or chapter,
                "section_ref": chunk.section_ref or section,
                "jurisdiction": chunk.jurisdiction,
                "heading": chunk.heading,
                "body_text": chunk.body_text,
                "chunk_index": chunk.chunk_index,
                "source_url": chunk.source_url,
                "version_date": chunk.version_date,
                "effective_from": chunk.effective_from,
                "effective_to": chunk.effective_to,
                "is_prospective": chunk.is_prospective,
            })

    console.print(f"[green]{len(chunks)} chunk(s) stored[/green]")
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest legislation.gov.uk into the DB")
    parser.add_argument(
        "--section",
        help="Ingest a single section, e.g. ukpga/1996/18/111",
        default=None,
    )
    args = parser.parse_args()

    if args.section:
        parts = args.section.strip("/").split("/")
        if len(parts) < 4:
            console.print("[red]Expected format: leg_type/year/chapter/section[/red]")
            sys.exit(1)
        leg_type, year_s, chapter, section = parts[0], parts[1], parts[2], parts[3]
        _ingest_section(leg_type, int(year_s), chapter, section, "", False, 0, [])
    else:
        ingest_all()


if __name__ == "__main__":
    main()
