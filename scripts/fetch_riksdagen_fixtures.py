"""Fetch and save the Swedish Riksdagen fixtures used by the SE parser tests."""

from __future__ import annotations

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ingestion.riksdagen.client import (
    document_html_url,
    document_list_url,
    document_text_url,
    normalise_sfs_number,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = ROOT / "tests" / "fixtures" / "riksdagen"
TARGETS = {
    "1982:80": {
        "title": "Lag (1982:80) om anställningsskydd",
        "amendment_effective_from": "2022-10-01",
    },
    "1976:580": {
        "title": "Lag (1976:580) om medbestämmande i arbetslivet",
    },
    "2008:567": {
        "title": "Diskrimineringslag (2008:567)",
    },
}


def _throttle(seconds: float = 1.1) -> None:
    time.sleep(seconds)


def _fetch(url: str, accept: str) -> tuple[str, str]:
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(url, headers={"Accept": accept})
    response.raise_for_status()
    return response.text, response.headers.get("content-type", "")


def _listing_item(listing: dict, expected_title: str) -> dict:
    docs = listing.get("dokumentlista", {}).get("dokument", [])
    if isinstance(docs, dict):
        docs = [docs]
    matches = [doc for doc in docs if str(doc.get("titel") or "") == expected_title]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one exact listing match for {expected_title!r}, found {len(matches)}")
    return matches[0]


def _write_bundle(sfs_number: str, target: dict[str, str]) -> None:
    sfs_number = normalise_sfs_number(sfs_number)
    slug = f"sfs-{sfs_number.replace(':', '-')}"
    bundle_dir = FIXTURES_ROOT / slug
    bundle_dir.mkdir(parents=True, exist_ok=True)

    listing_text, listing_content_type = _fetch(document_list_url(sfs_number), "application/json")
    listing = json.loads(listing_text)
    item = _listing_item(listing, target["title"])

    text, text_content_type = _fetch(document_text_url(sfs_number), "text/plain")
    _throttle()
    html, html_content_type = _fetch(document_html_url(sfs_number), "text/html")

    metadata = {
        "beteckning": sfs_number,
        "titel": item.get("titel"),
        "undertitel": item.get("undertitel"),
        "datum": item.get("datum"),
        "publicerad": item.get("publicerad"),
        "systemdatum": item.get("systemdatum"),
        "dokument_url_text": f"https://data.riksdagen.se/dokument/{slug}.text",
        "dokument_url_html": f"https://data.riksdagen.se/dokument/{slug}.html",
        "amendment_effective_from": target.get("amendment_effective_from"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "listing_url": document_list_url(sfs_number),
        "text_url": document_text_url(sfs_number),
        "html_url": document_html_url(sfs_number),
        "content_types": {
            "listing": listing_content_type,
            "text": text_content_type,
            "html": html_content_type,
        },
    }

    (bundle_dir / "listing.json").write_text(json.dumps(listing, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle_dir / "text.txt").write_text(text, encoding="utf-8")
    (bundle_dir / "html.html").write_text(html, encoding="utf-8")


def main() -> None:
    for sfs_number, target in TARGETS.items():
        _write_bundle(sfs_number, target)
        _throttle()


if __name__ == "__main__":
    main()
