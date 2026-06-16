"""Worker A: legislation.gov.uk CLML fetch, chunk, embed, optional Neo4j Act/Section nodes."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ingestion.workers.base_worker import QUEUE_LEGISLATION, BaseWorker, RedisQueue
from ingestion.workers.unified_indexer import UnifiedIndexer

logger = logging.getLogger(__name__)


class LegislationWorker(BaseWorker):
    worker_type = "legislation"
    queue_name = QUEUE_LEGISLATION

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = payload.get("job_id", str(uuid.uuid4()))
        section = payload.get("section")
        act_meta = payload.get("act_meta") or {}
        run_full = payload.get("run_full", False)

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
                from ingestion.legislation.ingest import ingest_all
                ingest_all()
                status = "done"
            elif section and act_meta:
                from ingestion.legislation.ingest import _ingest_section
                errors: list[str] = []
                total = [0]
                _ingest_section(
                    act_meta.get("leg_type", "ukpga"),
                    int(act_meta.get("year", 1996)),
                    str(act_meta.get("chapter", "18")),
                    str(section),
                    act_meta.get("act_title", "Employment Rights Act 1996"),
                    bool(act_meta.get("prospective", False)),
                    total,
                    errors,
                )
                status = "done" if not errors else "failed"
            else:
                status = "skipped"

            indexer = UnifiedIndexer()
            indexed = indexer.index_pending_legislation(limit=payload.get("index_limit", 50))

            neo4j_status = "skipped"
            if indexer.neo4j_enabled and indexed.get("graph_entities"):
                neo4j_status = "done" if indexed.get("neo4j_ok") else "failed"

            with conn.cursor() as cur:
                self._record_job(
                    cur,
                    job_id=job_id,
                    document_id=payload.get("document_id"),
                    chunk_id=payload.get("chunk_id"),
                    postgres_status=status,
                    neo4j_status=neo4j_status,
                    metadata={"indexed": indexed},
                )
            conn.commit()
            return {"status": status, "indexed": indexed}
        finally:
            conn.close()


def enqueue_legislation_job(**kwargs: Any) -> str:
    return RedisQueue(QUEUE_LEGISLATION).enqueue(kwargs)
