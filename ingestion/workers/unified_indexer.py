"""Dual-write coordinator: Postgres+pgvector always; Neo4j optional (NEO4J_ENABLED)."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _canonical_node_type(raw_type: str | None) -> str:
    mapping = {
        "section": "legislation_section",
        "statute": "legislation_section",
        "act": "legislation_section",
        "guidance": "procedure",
        "legaltest": "legal_test",
        "legal_test": "legal_test",
        "concept": "concept",
        "case": "concept",
    }
    valid = {
        "claim_type", "legal_test", "procedure", "deadline",
        "remedy", "defence", "evidence_type", "legislation_section", "concept",
    }
    key = str(raw_type or "section").strip().replace("-", "_").replace(" ", "_").lower()
    return mapping.get(key, key if key in valid else "concept")


class UnifiedIndexer:
    """Coordinates document_id, chunk_id, embedding, graph_entities, graph_edges, rule_candidates."""

    def __init__(self) -> None:
        self.neo4j_enabled = os.getenv("NEO4J_ENABLED", "false").lower() in ("1", "true", "yes")

    def index_chunk(
        self,
        *,
        document_id: str,
        chunk_id: str,
        body_text: str,
        source_type: str,
        source_url: str,
        authority_ref: str,
        embedding: Optional[list[float]] = None,
        graph_entities: Optional[list[dict]] = None,
        graph_edges: Optional[list[dict]] = None,
        rule_candidates: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        postgres_ok = self._write_postgres(
            document_id=document_id,
            chunk_id=chunk_id,
            body_text=body_text,
            source_type=source_type,
            source_url=source_url,
            authority_ref=authority_ref,
            embedding=embedding,
        )
        proposals = 0
        postgres_graph_ok = False
        neo4j_ok = False
        if graph_entities or graph_edges:
            postgres_graph_ok = self._write_postgres_graph(
                graph_entities=graph_entities or [],
                graph_edges=graph_edges or [],
                source_url=source_url,
            )

        if self.neo4j_enabled and (graph_entities or graph_edges):
            from ingestion.graph.neo4j_batch_writer import Neo4jBatchWriter
            neo4j_ok = Neo4jBatchWriter().write_batch(graph_entities or [], graph_edges or [])

        if rule_candidates:
            try:
                proposals = self._queue_proposals(
                    document_id, chunk_id, rule_candidates, source_worker="unified_indexer"
                )
            except Exception as exc:
                logger.debug("proposal queue skipped: %s", exc)

        if graph_entities or graph_edges:
            try:
                from ingestion.workers.base_worker import RedisQueue, QUEUE_GRAPH
                RedisQueue(QUEUE_GRAPH).enqueue({
                    "job_id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "graph_entities": graph_entities or [],
                    "graph_edges": graph_edges or [],
                    "rule_candidates": rule_candidates or [],
                })
            except Exception as exc:
                logger.debug("graph queue enqueue skipped: %s", exc)

        return {
            "postgres_ok": postgres_ok,
            "postgres_graph_ok": postgres_graph_ok,
            "neo4j_ok": neo4j_ok,
            "neo4j_enabled": self.neo4j_enabled,
            "graph_entities": graph_entities or [],
            "graph_edges": graph_edges or [],
            "proposals_queued": proposals,
        }

    def _write_postgres(
        self,
        *,
        document_id: str,
        chunk_id: str,
        body_text: str,
        source_type: str,
        source_url: str,
        authority_ref: str,
        embedding: Optional[list[float]],
    ) -> bool:
        """Postgres is always written via corpus_chunks sync (authoritative plane)."""
        try:
            from ingestion.sync_corpus_chunks import sync_corpus_chunks
            stats = sync_corpus_chunks()
            return stats.get("after", 0) >= stats.get("before", 0)
        except Exception as exc:
            logger.warning("Postgres sync failed for %s: %s", chunk_id, exc)
            return False

    def _write_postgres_graph(
        self,
        *,
        graph_entities: list[dict],
        graph_edges: list[dict],
        source_url: str,
        jurisdiction: str = "EW",
    ) -> bool:
        """Primary graph plane: legal_nodes / legal_edges in Postgres (Neo4j optional only)."""
        if not graph_entities and not graph_edges:
            return True
        try:
            from backend.core.ingestion.graph_linker import GraphLinker

            linker = GraphLinker()
            conn = linker._get_conn()
            try:
                for ent in graph_entities:
                    node_id = ent.get("id") or ent.get("node_id")
                    if not node_id:
                        continue
                    linker.upsert_node(
                        conn,
                        node_id=str(node_id),
                        node_type=_canonical_node_type(ent.get("type")),
                        label=str(ent.get("label") or ent.get("authority_ref") or node_id),
                        jurisdiction=str(ent.get("jurisdiction") or jurisdiction),
                        source_url=source_url,
                        description=str(ent.get("description") or ""),
                    )
                for edge in graph_edges:
                    frm = edge.get("from") or edge.get("from_node_id")
                    to = edge.get("to") or edge.get("to_node_id")
                    rel = edge.get("rel") or edge.get("relationship_type") or "cites"
                    if frm and to:
                        linker.link(conn, str(frm), str(to), str(rel), jurisdiction, source_url)
                conn.commit()
            finally:
                conn.close()
            return True
        except Exception as exc:
            logger.warning("Postgres graph write failed: %s", exc)
            return False

    def _queue_proposals(
        self,
        document_id: str,
        chunk_id: str,
        candidates: list[dict],
        source_worker: str,
    ) -> int:
        import json
        from ingestion.db import get_connection

        conn = get_connection()
        count = 0
        try:
            with conn.cursor() as cur:
                for cand in candidates:
                    cur.execute(
                        """
                        INSERT INTO knowledge.ingestion_proposals (
                            proposal_type, source_worker, document_id, chunk_id, payload
                        ) VALUES ('rule_candidate', %s, %s, %s, %s::jsonb)
                        """,
                        (source_worker, document_id, chunk_id, json.dumps(cand)),
                    )
                    count += 1
            conn.commit()
        finally:
            conn.close()
        return count

    def index_pending_legislation(self, limit: int = 50) -> dict[str, Any]:
        from ingestion.db import get_connection

        conn = get_connection()
        indexed = 0
        neo4j_ok = True
        graph_entities: list[dict] = []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_url, chunk_index, section_ref, body_text, act_title
                    FROM legislation
                    WHERE embedding IS NOT NULL
                    ORDER BY last_verified_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
            for row in rows:
                doc_id = row["source_url"]
                chunk_id = f"{doc_id}#chunk-{row['chunk_index']}"
                entities = [{
                    "id": chunk_id,
                    "type": "Section",
                    "label": row.get("section_ref") or row.get("act_title", ""),
                    "authority_ref": row.get("section_ref") or "",
                }]
                result = self.index_chunk(
                    document_id=doc_id,
                    chunk_id=chunk_id,
                    body_text=row["body_text"],
                    source_type="legislation",
                    source_url=row["source_url"],
                    authority_ref=row.get("section_ref") or "",
                    graph_entities=entities,
                )
                indexed += 1
                graph_entities.extend(entities)
                neo4j_ok = neo4j_ok and (not self.neo4j_enabled or result.get("neo4j_ok", False))
        finally:
            conn.close()
        return {"indexed": indexed, "graph_entities": graph_entities, "neo4j_ok": neo4j_ok}

    def index_pending_acas(self, limit: int = 50) -> dict[str, Any]:
        from ingestion.db import get_connection

        conn = get_connection()
        indexed = 0
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_url, chunk_index, doc_title, body_text
                    FROM acas_guidance
                    ORDER BY last_verified_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
            for row in rows:
                doc_id = row["source_url"]
                chunk_id = f"{doc_id}#chunk-{row['chunk_index']}"
                self.index_chunk(
                    document_id=doc_id,
                    chunk_id=chunk_id,
                    body_text=row["body_text"],
                    source_type="acas_guidance",
                    source_url=row["source_url"],
                    authority_ref=row.get("doc_title") or "",
                )
                indexed += 1
        finally:
            conn.close()
        return {"indexed": indexed}
