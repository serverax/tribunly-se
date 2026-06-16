"""
HTTP client for legislation.gov.uk with polite throttling.

No API key required. No published rate limit  -  Fair Use Policy applies.
Throttle to LEGISLATION_REQUESTS_PER_SECOND (default 1 req/s) and use
exponential back-off on 429/503.

URI scheme:
  Identifier:     /id/{type}/{year}/{number}[/{section}]
  Representation: /{type}/{year}/{number}[/{section}]/data.xml
  Title resolve:  /id?title={url-encoded title}  → 301 to canonical URI
"""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ingestion.config import settings, LEGISLATION_BASE

logger = logging.getLogger(__name__)

_THROTTLE_INTERVAL = 1.0 / settings.legislation_requests_per_second
_last_request_time: float = 0.0


def _throttle() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _THROTTLE_INTERVAL:
        time.sleep(_THROTTLE_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
)
def _get(url: str, follow_redirects: bool = True) -> httpx.Response:
    _throttle()
    with httpx.Client(follow_redirects=follow_redirects, timeout=30) as client:
        resp = client.get(url, headers={"Accept": "application/xml"})
        if resp.status_code == 404:
            return resp  # caller handles 404 (section not found is expected)
        resp.raise_for_status()
        return resp


def resolve_title(title: str) -> Optional[str]:
    """
    Resolve a plain-text Act title to its canonical legislation.gov.uk URI.
    Returns the canonical path (e.g. '/ukpga/1996/18') or None if not found.

    Per the API spec: 301 → unique match; 300/303 → multiple choices (parse the HTML).
    """
    url = f"{LEGISLATION_BASE}/id?{urlencode({'title': title})}"
    try:
        with httpx.Client(follow_redirects=False, timeout=30) as client:
            _throttle()
            resp = client.get(url)

        if resp.status_code == 301:
            location = resp.headers.get("Location", "")
            # Strip trailing /contents or similar
            path = location.split("legislation.gov.uk")[-1].rstrip("/contents")
            logger.info("Title '%s' resolved to %s", title, path)
            return path

        if resp.status_code in (300, 303):
            logger.warning(
                "Title '%s' returned multiple choices (%s). Inspect manually: %s",
                title, resp.status_code, url,
            )
            return None

        logger.warning("Title resolution for '%s' returned %s", title, resp.status_code)
        return None

    except Exception as exc:
        logger.error("Title resolution failed for '%s': %s", title, exc)
        return None


def fetch_section_xml(leg_type: str, year: int, chapter: str, section: str,
                      version: Optional[str] = None) -> Optional[bytes]:
    """
    Fetch a single section's CLML XML.

    version: None → currently in force; 'prospective' → not-yet-commenced text;
             'YYYY-MM-DD' → point-in-time.
    """
    base_path = f"/{leg_type}/{year}/{chapter}/section/{section}"
    if version:
        base_path = f"{base_path}/{version}"
    url = f"{LEGISLATION_BASE}{base_path}/data.xml"

    logger.debug("Fetching legislation XML: %s", url)
    resp = _get(url)

    if resp.status_code == 404:
        logger.warning("Section not found (404): %s", url)
        return None

    return resp.content


def fetch_whole_act_xml(leg_type: str, year: int, chapter: str,
                        version: Optional[str] = None) -> Optional[bytes]:
    """Fetch the whole act as CLML XML. Use for small/medium acts."""
    base_path = f"/{leg_type}/{year}/{chapter}"
    if version:
        base_path = f"{base_path}/{version}"
    url = f"{LEGISLATION_BASE}{base_path}/data.xml"

    logger.debug("Fetching whole act XML: %s", url)
    resp = _get(url)

    if resp.status_code == 404:
        logger.warning("Act not found (404): %s", url)
        return None

    return resp.content


def section_canonical_url(leg_type: str, year: int, chapter: str, section: str,
                           version: Optional[str] = None) -> str:
    """Return the canonical source URL to store in the legislation table."""
    base = f"{LEGISLATION_BASE}/{leg_type}/{year}/{chapter}/section/{section}"
    if version:
        return f"{base}/{version}/data.xml"
    return f"{base}/data.xml"
