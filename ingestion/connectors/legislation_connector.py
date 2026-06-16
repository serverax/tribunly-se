"""Legislation.gov.uk connector."""

from __future__ import annotations

from typing import Any

from ingestion.connectors.base import SourceConnector


class LegislationConnector(SourceConnector):
    source_type = "legislation"

    def fetch(self, **kwargs: Any) -> dict:
        return {"mode": "batch", "script": "ingestion.legislation.ingest"}

    def normalise(self, raw: Any) -> dict:
        return {
            "source_type": self.source_type,
            "authority_ref": raw.get("authority_ref", "legislation.gov.uk"),
            "content_hash": raw.get("content_hash"),
            "payload": raw,
        }

    def ingest(self, normalised: dict) -> dict:
        from ingestion.legislation import ingest as leg_ingest

        leg_ingest.ingest_all()
        return {"status": "ok", "connector": self.source_type}
