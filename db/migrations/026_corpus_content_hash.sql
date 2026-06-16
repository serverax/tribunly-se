-- 026_corpus_content_hash.sql (addendum §1  -  content_hash is required corpus metadata)
-- Adds content_hash to the corpus source tables and backfills existing legislation
-- rows from body_text (SHA-256 hex). Idempotent; safe to re-run.
-- The ingest script (scripts/ingest-employment-law-corpus.sh) backfills content_hash
-- after each ingestion so freshly-ingested rows are covered too.

ALTER TABLE legislation       ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE acas_guidance     ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE official_guidance ADD COLUMN IF NOT EXISTS content_hash TEXT;

UPDATE legislation
   SET content_hash = encode(sha256(coalesce(body_text,'')::bytea), 'hex')
 WHERE content_hash IS NULL;
