"""Worker C: ACAS guidance ingestion."""

from __future__ import annotations

import uuid
from typing import Any

from ingestion.workers.base_worker import QUEUE_ACAS, BaseWorker


class AcasWorker(BaseWorker):
    worker_type = "acas"
    queue_name = QUEUE_ACAS

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = payload.get("job_id", str(uuid.uuid4()))
        run_full = payload.get("run_full", True)

        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                self._record_job(
                    cur,
                    job_id=job_id,
                    document_id=payload.get("document_id"),
                    chunk_id=None,
                    postgres_status="processing",
                )
            conn.commit()

            if run_full:
                from ingestion.acas.ingest import ingest_all
                ingest_all()

            from ingestion.workers.unified_indexer import UnifiedIndexer
            indexed = UnifiedIndexer().index_pending_acas(limit=payload.get("index_limit", 50))

            with conn.cursor() as cur:
                self._record_job(
                    cur,
                    job_id=job_id,
                    document_id=payload.get("document_id"),
                    chunk_id=None,
                    postgres_status="done",
                    metadata={"indexed": indexed},
                )
            conn.commit()
            return {"status": "done", "indexed": indexed}
        finally:
            conn.close()
