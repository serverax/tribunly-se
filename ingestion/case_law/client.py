"""
HTTP client for Find Case Law (National Archives).

Rate limit: 1,000 requests per rolling 5-minute window per IP.
We target FCL_REQUESTS_PER_SECOND (default 1 req/s)  -  well under the limit.

Bulk atom-feed pagination is GATED behind FCL_BULK_LICENCE_GRANTED.
Per-document fetches (fetch_document_xml) are always allowed within the
Open Justice Licence terms.

API docs: https://nationalarchives.github.io/ds-find-caselaw-docs/public
Contact:  caselawlicence@nationalarchives.gov.uk
"""

from __future__ import annotations

import logging
import time
from typing import Iterator, Optional
from xml.etree import ElementTree as ET

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ingestion.config import settings, FCL_BASE, FCL_ATOM_URL, FCL_EAT_ATOM_PARAMS

logger = logging.getLogger(__name__)

ATOM_NS = "http://www.w3.org/2005/Atom"
TNA_NS  = "https://caselaw.nationalarchives.gov.uk"   # confirmed from live atom feed XML

_THROTTLE_INTERVAL = 1.0 / settings.fcl_requests_per_second
_last_request_time: float = 0.0


def _throttle() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _THROTTLE_INTERVAL:
        time.sleep(_THROTTLE_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    wait=wait_exponential(multiplier=2, min=4, max=120),
    stop=stop_after_attempt(5),
)
def _get(url: str, params: Optional[dict] = None) -> httpx.Response:
    _throttle()
    with httpx.Client(timeout=60) as client:
        resp = client.get(url, params=params)
        if resp.status_code == 429:
            logger.warning("FCL rate limit hit (429)  -  tenacity will retry with back-off")
            resp.raise_for_status()
        if resp.status_code == 404:
            return resp
        resp.raise_for_status()
        return resp


def fetch_document_xml(xml_slug: str) -> Optional[bytes]:
    """
    Fetch a single document's Akoma Ntoso XML.

    xml_slug: the fetch path slug, e.g. 'eat/2024/123'.
    Always permitted under the Open Justice Licence (no bulk-licence gate).
    """
    url = f"{FCL_BASE}/{xml_slug}/data.xml"
    logger.debug("Fetching FCL document: %s", url)
    resp = _get(url)
    if resp.status_code == 404:
        logger.warning("FCL document not found (404): %s", url)
        return None
    return resp.content


def lookup_document_uri_by_slug(xml_slug: str, max_pages: int = 3) -> Optional[str]:
    """
    Resolve a stable document identifier (d-{uuid}) for a fetch slug.

    This is a targeted lookup used by manual/sample ingestion paths that start
    from known slugs (eat/year/number) instead of iterating the full atom feed.
    """
    if not xml_slug:
        return None

    feed_params = dict(FCL_EAT_ATOM_PARAMS)
    for page in range(1, max_pages + 1):
        feed_params["page"] = str(page)
        logger.debug("Resolving slug via atom feed page %d: %s", page, xml_slug)
        resp = _get(FCL_ATOM_URL, params=feed_params)
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            return None

        entries = root.findall(f"{{{ATOM_NS}}}entry")
        for entry in entries:
            parsed = _parse_atom_entry(entry)
            if parsed.get("xml_slug") == xml_slug:
                return parsed.get("document_uri") or None

        if not entries:
            break

    return None


def iter_atom_feed(
    params: Optional[dict] = None,
    max_pages: Optional[int] = None,
) -> Iterator[dict]:
    """
    Paginate through the FCL Atom feed and yield entry dicts.

    GUARDRAIL: Raises RuntimeError if FCL_BULK_LICENCE_GRANTED is not True.
    Use fetch_document_xml for per-document access instead.

    Each yielded dict contains:
        document_uri, xml_slug, published, updated, content_hash, xml_url, pdf_url
    """
    if not settings.fcl_bulk_licence_granted:
        raise RuntimeError(
            "Bulk atom-feed pagination requires the Find Case Law computational-analysis "
            "licence to be granted and FCL_BULK_LICENCE_GRANTED=true set in .env. "
            "Submit the application at: "
            "https://caselaw.nationalarchives.gov.uk/re-use-find-case-law-records/licence-application-process"
        )

    feed_params = dict(FCL_EAT_ATOM_PARAMS)
    if params:
        feed_params.update(params)

    page = 1
    while True:
        if max_pages and page > max_pages:
            break

        feed_params["page"] = str(page)
        logger.info("Fetching FCL atom feed page %d (params: %s)", page, feed_params)
        resp = _get(FCL_ATOM_URL, params=feed_params)

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as exc:
            logger.error("Atom feed parse error on page %d: %s", page, exc)
            break

        entries = root.findall(f"{{{ATOM_NS}}}entry")
        if not entries:
            logger.info("No more entries at page %d  -  feed exhausted", page)
            break

        for entry in entries:
            yield _parse_atom_entry(entry)

        page += 1


def _parse_atom_entry(entry: ET.Element) -> dict:
    """
    Extract the fields we need from an Atom <entry> element.

    document_uri: the stable d-{uuid} identifier (store in DB, from <tna:uri>)
    xml_slug:     the fetch path, e.g. 'eat/2026/78' (from <link type="akn+xml">)
                  Use this as the argument to fetch_document_xml().
                  The d-uuid is the identifier; the slug is the URL path for XML.
    """
    def _find_text(tag: str, ns: str = ATOM_NS) -> Optional[str]:
        el = entry.find(f"{{{ns}}}{tag}")
        return el.text.strip() if el is not None and el.text else None

    document_uri = _find_text("uri", TNA_NS) or ""
    content_hash = _find_text("contenthash", TNA_NS) or ""
    published = _find_text("published")
    updated = _find_text("updated")

    xml_url: Optional[str] = None
    xml_slug: Optional[str] = None
    pdf_url: Optional[str] = None
    for link_el in entry.findall(f"{{{ATOM_NS}}}link"):
        rel  = link_el.get("rel", "")
        mime = link_el.get("type", "")
        href = link_el.get("href", "")
        if rel == "alternate" and "akn+xml" in mime:
            xml_url = href
            # Derive the slug: strip base URL and trailing /data.xml
            # e.g. https://caselaw.../eat/2026/78/data.xml → eat/2026/78
            if href.startswith(FCL_BASE):
                xml_slug = href[len(FCL_BASE):].strip("/").removesuffix("/data.xml")
        elif rel == "alternate" and "pdf" in mime:
            pdf_url = href

    return {
        "document_uri": document_uri,   # d-{uuid}  -  store in DB
        "xml_slug":     xml_slug,        # eat/year/num  -  use for fetching
        "published":    published,
        "updated":      updated,
        "content_hash": content_hash,
        "xml_url":      xml_url,
        "pdf_url":      pdf_url,
    }
