"""Perpetual Law Brain — ingestion orchestrator.

Workflow: validate domain (whitelist) -> critic gate -> graph link -> chunk+embed
-> audit. Idempotent (chunk_hash + content-hash change detection). Every run is
logged to corpus_ingestion_runs; every rejection/failure to corpus_ingestion_errors.

NON-NEGOTIABLE: a document that fails the critic "does not exist" to the system —
it is never graph-linked, chunked, or embedded. No AI-generated legal authority.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from backend.core.agentic.ingestion_critic import IngestionCritic, IngestionDoc
from backend.core.ingestion.crawler import WhitelistCrawler, assert_whitelisted
from backend.core.ingestion.embedder import CorpusEmbedder
from backend.core.ingestion.graph_linker import GraphLinker

logger = logging.getLogger(__name__)


def _get_conn():
    from ingestion.db import get_connection
    return get_connection()


class PerpetualLawBrain:
    def __init__(self, critic: Optional[IngestionCritic] = None,
                 linker: Optional[GraphLinker] = None,
                 embedder: Optional[CorpusEmbedder] = None,
                 crawler: Optional[WhitelistCrawler] = None,
                 get_conn: Callable = _get_conn) -> None:
        self.critic = critic or IngestionCritic()
        self.linker = linker or GraphLinker()
        self.embedder = embedder or CorpusEmbedder()
        self.crawler = crawler or WhitelistCrawler()
        self._get_conn = get_conn

    # ── audit helpers ────────────────────────────────────────────────────────
    def _start_run(self, conn) -> str:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO corpus_ingestion_runs (domain, run_kind, status)
                   VALUES ('employment_uk','perpetual_law_brain','running') RETURNING id""")
            run_id = cur.fetchone()[0]
        conn.commit()
        return str(run_id)

    def _finish_run(self, conn, run_id: str, *, status: str, rows_ingested: int,
                    rows_rejected: int, validation_passed: bool,
                    failures: Optional[list] = None) -> None:
        import json
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE corpus_ingestion_runs
                   SET status=%s, completed_at=now(), rows_ingested=%s, rows_rejected=%s,
                       validation_passed=%s, failures=%s
                   WHERE id=%s::uuid""",
                (status, rows_ingested, rows_rejected, validation_passed,
                 json.dumps(failures or []), run_id),
            )
        conn.commit()

    def _log_error(self, conn, run_id: str, source_url: str, error_type: str,
                   error_message: str) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO corpus_ingestion_errors
                   (ingestion_run_id, domain, source_url, error_type, error_message, retryable)
                   VALUES (%s::uuid,'employment_uk',%s,%s,%s,false)""",
                (run_id, source_url, error_type, error_message[:1000]),
            )
        conn.commit()

    # ── main entry ───────────────────────────────────────────────────────────
    def ingest_document(self, doc: IngestionDoc, *, node_id: str, node_type: str,
                        label: str, links: Optional[list[dict]] = None,
                        embed: bool = True) -> dict:
        """Run one document through critic -> graph -> embed, fully audited.
        Returns a dict with status 'ingested' or 'rejected' and the run_id."""
        conn = self._get_conn()
        try:
            run_id = self._start_run(conn)

            # Gate 1 — critic (structure + provenance). Reject => does not exist.
            verdict = self.critic.validate(doc)
            if not verdict.passed:
                self._log_error(conn, run_id, doc.source_url, "critic_rejected", verdict.reason)
                self._finish_run(conn, run_id, status="failed", rows_ingested=0,
                                 rows_rejected=1, validation_passed=False,
                                 failures=[verdict.reason])
                return {"status": "rejected", "reason": verdict.reason,
                        "checks": verdict.checks, "run_id": run_id}

            # Gate 2 — graph link (provenance-bound edges only).
            link = self.linker.integrate(
                node_id=node_id, node_type=node_type, label=label,
                jurisdiction=doc.jurisdiction_code, source_url=doc.source_url, links=links)

            # Gate 3 — embed ONLY now that critic + graph approved.
            emb = self.embedder.store(
                source_url=doc.source_url, authority_ref=doc.authority_ref,
                jurisdiction_code=doc.jurisdiction_code, body_text=doc.content,
                title=doc.title, source_type=doc.source_type,
                ingestion_run_id=run_id, embed=embed)
            # content-hash change detection: stale-out superseded chunks.
            stale = self.embedder.mark_stale(doc.source_url, emb.chunk_hashes)

            self._finish_run(conn, run_id, status="passed",
                             rows_ingested=emb.chunks_written, rows_rejected=0,
                             validation_passed=True)
            return {
                "status": "ingested", "run_id": run_id,
                "node_id": node_id, "node_upserted": link.node_upserted,
                "edges_created": link.edges_created, "unresolved": link.unresolved,
                "chunks_written": emb.chunks_written, "stale_marked": stale,
            }
        finally:
            conn.close()

    def ingest_url(self, url: str, *, node_id: str, node_type: str, label: str,
                   source_type: str, parser_type: str, jurisdiction_code: str,
                   authority_ref: str, links: Optional[list[dict]] = None) -> dict:
        """Fetch (whitelist-enforced) then ingest. Network — not used in unit tests."""
        assert_whitelisted(url)
        fetched = self.crawler.fetch(url)
        doc = IngestionDoc(
            source_url=fetched.final_url, source_type=source_type, parser_type=parser_type,
            jurisdiction_code=jurisdiction_code, authority_ref=authority_ref,
            content=fetched.content, title=label)
        return self.ingest_document(doc, node_id=node_id, node_type=node_type,
                                    label=label, links=links)
