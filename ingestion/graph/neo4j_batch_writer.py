"""Optional Neo4j batch writer (NEO4J_ENABLED). Postgres graph remains authoritative fallback."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class Neo4jBatchWriter:
    def __init__(self) -> None:
        self.enabled = os.getenv("NEO4J_ENABLED", "false").lower() in ("1", "true", "yes")
        self.uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "lawapp-neo4j-dev")

    def write_batch(self, entities: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bool:
        if not self.enabled:
            return False
        if not entities and not edges:
            return True
        try:
            from neo4j import GraphDatabase
        except ImportError:
            logger.warning("neo4j driver not installed; skipping graph write")
            return False

        driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        try:
            with driver.session() as session:
                for ent in entities:
                    session.run(
                        """
                        MERGE (n:LegalEntity {id: $id})
                        SET n.type = $type, n.label = $label, n.authority_ref = $authority_ref
                        """,
                        id=ent["id"],
                        type=ent.get("type"),
                        label=ent.get("label"),
                        authority_ref=ent.get("authority_ref"),
                    )
                for edge in edges:
                    session.run(
                        """
                        MATCH (a:LegalEntity {id: $from_id}), (b:LegalEntity {id: $to_id})
                        MERGE (a)-[r:REL {relation: $relation}]->(b)
                        SET r.evidence_span = $evidence_span
                        """,
                        from_id=edge["from_id"],
                        to_id=edge["to_id"],
                        relation=edge["relation"],
                        evidence_span=edge.get("evidence_span"),
                    )
            return True
        except Exception as exc:
            logger.warning("Neo4j batch write failed: %s", exc)
            return False
        finally:
            driver.close()
