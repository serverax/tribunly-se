"""Worker D: deterministic rule candidates to knowledge.ingestion_proposals (never direct rules write)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from ingestion.workers.base_worker import QUEUE_GRAPH, BaseWorker, RedisQueue


class RulesCompilerWorker(BaseWorker):
    worker_type = "rules_compiler"
    queue_name = QUEUE_GRAPH

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = payload.get("job_id", str(uuid.uuid4()))
        candidates = payload.get("rule_candidates") or []

        if not candidates and payload.get("compile_from_rules_table"):
            candidates = self._compile_from_existing_rules()

        from ingestion.db import get_connection

        conn = get_connection()
        inserted = 0
        try:
            with conn.cursor() as cur:
                self._record_job(
                    cur,
                    job_id=job_id,
                    document_id=payload.get("document_id"),
                    chunk_id=payload.get("chunk_id"),
                    postgres_status="processing",
                )
                for cand in candidates:
                    cur.execute(
                        """
                        INSERT INTO knowledge.ingestion_proposals (
                            proposal_type, source_worker, document_id, chunk_id, payload
                        ) VALUES ('rule_candidate', 'rules_compiler', %s, %s, %s::jsonb)
                        """,
                        (
                            payload.get("document_id"),
                            payload.get("chunk_id"),
                            json.dumps(cand),
                        ),
                    )
                    inserted += 1
                self._record_job(
                    cur,
                    job_id=job_id,
                    document_id=payload.get("document_id"),
                    chunk_id=payload.get("chunk_id"),
                    postgres_status="done",
                    metadata={"proposals_inserted": inserted},
                )
            conn.commit()
            return {"status": "done", "proposals_inserted": inserted}
        finally:
            conn.close()

    def _compile_from_existing_rules(self) -> list[dict[str, Any]]:
        """Read rules table and emit proposal snapshots for reviewer diff (no writes to rules)."""
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT rule_key, claim_type, value_numeric, value_text, unit,
                           authority_ref, authority_url, effective_from
                    FROM rules
                    WHERE is_prospective = false
                    ORDER BY rule_key
                    LIMIT 20
                    """
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        return [
            {
                "rule_key": r["rule_key"],
                "claim_type": r["claim_type"],
                "value_numeric": r["value_numeric"],
                "value_text": r["value_text"],
                "unit": r["unit"],
                "authority_ref": r["authority_ref"],
                "authority_url": r["authority_url"],
                "effective_from": str(r["effective_from"]) if r["effective_from"] else None,
                "proposal_note": "snapshot_for_reviewer_diff",
            }
            for r in rows
        ]


def enqueue_graph_build(payload: dict[str, Any]) -> str:
    return RedisQueue(QUEUE_GRAPH).enqueue(payload)
