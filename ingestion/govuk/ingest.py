"""
GOV.UK Content API ingestion.

Fetches official government guidance from https://www.gov.uk/api/content/{path}
Stores in official_guidance table.
Source type: explanation/support  -  NOT primary law.

Usage:
    python -m ingestion.govuk.ingest
    python -m ingestion.govuk.ingest --path /dismiss-staff
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re

import httpx
from rich.console import Console

from ingestion.config import settings
from ingestion.db import transaction

console = Console()
logger  = logging.getLogger(__name__)

GOVUK_API = "https://www.gov.uk/api/content"

# Priority employment guidance paths (official GOV.UK content API).
# Paths that 404 or return no body are skipped  -  no placeholder rows.
EMPLOYMENT_GUIDANCE_PATHS = [
    "/dismiss-staff",
    "/employment-tribunals",
    "/make-claim-to-employment-tribunal",
    "/calculate-your-redundancy-pay",
    "/staff-redundant",
    "/employee-rights-when-company-faces-closure",
    "/redundancy-your-rights",
    "/unfair-dismissal-your-rights",
    "/employment-contracts",
    "/pay-and-work-rights",
    "/statutory-pay-entitlement",
    "/holiday-entitlement-rights",
    "/acas-early-conciliation",
    # expansion (tribunal procedure + disciplinary/grievance + statutory rights)
    "/raise-grievance-at-work",
    "/disciplinary-procedures-and-action-at-work",
    "/written-statement-employment-particulars",
    "/whistleblowing",
    "/being-monitored-at-work",
    "/flexible-working",
    "/employment-status",
    "/national-minimum-wage-rates",
    "/maternity-pay-leave",
    "/taking-sick-leave",
    "/continuous-employment-what-it-is",
    "/dismissal",
    # Phase 1 repair  -  additional licensed GOV.UK paths (verified 2026-06-16)
    "/statutory-sick-pay",
    "/paternity-pay-leave",
    "/adoption-pay-leave",
    "/overtime-your-rights",
]


GOVUK_CHUNK_CHARS = 2000
GOVUK_OVERLAP_CHARS = 150


def _chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
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
    return chunks or [text]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _extract_body(content: dict) -> str:
    """Extract plain text from GOV.UK content API response."""
    parts = []

    # Title and description
    if content.get("title"):
        parts.append(content["title"])
    if content.get("description"):
        parts.append(content["description"])

    # Body text (HTML  -  store as-is; strip later if needed)
    details = content.get("details", {})
    if isinstance(details, dict):
        body = details.get("body", "")
        if body:
            # Basic HTML strip
            import re
            body = re.sub(r"<[^>]+>", " ", body)
            body = re.sub(r"\s+", " ", body).strip()
            parts.append(body)

    return "\n\n".join(parts).strip()


def ingest_path(path: str, conn=None) -> bool:
    """Fetch one GOV.UK path and upsert into official_guidance."""
    url = f"{GOVUK_API}{path}"
    try:
        resp = httpx.get(url, timeout=10, headers={"Accept": "application/json"})
        resp.raise_for_status()
    except Exception as e:
        logger.warning("GOV.UK fetch failed for %s: %s", path, e)
        return False

    content = resp.json()
    body    = _extract_body(content)
    if not body:
        logger.warning("No body text for %s  -  skipping", path)
        return False

    title        = content.get("title", path)
    description  = content.get("description", "")
    public_url   = f"https://www.gov.uk{path}"
    doc_type     = content.get("document_type", "guidance")
    content_type = content.get("schema_name", "guidance")
    pub_date     = content.get("public_updated_at", "")
    chunks = _chunk_text(body, GOVUK_CHUNK_CHARS, GOVUK_OVERLAP_CHARS)

    sql = """
        INSERT INTO official_guidance
            (source_name, source_url, title, description, body_text,
             document_type, jurisdiction, metadata, content_hash,
             is_current, last_verified_at, chunk_index,
             country_code, domain, source_type, licence_status,
             parser_type, parent_source_id)
        VALUES
            ('govuk', %(url)s, %(title)s, %(desc)s, %(body)s,
             %(doc_type)s, 'EW', %(meta)s::jsonb, %(hash)s,
             true, now(), %(chunk_index)s,
             'GB', 'employment_uk', 'official_guidance', 'GRANTED',
             'html', 'govuk')
        ON CONFLICT (source_url, chunk_index) DO UPDATE SET
            title            = EXCLUDED.title,
            description      = EXCLUDED.description,
            body_text        = EXCLUDED.body_text,
            content_hash     = EXCLUDED.content_hash,
            last_verified_at = now(),
            country_code     = EXCLUDED.country_code,
            domain           = EXCLUDED.domain,
            source_type      = EXCLUDED.source_type,
            licence_status   = EXCLUDED.licence_status,
            parser_type      = EXCLUDED.parser_type,
            parent_source_id = EXCLUDED.parent_source_id
        WHERE official_guidance.content_hash != EXCLUDED.content_hash
    """
    import json
    meta = json.dumps({"schema_name": content_type, "public_updated_at": pub_date})

    def _exec(cur) -> None:
        cur.execute("DELETE FROM official_guidance WHERE source_url = %s", (public_url,))
        for idx, chunk in enumerate(chunks):
            params = {
                "url": public_url,
                "title": title if idx == 0 else f"{title} (part {idx + 1})",
                "desc": description,
                "body": chunk,
                "doc_type": doc_type,
                "meta": meta,
                "hash": _content_hash(chunk),
                "chunk_index": idx,
            }
            cur.execute(sql, params)

    if conn:
        with conn.cursor() as cur:
            _exec(cur)
    else:
        with transaction() as cur:
            _exec(cur)

    console.print(f"  [green]✓[/green] {path}  -  {len(body)} chars, {len(chunks)} chunk(s)")
    return True


def ingest_all() -> None:
    console.print("[bold green]GOV.UK guidance ingestion starting[/bold green]")
    ok = 0
    with transaction() as cur:
        conn_obj = cur.connection  # type: ignore[attr-defined]
        for path in EMPLOYMENT_GUIDANCE_PATHS:
            if ingest_path(path, conn_obj):
                ok += 1
    console.print(f"[bold]Done: {ok}/{len(EMPLOYMENT_GUIDANCE_PATHS)} paths ingested[/bold]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GOV.UK guidance ingestion")
    parser.add_argument("--path", help="Single GOV.UK path to ingest (e.g. /dismiss-staff)")
    args = parser.parse_args()
    if args.path:
        ingest_path(args.path)
    else:
        ingest_all()
