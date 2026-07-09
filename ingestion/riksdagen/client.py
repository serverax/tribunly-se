"""HTTP client for Riksdagens öppna data."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://data.riksdagen.se"
REQUESTS_PER_SECOND = 1.0
_MIN_INTERVAL = 1.0 / REQUESTS_PER_SECOND
_LAST_REQUEST_AT = 0.0


class RiksdagenFetchError(RuntimeError):
    """Raised when a live Riksdagen fetch fails."""


def _throttle() -> None:
    global _LAST_REQUEST_AT
    elapsed = time.monotonic() - _LAST_REQUEST_AT
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_REQUEST_AT = time.monotonic()


def _get(url: str, *, accept: str) -> httpx.Response:
    _throttle()
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(url, headers={"Accept": accept})
    response.raise_for_status()
    return response


def normalise_sfs_number(sfs_number: str) -> str:
    value = sfs_number.strip()
    if ":" not in value:
        raise ValueError(f"Expected SFS number in YYYY:NNN format, got {sfs_number!r}")
    year, number = value.split(":", 1)
    if not year.isdigit() or not number.isdigit():
        raise ValueError(f"Invalid SFS number: {sfs_number!r}")
    return f"{int(year)}:{int(number)}"


def slug_for_sfs_number(sfs_number: str) -> str:
    year, number = normalise_sfs_number(sfs_number).split(":", 1)
    return f"sfs-{year}-{number}"


def document_list_url(sfs_number: str) -> str:
    return f"{BASE_URL}/dokumentlista/?sok={quote_plus(normalise_sfs_number(sfs_number))}&doktyp=sfs&utformat=json"


def document_text_url(sfs_number: str) -> str:
    return f"{BASE_URL}/dokument/{slug_for_sfs_number(sfs_number)}.text"


def document_html_url(sfs_number: str) -> str:
    return f"{BASE_URL}/dokument/{slug_for_sfs_number(sfs_number)}.html"


def fetch_document_list(sfs_number: str) -> dict[str, Any]:
    response = _get(document_list_url(sfs_number), accept="application/json")
    return response.json()


def fetch_document_text(sfs_number: str) -> str:
    response = _get(document_text_url(sfs_number), accept="text/plain")
    return response.text


def fetch_document_html(sfs_number: str) -> str:
    response = _get(document_html_url(sfs_number), accept="text/html")
    return response.text


def save_text(path: str | Path, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def save_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
