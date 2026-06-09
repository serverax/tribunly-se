"""Database connection and helper utilities for the ingestion pipeline."""

from __future__ import annotations

import atexit
import contextlib
import hashlib
import json
import logging
import os
import threading
from typing import Any, Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extensions import connection as PGConnection

from ingestion.config import settings

logger = logging.getLogger(__name__)

# ── Connection pooling (SCALE: 100k concurrent) ───────────────────────────────
# Opening a fresh psycopg2 connection costs ~28ms p50 (measured) and Postgres
# max_connections is finite (~100), so a connect-per-request model collapses the
# auth/RLS hot path (check_case_ownership, /cases) under load and exhausts the DB.
# A process-local ThreadedConnectionPool reuses warm connections so the per-request
# cost drops to the query itself (~1.6ms). For true 100k the deployment ALSO sits
# behind PgBouncer (transaction pooling) with DATABASE_URL → pgbouncer:6432 and the
# API horizontally scaled (HPA); this app-side pool is the per-replica layer.
#
# Tunables (env): DB_POOL_ENABLED (default 1), DB_POOL_MIN (default 1),
# DB_POOL_MAX (default 16). Set DB_POOL_ENABLED=0 to restore connect-per-call.
_pool: "psycopg2.pool.ThreadedConnectionPool | None" = None
_pool_lock = threading.Lock()


def _pool_enabled() -> bool:
    return os.getenv("DB_POOL_ENABLED", "1").lower() not in ("0", "false", "no")


def _get_pool() -> "psycopg2.pool.ThreadedConnectionPool | None":
    """Lazily create the process-local pool. Returns None if pooling is disabled
    or the pool cannot be created (callers then fall back to a direct connect)."""
    global _pool
    if not _pool_enabled():
        return None
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                try:
                    _pool = psycopg2.pool.ThreadedConnectionPool(
                        int(os.getenv("DB_POOL_MIN", "1")),
                        int(os.getenv("DB_POOL_MAX", "16")),
                        settings.database_url,
                    )
                    logger.info(
                        "DB pool initialised (min=%s max=%s)",
                        os.getenv("DB_POOL_MIN", "1"), os.getenv("DB_POOL_MAX", "16"),
                    )
                except Exception as exc:  # pragma: no cover - infra failure path
                    logger.warning("DB pool init failed (%s) — using direct connects", exc)
                    _pool = None
    return _pool


class _PooledConnection:
    """Transparent proxy over a pooled psycopg2 connection.

    Behaves like a real connection (cursor/commit/rollback, attribute access,
    context-manager) but `.close()` RETURNS the connection to the pool instead of
    tearing down the socket. Before returning, any open transaction is rolled back
    so a reused connection never carries another request's uncommitted state — an
    isolation safeguard that matters directly for cross-user (RLS) correctness.
    """

    __slots__ = ("_conn", "_pool", "_returned")

    def __init__(self, pool: "psycopg2.pool.ThreadedConnectionPool", conn: PGConnection) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_returned", False)

    def close(self) -> None:
        if object.__getattribute__(self, "_returned"):
            return
        object.__setattr__(self, "_returned", True)
        conn = object.__getattribute__(self, "_conn")
        pool = object.__getattribute__(self, "_pool")
        broken = False
        try:
            if conn.closed == 0:
                if not conn.autocommit:
                    conn.rollback()  # discard uncommitted state before reuse
                else:
                    # A borrower ran in autocommit (e.g. a read-only ownership check);
                    # restore the pool default so the next borrower gets autocommit=False.
                    conn.autocommit = False
        except Exception:
            broken = True
        try:
            pool.putconn(conn, close=broken)
        except Exception:  # pragma: no cover - pool already closed at shutdown
            with contextlib.suppress(Exception):
                conn.close()

    # Proxy everything else to the underlying connection.
    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_conn"), name, value)

    def __enter__(self) -> PGConnection:
        # psycopg2's own CM returns the connection and commits/rolls back on exit
        # (it does NOT close). Mirror that; the caller is still expected to .close()
        # (return to pool) afterwards, exactly as with a real connection.
        return object.__getattribute__(self, "_conn").__enter__()

    def __exit__(self, *exc: Any) -> Any:
        return object.__getattribute__(self, "_conn").__exit__(*exc)


def get_connection() -> PGConnection:
    """Acquire a DB connection.

    Pool-backed by default (warm reuse → ~1.6ms instead of ~28ms connect). The
    returned object supports the full connection contract; `.close()` returns it to
    the pool. Falls back to a direct connection if pooling is disabled or the pool
    is exhausted/unavailable, so callers never hard-fail on a transient pool issue.
    """
    pool = _get_pool()
    if pool is not None:
        try:
            conn = pool.getconn()
            conn.autocommit = False
            return _PooledConnection(pool, conn)  # type: ignore[return-value]
        except psycopg2.pool.PoolError as exc:
            # Pool exhausted under burst — degrade to a direct connect rather than
            # failing the request. PgBouncer + HPA absorb sustained 100k load.
            logger.warning("DB pool exhausted (%s) — direct connect fallback", exc)
        except Exception as exc:  # pragma: no cover
            logger.warning("DB pool getconn failed (%s) — direct connect fallback", exc)
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = False
    return conn


def close_pool() -> None:
    """Close all pooled connections (call on process shutdown)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            with contextlib.suppress(Exception):
                _pool.closeall()
            _pool = None


atexit.register(close_pool)


@contextlib.contextmanager
def transaction() -> Generator[psycopg2.extras.DictCursor, None, None]:
    """Context manager that yields a DictCursor and commits on success, rolls back on error."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_legislation(cur: Any, row: dict) -> None:
    """Insert or update a legislation chunk. Keyed on (source_url, chunk_index).
    Provenance columns default to UK-employment values but can be overridden via
    the row dict so future domains/countries reuse the same writer."""
    row = {
        "country_code": "GB",
        "domain": "employment_uk",
        "source_type": "primary_legislation",
        "licence_status": "GRANTED",
        "parser_type": "clml_xml",
        "parent_source_id": "legislation_gov_uk",
        **row,
    }
    cur.execute(
        """
        INSERT INTO legislation (
            act_title, leg_type, year, chapter, section_ref, jurisdiction,
            heading, body_text, chunk_index, source_url, version_date,
            effective_from, effective_to, is_prospective, last_verified_at,
            content_hash, country_code, domain, source_type, licence_status,
            parser_type, parent_source_id
        ) VALUES (
            %(act_title)s, %(leg_type)s, %(year)s, %(chapter)s, %(section_ref)s,
            %(jurisdiction)s, %(heading)s, %(body_text)s, %(chunk_index)s,
            %(source_url)s, %(version_date)s, %(effective_from)s, %(effective_to)s,
            %(is_prospective)s, now(),
            encode(sha256(coalesce(%(body_text)s, '')::bytea), 'hex'),
            %(country_code)s, %(domain)s, %(source_type)s, %(licence_status)s,
            %(parser_type)s, %(parent_source_id)s
        )
        ON CONFLICT (source_url, chunk_index) DO UPDATE SET
            act_title        = EXCLUDED.act_title,
            heading          = EXCLUDED.heading,
            body_text        = EXCLUDED.body_text,
            effective_from   = EXCLUDED.effective_from,
            effective_to     = EXCLUDED.effective_to,
            is_prospective   = EXCLUDED.is_prospective,
            last_verified_at = now(),
            content_hash     = EXCLUDED.content_hash,
            country_code     = EXCLUDED.country_code,
            domain           = EXCLUDED.domain,
            source_type      = EXCLUDED.source_type,
            licence_status   = EXCLUDED.licence_status,
            parser_type      = EXCLUDED.parser_type,
            parent_source_id = EXCLUDED.parent_source_id
        """,
        row,
    )


def upsert_legislation_embedding(cur: Any, source_url: str, chunk_index: int, embedding: list[float]) -> None:
    cur.execute(
        "UPDATE legislation SET embedding = %s WHERE source_url = %s AND chunk_index = %s",
        (embedding, source_url, chunk_index),
    )


def upsert_case_law_document(cur: Any, doc: dict) -> str:
    """
    Insert or update a case_law_documents row (one per decision).
    Returns the document UUID (for use when inserting chunks).

    Keyed on document_uri (the stable d-{uuid} identifier).
    Metadata always updates (parser may improve). Body text is in chunks — not here.
    """
    cur.execute(
        """
        INSERT INTO case_law_documents (
            document_uri, fetch_url, neutral_citation, fclid, case_name, court_code,
            decision_date, judges, parties, content_hash,
            published_date, updated_date, last_verified_at
        ) VALUES (
            %(document_uri)s, %(fetch_url)s, %(neutral_citation)s, %(fclid)s,
            %(case_name)s, %(court_code)s, %(decision_date)s, %(judges)s,
            %(parties)s, %(content_hash)s, %(published_date)s, %(updated_date)s, now()
        )
        ON CONFLICT (document_uri) DO UPDATE SET
            fetch_url        = EXCLUDED.fetch_url,
            neutral_citation = EXCLUDED.neutral_citation,
            case_name        = EXCLUDED.case_name,
            court_code       = EXCLUDED.court_code,
            decision_date    = EXCLUDED.decision_date,
            judges           = EXCLUDED.judges,
            parties          = EXCLUDED.parties,
            content_hash     = EXCLUDED.content_hash,
            updated_date     = EXCLUDED.updated_date,
            last_verified_at = now()
        RETURNING id
        """,
        doc,
    )
    row = cur.fetchone()
    return row["id"] if row else _get_document_id(cur, doc["document_uri"])


def _get_document_id(cur: Any, document_uri: str) -> str:
    cur.execute("SELECT id FROM case_law_documents WHERE document_uri = %s", (document_uri,))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"case_law_documents row not found for {document_uri}")
    return row["id"]


def upsert_case_law_chunk(cur: Any, document_id: str, chunk_index: int, body_text: str) -> None:
    """
    Insert or update a case_law_chunks row.
    Body text only updated when the parent document's content_hash changes
    (caller is responsible for that logic — here we always upsert the text
    so re-ingest after a parser fix works correctly).
    """
    cur.execute(
        """
        INSERT INTO case_law_chunks (document_id, chunk_index, body_text)
        VALUES (%s, %s, %s)
        ON CONFLICT (document_id, chunk_index) DO UPDATE SET
            body_text = EXCLUDED.body_text
        """,
        (document_id, chunk_index, body_text),
    )


def upsert_acas_guidance(cur: Any, row: dict) -> None:
    row = {
        "country_code": "GB",
        "jurisdiction": "EW",
        "domain": "employment_uk",
        "source_type": "official_guidance",
        "licence_status": "GRANTED",
        "parser_type": "html",
        "parent_source_id": "acas",
        "edition": None,
        "section_ref": None,
        "effective_from": None,
        **row,
    }
    cur.execute(
        """
        INSERT INTO acas_guidance (
            doc_title, edition, section_ref, body_text, chunk_index,
            source_url, effective_from, last_verified_at, content_hash,
            country_code, jurisdiction, domain, source_type, licence_status,
            parser_type, parent_source_id
        ) VALUES (
            %(doc_title)s, %(edition)s, %(section_ref)s, %(body_text)s,
            %(chunk_index)s, %(source_url)s, %(effective_from)s, now(),
            encode(sha256(coalesce(%(body_text)s, '')::bytea), 'hex'),
            %(country_code)s, %(jurisdiction)s, %(domain)s, %(source_type)s,
            %(licence_status)s, %(parser_type)s, %(parent_source_id)s
        )
        ON CONFLICT DO NOTHING
        """,
        row,
    )


def upsert_rule(cur: Any, row: dict) -> None:
    """Insert or update a rule row. Keyed on (rule_key, jurisdiction, effective_from)."""
    row = {
        "country_code": "GB",
        "domain": "employment_uk",
        "verification_status": None,
        "verification_notes": None,
        **row,
    }
    cur.execute(
        """
        INSERT INTO rules (
            rule_key, claim_type, jurisdiction, value_numeric, value_text, unit,
            description, authority_type, authority_ref, authority_url,
            effective_from, effective_to, is_prospective, last_verified_at,
            country_code, domain, verification_status, verification_notes
        ) VALUES (
            %(rule_key)s, %(claim_type)s, %(jurisdiction)s, %(value_numeric)s,
            %(value_text)s, %(unit)s, %(description)s, %(authority_type)s,
            %(authority_ref)s, %(authority_url)s, %(effective_from)s,
            %(effective_to)s, %(is_prospective)s, now(),
            %(country_code)s, %(domain)s, %(verification_status)s, %(verification_notes)s
        )
        ON CONFLICT (rule_key, jurisdiction, effective_from) DO UPDATE SET
            value_numeric       = EXCLUDED.value_numeric,
            value_text          = EXCLUDED.value_text,
            description         = EXCLUDED.description,
            authority_ref       = EXCLUDED.authority_ref,
            authority_url       = EXCLUDED.authority_url,
            effective_to        = EXCLUDED.effective_to,
            is_prospective      = EXCLUDED.is_prospective,
            last_verified_at    = now(),
            country_code        = EXCLUDED.country_code,
            domain              = EXCLUDED.domain,
            verification_status = EXCLUDED.verification_status,
            verification_notes  = EXCLUDED.verification_notes
        """,
        row,
    )


def insert_audit_log(cur: Any, payload: dict) -> None:
    """
    Insert one row into assessment_audit_logs.

    GUARDRAIL: stores only safe metadata — no raw user facts, no personal data
    (names, employers, addresses, DOB, emails, medical details), no free-text
    case narrative. The fact_snapshot_hash is SHA256 of de-identified facts only.

    Called after the governance decision, regardless of pass/fail.
    """
    cur.execute(
        """
        INSERT INTO assessment_audit_logs (
            case_id, fact_snapshot_hash, rules_used, retrieval_bundle,
            model_provider, model_name, boundary_log,
            grounding_score, confidence_score, governance_result, output_version
        ) VALUES (
            %(case_id)s, %(fact_snapshot_hash)s, %(rules_used)s::jsonb,
            %(retrieval_bundle)s::jsonb, %(model_provider)s, %(model_name)s,
            %(boundary_log)s::jsonb, %(grounding_score)s, %(confidence_score)s,
            %(governance_result)s::jsonb, %(output_version)s
        )
        """,
        {
            "case_id":            payload.get("case_id"),
            "fact_snapshot_hash": payload["fact_snapshot_hash"],
            "rules_used":         json.dumps(payload.get("rules_used", [])),
            "retrieval_bundle":   json.dumps(payload.get("retrieval_bundle", {})),
            "model_provider":     payload["model_provider"],
            "model_name":         payload.get("model_name"),
            "boundary_log":       json.dumps(payload["boundary_log"]),
            "grounding_score":    payload.get("grounding_score"),
            "confidence_score":   payload.get("confidence_score"),
            "governance_result":  json.dumps(payload["governance_result"]),
            "output_version":     payload.get("output_version", "1.0"),
        },
    )


def _safe_fact_hash(safe_facts: dict) -> str:
    """SHA256 of de-identified safe_facts — fingerprint only, no PII stored."""
    hashable = {k: v for k, v in safe_facts.items() if not k.startswith("_")}
    return hashlib.sha256(
        json.dumps(hashable, sort_keys=True, default=str).encode()
    ).hexdigest()
