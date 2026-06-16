"""
Ingestion manager  -  coordinates connectors and quarantine queue.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IngestionManager:
    """Coordinate source connectors; quarantine on validation failure."""

    def __init__(self) -> None:
        self._connectors: dict[str, Any] = {}

    def register_connector(self, name: str, connector: Any) -> None:
        self._connectors[name] = connector

    def list_connectors(self) -> list[str]:
        return list(self._connectors.keys())

    def quarantine(
        self,
        *,
        connector: str,
        source_type: str,
        raw_payload: dict,
        validation_errors: list[str],
        authority_ref: Optional[str] = None,
        content_hash: Optional[str] = None,
    ) -> Optional[str]:
        qid = str(uuid.uuid4())
        try:
            from ingestion.db import get_connection

            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO knowledge.quarantine_queue (
                            id, connector, source_type, authority_ref,
                            raw_payload, validation_errors, content_hash
                        ) VALUES (
                            %s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, %s
                        )
                        RETURNING id
                        """,
                        (
                            qid,
                            connector,
                            source_type,
                            authority_ref,
                            json.dumps(raw_payload),
                            json.dumps(validation_errors),
                            content_hash,
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
                return str(row[0]) if row else None
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("Quarantine queue unavailable: %s", exc)
            return None

    def run_connector(self, name: str, **kwargs: Any) -> dict:
        connector = self._connectors.get(name)
        if not connector:
            return {"status": "error", "message": f"unknown connector: {name}"}
        try:
            from ingestion.validation.ingestion_validator import IngestionValidator

            validator = IngestionValidator()
            raw = connector.fetch(**kwargs)
            normalised = connector.normalise(raw)
            verdict = validator.validate(normalised)
            if not verdict.passed:
                qid = self.quarantine(
                    connector=name,
                    source_type=connector.source_type,
                    raw_payload=normalised,
                    validation_errors=verdict.errors,
                    authority_ref=normalised.get("authority_ref"),
                    content_hash=normalised.get("content_hash"),
                )
                return {"status": "quarantined", "quarantine_id": qid, "errors": verdict.errors}
            result = connector.ingest(normalised)
            return {"status": "ok", "result": result}
        except Exception as exc:
            logger.exception("Connector %s failed: %s", name, exc)
            return {"status": "error", "message": str(exc)}

    def run_legislation(self) -> dict:
        """Wire to existing ingestion.legislation.ingest."""
        try:
            from ingestion.legislation import ingest as leg_ingest

            leg_ingest.ingest_all()
            return {"status": "ok", "connector": "legislation"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def run_acas(self) -> dict:
        try:
            from ingestion.acas import ingest as acas_ingest

            acas_ingest.ingest_all()
            return {"status": "ok", "connector": "acas"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def run_case_law_sample(self) -> dict:
        try:
            from ingestion.case_law import ingest as cl_ingest

            cl_ingest.ingest_sample()
            return {"status": "ok", "connector": "case_law", "mode": "sample"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}


def build_default_ingestion_manager() -> IngestionManager:
    from ingestion.connectors.legislation_connector import LegislationConnector
    from ingestion.connectors.acas_connector import AcasConnector
    from ingestion.connectors.case_law_connector import CaseLawConnector

    mgr = IngestionManager()
    mgr.register_connector("legislation", LegislationConnector())
    mgr.register_connector("acas", AcasConnector())
    mgr.register_connector("case_law", CaseLawConnector())
    return mgr
