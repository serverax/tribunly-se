"""Redis list queue primitives and base worker for ingestion jobs."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)

QUEUE_LEGISLATION = "ingestion-legislation"
QUEUE_CASE_LAW = "ingestion-case-law"
QUEUE_ACAS = "ingestion-acas"
QUEUE_EMBEDDING = "embedding-jobs"
QUEUE_GRAPH = "graph-build-jobs"

ALL_QUEUES = (
    QUEUE_LEGISLATION,
    QUEUE_CASE_LAW,
    QUEUE_ACAS,
    QUEUE_EMBEDDING,
    QUEUE_GRAPH,
)


def redis_url() -> str:
    return os.getenv("REDIS_URL", os.getenv("RATELIMIT_STORAGE_URI", "redis://redis:6379"))


class RedisQueue:
    """Simple Redis list queue (LPUSH / BRPOP)."""

    def __init__(self, name: str, url: Optional[str] = None) -> None:
        self.name = name
        self._url = url or redis_url()
        self._client = None

    def _conn(self):
        if self._client is None:
            import redis
            self._client = redis.from_url(self._url, decode_responses=True)
        return self._client

    def enqueue(self, payload: dict[str, Any]) -> str:
        job_id = payload.get("job_id") or str(uuid.uuid4())
        payload = {**payload, "job_id": job_id}
        self._conn().lpush(self.name, json.dumps(payload))
        return job_id

    def dequeue(self, timeout: int = 5) -> Optional[dict[str, Any]]:
        item = self._conn().brpop(self.name, timeout=timeout)
        if not item:
            return None
        _, raw = item
        return json.loads(raw)

    def depth(self) -> int:
        return int(self._conn().llen(self.name))


class BaseWorker(ABC):
    worker_type: str = "base"
    queue_name: str = QUEUE_LEGISLATION

    def __init__(self) -> None:
        self.queue = RedisQueue(self.queue_name)

    def _record_job(
        self,
        cur: Any,
        *,
        job_id: str,
        document_id: Optional[str],
        chunk_id: Optional[str],
        postgres_status: str,
        neo4j_status: str = "skipped",
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        cur.execute(
            """
            INSERT INTO ingestion_jobs (
                id, worker_type, queue_name, document_id, chunk_id,
                postgres_status, neo4j_status, error_message, metadata
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                postgres_status = EXCLUDED.postgres_status,
                neo4j_status = EXCLUDED.neo4j_status,
                error_message = EXCLUDED.error_message,
                metadata = EXCLUDED.metadata,
                updated_at = now()
            """,
            (
                job_id,
                self.worker_type,
                self.queue_name,
                document_id,
                chunk_id,
                postgres_status,
                neo4j_status,
                error_message,
                json.dumps(metadata or {}),
            ),
        )

    @abstractmethod
    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process one queue message. Return result metadata."""

    def run_once(self) -> bool:
        payload = self.queue.dequeue(timeout=2)
        if not payload:
            return False
        job_id = payload.get("job_id", str(uuid.uuid4()))
        try:
            result = self.process(payload)
            logger.info("Worker %s job %s done: %s", self.worker_type, job_id, result.get("status"))
        except Exception as exc:
            logger.exception("Worker %s job %s failed", self.worker_type, job_id)
            try:
                from ingestion.db import get_connection
                conn = get_connection()
                with conn.cursor() as cur:
                    self._record_job(
                        cur,
                        job_id=job_id,
                        document_id=payload.get("document_id"),
                        chunk_id=payload.get("chunk_id"),
                        postgres_status="failed",
                        neo4j_status="skipped",
                        error_message=str(exc)[:500],
                    )
                conn.commit()
                conn.close()
            except Exception:
                pass
        return True

    def run_forever(self, poll_interval: float = 0.5) -> None:
        logger.info("Starting worker %s on queue %s", self.worker_type, self.queue_name)
        while True:
            if not self.run_once():
                time.sleep(poll_interval)
