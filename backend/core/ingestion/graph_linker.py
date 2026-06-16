"""Graph linker  -  Perpetual Law Brain stage 3.

Maps an approved legal document into the knowledge graph: upserts a legal_node for
the document and creates legal_edges to EXISTING nodes it cites. Edges are only
created when (a) the target node already exists and (b) provenance (source_url) is
present. Unresolved links are logged, never silently fabricated.

This does NOT decide law. It records citation/provenance relationships only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ALLOWED_RELATIONSHIPS = {
    "cites", "amends", "explains", "applies", "same_topic", "source_of_rule",
}


@dataclass
class LinkResult:
    node_id: str
    node_upserted: bool
    edges_created: list[dict] = field(default_factory=list)
    unresolved: list[dict] = field(default_factory=list)


def _get_conn():
    from ingestion.db import get_connection
    return get_connection()


class GraphLinker:
    def __init__(self, get_conn: Callable = _get_conn) -> None:
        self._get_conn = get_conn

    def node_exists(self, conn, node_id: str, jurisdiction: str) -> bool:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM legal_nodes WHERE node_id=%s AND jurisdiction=%s AND is_active=true",
                (node_id, jurisdiction),
            )
            return cur.fetchone() is not None

    def upsert_node(self, conn, node_id: str, node_type: str, label: str,
                    jurisdiction: str, source_url: str, authority_level: int = 1,
                    description: str = "") -> bool:
        """Insert the node if absent (idempotent). Returns True if a row was written."""
        if not source_url:
            raise ValueError("refusing to create a legal_node without source_url (provenance)")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM legal_nodes WHERE node_id=%s AND jurisdiction=%s",
                (node_id, jurisdiction),
            )
            if cur.fetchone():
                return False
            cur.execute(
                """
                INSERT INTO legal_nodes
                    (node_id, node_type, label, description, jurisdiction,
                     authority_level, source_ref, source_url, is_active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,true)
                """,
                (node_id, node_type, label, description, jurisdiction,
                 authority_level, label, source_url),
            )
            return True

    def link(self, conn, from_node_id: str, to_node_id: str, relationship_type: str,
             jurisdiction: str, source_url: str) -> bool:
        """Create an edge to an EXISTING target, with provenance. Idempotent.
        Returns True if an edge row was written; False if the target is unresolved
        or the edge already exists."""
        if relationship_type not in ALLOWED_RELATIONSHIPS:
            raise ValueError(f"relationship_type not allowed: {relationship_type}")
        if not source_url:
            raise ValueError("refusing to create a legal_edge without provenance (source_url)")
        if not self.node_exists(conn, to_node_id, jurisdiction):
            return False  # unresolved  -  caller logs it
        with conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM legal_edges
                   WHERE from_node_id=%s AND to_node_id=%s AND relationship_type=%s AND jurisdiction=%s""",
                (from_node_id, to_node_id, relationship_type, jurisdiction),
            )
            if cur.fetchone():
                return False
            cur.execute(
                """
                INSERT INTO legal_edges
                    (from_node_id, to_node_id, relationship_type, weight, jurisdiction, notes)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (from_node_id, to_node_id, relationship_type, 1.0, jurisdiction,
                 f"provenance:{source_url}"),
            )
            return True

    def integrate(self, node_id: str, node_type: str, label: str, jurisdiction: str,
                  source_url: str, links: Optional[list[dict]] = None,
                  authority_level: int = 1) -> LinkResult:
        """Upsert the document node and create edges for every resolvable link.
        links: [{"to": node_id, "rel": relationship_type}]. Unresolved targets are
        logged and returned, never invented."""
        links = links or []
        conn = self._get_conn()
        try:
            upserted = self.upsert_node(conn, node_id, node_type, label, jurisdiction,
                                        source_url, authority_level)
            result = LinkResult(node_id=node_id, node_upserted=upserted)
            for ln in links:
                to_id, rel = ln.get("to"), ln.get("rel", "cites")
                created = self.link(conn, node_id, to_id, rel, jurisdiction, source_url)
                if created:
                    result.edges_created.append({"to": to_id, "rel": rel})
                else:
                    if not self.node_exists(conn, to_id, jurisdiction):
                        result.unresolved.append({"to": to_id, "rel": rel})
                        logger.info("graph_linker: unresolved link %s -[%s]-> %s", node_id, rel, to_id)
            conn.commit()
            return result
        finally:
            conn.close()
