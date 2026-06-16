"""ACAS guidance connector."""

from __future__ import annotations

from typing import Any

from ingestion.connectors.base import SourceConnector


class AcasConnector(SourceConnector):
    source_type = "acas_guidance"

    def fetch(self, **kwargs: Any) -> dict:
        return {"mode": "batch", "script": "ingestion.acas.ingest"}

    def normalise(self, raw: Any) -> dict:
        return {
            "source_type": self.source_type,
            "authority_ref": raw.get("authority_ref", "acas.org.uk"),
            "content_hash": raw.get("content_hash"),
            "payload": raw,
        }

    def ingest(self, normalised: dict) -> dict:
        from ingestion.acas import ingest as acas_ingest

        acas_ingest.ingest_all()
        return {"status": "ok", "connector": self.source_type}
