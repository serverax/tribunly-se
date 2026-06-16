"""Worker B: Find Case Law sample-only (FCL bulk blocked unless licence granted)."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from ingestion.workers.base_worker import QUEUE_CASE_LAW, BaseWorker

logger = logging.getLogger(__name__)

# Sample URIs for fixture/testing only. Bulk embedding requires FCL licence.
SAMPLE_CASE_URIS = [
    "https://caselaw.nationalarchives.gov.uk/ewca/civ/2017/1671",
]


class CaseLawWorker(BaseWorker):
    worker_type = "case_law"
    queue_name = QUEUE_CASE_LAW

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = payload.get("job_id", str(uuid.uuid4()))
        bulk = bool(payload.get("bulk", False))
        fcl_granted = os.getenv("FCL_BULK_LICENCE_GRANTED", "false").lower() in ("1", "true", "yes")

        if bulk and not fcl_granted:
            logger.warning("FCL bulk ingestion blocked: licence not granted")
            from ingestion.db import get_connection
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    self._record_job(
                        cur,
                        job_id=job_id,
                        document_id=None,
                        chunk_id=None,
                        postgres_status="skipped",
                        error_message="FCL_BULK_LICENCE_GRANTED=false",
                        metadata={"reason": "sample_only_boundary"},
                    )
                conn.commit()
            finally:
                conn.close()
            return {"status": "skipped", "reason": "fcl_bulk_blocked"}

        if bulk and fcl_granted:
            from ingestion.case_law.ingest import ingest_bulk
            ingest_bulk(max_pages=payload.get("max_pages", 1))
            uris = ["bulk"]
        else:
            from ingestion.case_law.ingest import ingest_sample
            ingest_sample()
            uris = SAMPLE_CASE_URIS[:1]

        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                self._record_job(
                    cur,
                    job_id=job_id,
                    document_id=uris[0] if uris else None,
                    chunk_id=None,
                    postgres_status="done",
                    metadata={"sample_count": len(uris), "bulk": bulk and fcl_granted},
                )
            conn.commit()
        finally:
            conn.close()
        return {"status": "done", "uris_processed": len(uris)}
