"""Whitelist crawler — Perpetual Law Brain stage 1.

PHYSICALLY refuses any URL whose host is not an official UK legal source. No
arbitrary internet crawl, no search engines, no news/blog/opinion. Redirects are
validated hop-by-hop: a redirect that points off the whitelist is blocked, not
followed.

This module does NOT decide law. It only decides whether a URL is an allowed
official source and returns the raw bytes + a content hash for downstream gates.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from urllib.parse import urlparse

# Hardcoded allow-list. Nothing else may enter the legal brain.
DOMAIN_WHITELIST: frozenset[str] = frozenset({
    "legislation.gov.uk",
    "www.legislation.gov.uk",
    "caselaw.nationalarchives.gov.uk",
    "nationalarchives.gov.uk",
    "acas.org.uk",
    "www.acas.org.uk",
})

_MAX_REDIRECTS = 5


class BlockedDomainError(Exception):
    """Raised when a URL (or a redirect target) is not on DOMAIN_WHITELIST."""


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content: str
    content_hash: str
    domain: str


def host_of(url: str) -> str:
    """Return the lowercased host (no port) of a URL, or '' if unparseable."""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.split("@")[-1].split(":")[0]
    except Exception:
        return ""


def is_whitelisted(url: str) -> bool:
    return host_of(url) in DOMAIN_WHITELIST


def assert_whitelisted(url: str) -> None:
    """Raise BlockedDomainError unless the URL host is on the whitelist."""
    host = host_of(url)
    if host not in DOMAIN_WHITELIST:
        raise BlockedDomainError(
            f"Blocked non-whitelisted domain: {host or '<unparseable>'} ({url})"
        )


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


class WhitelistCrawler:
    """Fetches official legal sources only. Validates every redirect hop."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> FetchResult:
        """Fetch an allowed URL. Raises BlockedDomainError BEFORE any network call
        if the URL is not whitelisted, and on any redirect that leaves the
        whitelist."""
        assert_whitelisted(url)  # refuse before touching the network
        import httpx

        current = url
        with httpx.Client(follow_redirects=False, timeout=self.timeout) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                resp = client.get(current)
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location", "")
                    target = str(httpx.URL(current).join(location))
                    assert_whitelisted(target)  # block off-whitelist redirects
                    current = target
                    continue
                body = resp.text
                return FetchResult(
                    url=url,
                    final_url=current,
                    status_code=resp.status_code,
                    content=body,
                    content_hash=content_hash(body),
                    domain=host_of(current),
                )
        raise BlockedDomainError(f"Too many redirects starting from {url}")
