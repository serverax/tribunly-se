"""
Phase 1 — ACAS guidance ingestion.

ACAS has no machine-readable API or feed (confirmed at build time, 2026-05-29).
The Code of Practice on Disciplinary and Grievance Procedures is treated as a
static authoritative document and ingested by fetching the ACAS website page.

Current edition: March 2015 (verified: no later edition found as of 2026-05-29).
Check ACAS_CODE_URL at each ingest run for any newer edition.

Usage:
    python -m ingestion.acas.ingest
"""

from __future__ import annotations

import logging
import re
from datetime import date
from html.parser import HTMLParser

import httpx
from rich.console import Console

from ingestion.config import settings, ACAS_CODE_URL, ACAS_CODE_TITLE, ACAS_CODE_EDITION
from ingestion.db import transaction, upsert_acas_guidance

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()

ACAS_CHUNK_CHARS = 2000
ACAS_OVERLAP_CHARS = 150

# The landing page only has navigation/summary text (2 chunks).
# The full Code text is at the /html path.
ACAS_CODE_FULL_URL = "https://www.acas.org.uk/acas-code-of-practice-on-disciplinary-and-grievance-procedures/html"

# Additional ACAS official guidance topics (public guidance, OGL-equivalent).
# Each is fetched as the single-page guide; thin pages (< MIN_GUIDANCE_CHARS) are
# skipped rather than stored as placeholder rows (fail-closed, no fake data).
MIN_GUIDANCE_CHARS = 600
ACAS_GUIDANCE_PAGES: list[tuple[str, str]] = [
    ("ACAS — Disciplinary procedure: step by step", "https://www.acas.org.uk/disciplinary-procedure-step-by-step"),
    ("ACAS — Grievance procedure: step by step", "https://www.acas.org.uk/grievance-procedure-step-by-step"),
    ("ACAS — Dismissals", "https://www.acas.org.uk/dismissals"),
    ("ACAS — Notice periods", "https://www.acas.org.uk/notice-periods"),
    ("ACAS — Early conciliation", "https://www.acas.org.uk/early-conciliation"),
    ("ACAS — Settlement agreements", "https://www.acas.org.uk/settlement-agreements"),
    ("ACAS — Managing staff redundancies", "https://www.acas.org.uk/manage-staff-redundancies"),
    ("ACAS — Unfair dismissal", "https://www.acas.org.uk/dismissals/unfair-dismissal"),
    ("ACAS — Discrimination at work", "https://www.acas.org.uk/discrimination-and-bullying/discrimination-at-work"),
    ("ACAS — Whistleblowing", "https://www.acas.org.uk/whistleblowing"),
    ("ACAS — Maternity leave and pay", "https://www.acas.org.uk/maternity-leave-and-pay"),
    ("ACAS — Paternity leave and pay", "https://www.acas.org.uk/paternity-leave-and-pay"),
    ("ACAS — Shared parental leave", "https://www.acas.org.uk/shared-parental-leave-and-pay"),
    ("ACAS — Parental leave", "https://www.acas.org.uk/parental-leave"),
    ("ACAS — National Minimum Wage", "https://www.acas.org.uk/national-minimum-wage"),
    ("ACAS — TUPE transfers", "https://www.acas.org.uk/tupe-transfers"),
    ("ACAS — Health and safety", "https://www.acas.org.uk/health-safety-and-wellbeing"),
    ("ACAS — Constructive dismissal", "https://www.acas.org.uk/dismissals/constructive-dismissal"),
    ("ACAS — Trade union recognition", "https://www.acas.org.uk/trade-union-recognition"),
    ("ACAS — Equal pay", "https://www.acas.org.uk/equal-pay"),
]


class _TextExtractor(HTMLParser):
    """Minimal HTML → plain text extractor (no lxml dependency for ACAS)."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_tags = {"script", "style", "nav", "header", "footer"}
        self._current_skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self._skip_tags:
            self._current_skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._skip_tags and self._current_skip:
            self._current_skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._current_skip:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._parts)).strip()


def _fetch_acas_page(url: str) -> str:
    """Fetch ACAS page and return its plain text content."""
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "lawapp/1.0 (employment-claim-copilot)"})
        resp.raise_for_status()

    extractor = _TextExtractor()
    extractor.feed(resp.text)
    return extractor.get_text()


def _chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split on sentence boundaries, accumulate into chunks."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current_len + len(sentence) > max_chars and current:
            chunks.append(" ".join(current))
            last = current[-1] if current else ""
            current = [last] if last else []
            current_len = len(last)
        current.append(sentence)
        current_len += len(sentence)

    if current:
        chunks.append(" ".join(current))

    return chunks or [""]


def ingest_acas_code() -> None:
    console.print("[bold green]Phase 1 — ACAS Code ingestion[/bold green]")
    console.print(f"Expected edition: {ACAS_CODE_EDITION} (verify at runtime)")
    console.print(f"Full Code URL: {ACAS_CODE_FULL_URL}")

    # Fetch the full Code HTML page, not the landing page.
    # Landing page only produces 2 chunks of navigation text.
    # The /html path contains the full paragraph text of the Code.
    try:
        text = _fetch_acas_page(ACAS_CODE_FULL_URL)
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Failed to fetch full ACAS Code text ({exc.response.status_code}). "
                      f"Falling back to landing page — RETRY_LATER for full ingestion.[/red]")
        try:
            text = _fetch_acas_page(ACAS_CODE_URL)
        except httpx.HTTPStatusError as exc2:
            console.print(f"[red]Both ACAS URLs failed: {exc2}[/red]")
            return

    if not text:
        console.print("[red]No text extracted from ACAS page.[/red]")
        return

    console.print(f"  Extracted {len(text):,} chars of text")

    # Check for edition change
    if "march 2015" not in text.lower() and "2015" not in text:
        console.print(
            "[bold yellow]FLAG: ACAS Code text does not mention 'March 2015' — "
            "a new edition may have been published. Verify manually before proceeding.[/bold yellow]"
        )

    chunks = _chunk_text(text, ACAS_CHUNK_CHARS, ACAS_OVERLAP_CHARS)
    console.print(f"  Chunked into {len(chunks)} chunk(s)")

    with transaction() as cur:
        for idx, chunk in enumerate(chunks):
            upsert_acas_guidance(cur, {
                "doc_title":    ACAS_CODE_TITLE,
                "edition":      ACAS_CODE_EDITION,
                "section_ref":  None,
                "body_text":    chunk,
                "chunk_index":  idx,
                "source_url":   ACAS_CODE_URL,
                "effective_from": date(2015, 3, 1),
            })

    console.print(f"[green]{len(chunks)} ACAS chunks stored.[/green]")
    console.print("[yellow]Note: verify ACAS Code edition each time ingest runs.[/yellow]")


def ingest_guidance_pages() -> None:
    """Ingest the additional ACAS official guidance topics (disciplinary, grievance,
    dismissal, early conciliation, settlement, redundancy, ...). Thin/failed pages
    are skipped — no placeholder rows."""
    console.print("[bold green]Phase 1 — ACAS guidance topics ingestion[/bold green]")
    stored_docs = 0
    for doc_title, url in ACAS_GUIDANCE_PAGES:
        try:
            text = _fetch_acas_page(url)
        except httpx.HTTPStatusError as exc:
            console.print(f"  [yellow]skip {url} (HTTP {exc.response.status_code})[/yellow]")
            continue
        except Exception as exc:  # network/other — skip, never fake
            console.print(f"  [yellow]skip {url} ({exc})[/yellow]")
            continue
        if not text or len(text) < MIN_GUIDANCE_CHARS:
            console.print(f"  [yellow]skip {url} (thin page, {len(text)} chars)[/yellow]")
            continue
        chunks = _chunk_text(text, ACAS_CHUNK_CHARS, ACAS_OVERLAP_CHARS)
        with transaction() as cur:
            for idx, chunk in enumerate(chunks):
                upsert_acas_guidance(cur, {
                    "doc_title":   doc_title,
                    "edition":     None,
                    "section_ref": None,
                    "body_text":   chunk,
                    "chunk_index": idx,
                    "source_url":  url,
                    "effective_from": None,
                })
        console.print(f"  [green]✓[/green] {doc_title}: {len(chunks)} chunk(s)")
        stored_docs += 1
    console.print(f"[bold]ACAS guidance topics stored: {stored_docs}/{len(ACAS_GUIDANCE_PAGES)}[/bold]")


def ingest_all() -> None:
    """Full ACAS ingestion: the Code of Practice + additional guidance topics."""
    ingest_acas_code()
    ingest_guidance_pages()


if __name__ == "__main__":
    ingest_all()
