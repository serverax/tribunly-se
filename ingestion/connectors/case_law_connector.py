"""Find Case Law connector (sample-only per FCL licence)."""

from __future__ import annotations

from typing import Any

from ingestion.connectors.base import SourceConnector
from ingestion.config import settings


class CaseLawConnector(SourceConnector):
    source_type = "case_law"

    def fetch(self, **kwargs: Any) -> dict:
        if settings.fcl_bulk_licence_granted:
            return {"mode": "bulk", "licence": True}
        return {"mode": "sample", "licence": False, "script": "ingestion.case_law.ingest --sample"}

    def normalise(self, raw: Any) -> dict:
        return {
            "source_type": self.source_type,
            "authority_ref": raw.get("authority_ref", "caselaw.nationalarchives.gov.uk"),
            "content_hash": raw.get("content_hash"),
            "mode": raw.get("mode", "sample"),
            "payload": raw,
        }

    def ingest(self, normalised: dict) -> dict:
        from ingestion.case_law import ingest as cl_ingest

        if normalised.get("mode") == "bulk" and settings.fcl_bulk_licence_granted:
            cl_ingest.ingest_bulk()
        else:
            cl_ingest.ingest_sample()
        return {"status": "ok", "connector": self.source_type, "mode": normalised.get("mode", "sample")}
