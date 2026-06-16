"""Legal record normaliser for ingestion pipeline."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def normalise_record(record: dict) -> dict:
    """Normalise connector output to a stable ingestion shape."""
    body = record.get("body_text") or record.get("text") or json.dumps(record.get("payload", {}))
    content_hash = record.get("content_hash") or hashlib.sha256(body.encode()).hexdigest()
    return {
        "source_type": record.get("source_type", "unknown"),
        "authority_ref": record.get("authority_ref", ""),
        "title": record.get("title", ""),
        "body_text": body[:50000] if isinstance(body, str) else str(body)[:50000],
        "content_hash": content_hash,
        "jurisdiction": record.get("jurisdiction", "EW"),
        "source_url": record.get("source_url"),
    }
