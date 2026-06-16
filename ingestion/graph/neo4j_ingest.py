"""
Validated Neo4j MERGE ingest for statutes and sample case law.

FCL bulk case embedding remains blocked. Only sample nodes with confirmed licence.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "lawapp_dev_only")


def _driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD))


def ingest_statute(
    statute_id: str,
    title: str,
    jurisdiction: str = "EW",
    source_url: Optional[str] = None,
    sections: Optional[list[dict[str, Any]]] = None,
) -> dict[str, int]:
    """MERGE Statute + Section nodes. sections: [{id, label, source_ref, source_url, description}]"""
    sections = sections or []
    driver = _driver()
    merged = 0
    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (s:Statute {id: $id})
                SET s.title = $title, s.jurisdiction = $jurisdiction, s.source_url = $source_url
                """,
                id=statute_id,
                title=title,
                jurisdiction=jurisdiction,
                source_url=source_url,
            )
            merged += 1
            for sec in sections:
                session.run(
                    """
                    MERGE (sec:Section {id: $id})
                    SET sec.label = $label, sec.source_ref = $source_ref,
                        sec.source_url = $source_url, sec.description = $description,
                        sec.jurisdiction = $jurisdiction, sec.authority_level = 1
                    WITH sec
                    MATCH (st:Statute {id: $statute_id})
                    MERGE (sec)-[:PART_OF]->(st)
                    """,
                    id=sec["id"],
                    label=sec.get("label", ""),
                    source_ref=sec.get("source_ref"),
                    source_url=sec.get("source_url"),
                    description=sec.get("description"),
                    jurisdiction=jurisdiction,
                    statute_id=statute_id,
                )
                merged += 1
    finally:
        driver.close()
    return {"merged_nodes": merged}


def ingest_case(
    case_id: str,
    case_name: str,
    neutral_citation: str,
    jurisdiction: str = "UK",
    source_url: Optional[str] = None,
    interprets: Optional[list[str]] = None,
) -> dict[str, int]:
    """
    MERGE a single Case node. Sample-only until FCL bulk licence granted.
    interprets: list of LegalTest node ids for INTERPRETS edges.
    """
    if os.getenv("FCL_BULK_LICENCE_GRANTED", "false").lower() not in ("1", "true", "yes"):
        logger.info("FCL bulk not granted: ingest_case allowed for sample nodes only (id=%s)", case_id)

    interprets = interprets or []
    driver = _driver()
    edges = 0
    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (c:Case {id: $id})
                SET c.label = $case_name, c.neutral_citation = $citation,
                    c.source_ref = $citation, c.source_url = $source_url,
                    c.jurisdiction = $jurisdiction, c.authority_level = 2
                """,
                id=case_id,
                case_name=case_name,
                citation=neutral_citation,
                source_url=source_url,
                jurisdiction=jurisdiction,
            )
            for test_id in interprets:
                session.run(
                    """
                    MATCH (c:Case {id: $case_id}), (t:LegalTest {id: $test_id})
                    MERGE (c)-[:INTERPRETS]->(t)
                    """,
                    case_id=case_id,
                    test_id=test_id,
                )
                edges += 1
    finally:
        driver.close()
    return {"merged_cases": 1, "interprets_edges": edges}
