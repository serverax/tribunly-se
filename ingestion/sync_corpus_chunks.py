"""
Sync corpus_chunks from source tables (legislation, acas_guidance, official_guidance).

Idempotent via chunk_hash ON CONFLICT DO NOTHING  -  safe to run after every ingest
and embed pass. Mirrors db/migrations/032_corpus_chunks_and_audits.sql population.

Usage:
    python -m ingestion.sync_corpus_chunks
"""

from __future__ import annotations

import logging

from rich.console import Console

from ingestion.db import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
console = Console()

_SYNC_SQL = """
INSERT INTO corpus_chunks
  (source_table, source_row_uuid, source_id, domain, claim_type, jurisdiction, jurisdiction_code, country_code,
   authority_ref, source_url, title, heading, body_text, chunk_index, chunk_hash,
   tokens_estimate, embedding, embedding_model, embedding_created_at,
   effective_from, effective_to, is_current, is_prospective, source_type, licence_status)
SELECT 'legislation', l.id,
       (SELECT id FROM legal_sources s WHERE s.source_id='legislation_gov_uk' AND s.domain='employment_uk' LIMIT 1),
       'employment_uk', 'unfair_dismissal', COALESCE(l.jurisdiction, l.jurisdiction_code, 'GB'), l.jurisdiction_code, l.country_code,
       (l.act_title||' s.'||COALESCE(l.section_ref,'')), l.source_url, l.act_title, l.heading,
       l.body_text, l.chunk_index,
       encode(sha256(('legislation:'||l.source_url||':'||l.chunk_index||':'||l.body_text)::bytea),'hex'),
       (length(l.body_text)/4)::int, l.embedding, 'bge-small-en-v1.5', l.last_verified_at,
       l.effective_from, l.effective_to, (NOT COALESCE(l.is_prospective,false)), COALESCE(l.is_prospective,false),
       l.source_type, l.licence_status
FROM legislation l
ON CONFLICT (chunk_hash) DO NOTHING;

INSERT INTO corpus_chunks
  (source_table, source_row_uuid, source_id, domain, claim_type, jurisdiction, jurisdiction_code, country_code,
   authority_ref, source_url, title, heading, body_text, chunk_index, chunk_hash,
   tokens_estimate, embedding, embedding_model, embedding_created_at,
   is_current, source_type, licence_status)
SELECT 'acas_guidance', a.id,
       (SELECT id FROM legal_sources s WHERE s.source_id='acas' AND s.domain='employment_uk' LIMIT 1),
       'employment_uk', 'unfair_dismissal', COALESCE(a.jurisdiction, a.jurisdiction_code, 'GB'), a.jurisdiction_code, a.country_code,
       a.doc_title, a.source_url, a.doc_title, NULL,
       a.body_text, a.chunk_index,
       encode(sha256(('acas:'||a.source_url||':'||a.chunk_index||':'||a.body_text)::bytea),'hex'),
       (length(a.body_text)/4)::int, a.embedding, 'bge-small-en-v1.5', a.last_verified_at,
       true, a.source_type, a.licence_status
FROM acas_guidance a
ON CONFLICT (chunk_hash) DO NOTHING;

INSERT INTO corpus_chunks
  (source_table, source_row_uuid, source_id, domain, claim_type, jurisdiction, jurisdiction_code, country_code,
   authority_ref, source_url, title, heading, body_text, chunk_index, chunk_hash,
   tokens_estimate, embedding, embedding_model, embedding_created_at,
   is_current, source_type, licence_status)
SELECT 'official_guidance', o.id,
       (SELECT id FROM legal_sources s WHERE s.source_id='govuk_courts_tribunals_publishing' AND s.domain='employment_uk' LIMIT 1),
       'employment_uk', 'unfair_dismissal', COALESCE(o.jurisdiction, o.jurisdiction_code, 'GB'), o.jurisdiction_code, o.country_code,
       o.title, o.source_url, o.title, NULL,
       o.body_text, o.chunk_index,
       encode(sha256(('govuk:'||o.source_url||':'||o.chunk_index||':'||o.body_text)::bytea),'hex'),
       (length(o.body_text)/4)::int, o.embedding, 'bge-small-en-v1.5', o.last_verified_at,
       COALESCE(o.is_current,true), o.source_type, o.licence_status
FROM official_guidance o
ON CONFLICT (chunk_hash) DO NOTHING;

UPDATE corpus_chunks SET quality_score = (
    (CASE WHEN source_url IS NOT NULL AND source_url<>'' THEN 0.25 ELSE 0 END)
  + (CASE WHEN jurisdiction_code IS NOT NULL THEN 0.2 ELSE 0 END)
  + (CASE WHEN authority_ref IS NOT NULL AND authority_ref<>'' THEN 0.2 ELSE 0 END)
  + (CASE WHEN embedding IS NOT NULL THEN 0.2 ELSE 0 END)
  + (CASE WHEN chunk_hash IS NOT NULL THEN 0.15 ELSE 0 END)
) WHERE quality_score IS NULL;
"""


def sync_corpus_chunks() -> dict[str, int]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM corpus_chunks")
            before = cur.fetchone()[0]
            cur.execute(_SYNC_SQL)
            cur.execute("SELECT COUNT(*) FROM corpus_chunks")
            after = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM corpus_chunks WHERE embedding IS NOT NULL"
            )
            embedded = cur.fetchone()[0]
        conn.commit()
        return {"before": before, "after": after, "added": after - before, "embedded": embedded}
    finally:
        conn.close()


def main() -> None:
    console.print("[bold green]Syncing corpus_chunks from source tables…[/bold green]")
    stats = sync_corpus_chunks()
    console.print(
        f"  before={stats['before']} after={stats['after']} "
        f"added={stats['added']} embedded={stats['embedded']}"
    )


if __name__ == "__main__":
    main()
