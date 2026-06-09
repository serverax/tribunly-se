-- 034_corpus_quality_views.sql
-- Data-science quality/freshness views + current-chunks materialized view, all
-- jurisdiction-aware. Normalises rules.verification_status to the allowed set.
-- Idempotent (CREATE OR REPLACE / IF NOT EXISTS).

-- ── 0. normalise verification_status to the CANONICAL vocabulary ────────────
-- Canonical values (existing production gate): verified, case_law_verified,
-- prospective, unverified. Map the legacy 'verified_against_official_source'
-- (and uncited NULLs) onto canonical 'verified'/'unverified'. Do NOT clobber
-- existing canonical statuses.
UPDATE rules SET verification_status = 'verified'
 WHERE verification_status IN ('verified_against_official_source','verified_live')
    OR (verification_status IS NULL AND authority_url ILIKE '%legislation.gov.uk%' AND authority_ref IS NOT NULL AND authority_ref <> '');
UPDATE rules SET verification_status = 'unverified'
 WHERE verification_status IS NULL
    OR verification_status NOT IN ('verified','case_law_verified','prospective','unverified','mismatch','blocked');

-- ── 1. source_freshness (per source_type + jurisdiction) ────────────────────
DROP VIEW IF EXISTS source_freshness;
CREATE VIEW source_freshness AS
WITH base AS (
  SELECT 'legislation' AS source_name, 'legislation' AS source_type, 'legislation' AS run_src, jurisdiction_code, last_verified_at FROM legislation
  UNION ALL SELECT 'acas_guidance','acas','acas', jurisdiction_code, last_verified_at FROM acas_guidance
  UNION ALL SELECT 'official_guidance','govuk','govuk', jurisdiction_code, last_verified_at FROM official_guidance
  UNION ALL SELECT 'rules','rules','limits_orders', jurisdiction_code, last_verified_at FROM rules
  UNION ALL SELECT 'case_law_documents','case_law','case_law', jurisdiction_code, last_verified_at FROM case_law_documents
)
SELECT b.source_name, b.source_type, b.jurisdiction_code,
       count(*)                                                              AS rows_count,
       count(*)                                                              AS rows,            -- backward-compat
       min(b.last_verified_at)                                               AS oldest_verified_at,
       min(b.last_verified_at)                                               AS oldest_verified, -- backward-compat
       max(b.last_verified_at)                                               AS newest_verified_at,
       count(*) FILTER (WHERE b.last_verified_at < now() - interval '120 days') AS stale_rows_count,
       (SELECT r.status FROM corpus_ingestion_runs r WHERE r.source_id = b.run_src ORDER BY r.created_at DESC LIMIT 1)               AS last_ingestion_status,
       (SELECT COALESCE(r.finished_at, r.completed_at) FROM corpus_ingestion_runs r WHERE r.source_id = b.run_src ORDER BY r.created_at DESC LIMIT 1) AS last_ingestion_finished_at
FROM base b
GROUP BY b.source_name, b.source_type, b.jurisdiction_code, b.run_src;

-- ── 2. corpus_quality_report (grouped by source_type/domain/claim/jurisdiction) ──
CREATE OR REPLACE VIEW corpus_quality_report AS
SELECT
   c.source_type, c.domain, c.claim_type, c.jurisdiction_code,
   count(*)                                                       AS total_chunks,
   count(*) FILTER (WHERE c.embedding IS NOT NULL)                AS chunks_with_embedding,
   count(*) FILTER (WHERE c.embedding IS NULL)                    AS chunks_without_embedding,
   count(*) FILTER (WHERE c.source_url IS NOT NULL AND c.source_url <> '') AS chunks_with_source_url,
   count(*) FILTER (WHERE c.source_url IS NULL OR c.source_url = '')       AS chunks_without_source_url,
   round(avg(c.quality_score), 3)                                AS avg_quality_score,
   (SELECT count(*) FROM rules WHERE verification_status NOT IN ('verified','case_law_verified')) AS unverified_rules_count,
   (SELECT count(*) FROM rules WHERE is_prospective)                                            AS prospective_rows_count,
   (count(*) - count(DISTINCT c.chunk_hash))                     AS duplicate_hash_count
FROM corpus_chunks c
GROUP BY c.source_type, c.domain, c.claim_type, c.jurisdiction_code;

-- ── 3. mv_current_employment_legal_chunks (clean retrieval set) ─────────────
DROP MATERIALIZED VIEW IF EXISTS mv_current_employment_legal_chunks;
CREATE MATERIALIZED VIEW mv_current_employment_legal_chunks AS
SELECT c.id, c.source_table, c.source_row_uuid, c.source_id, c.domain, c.claim_type,
       c.jurisdiction_code, c.authority_ref, c.source_url, c.title, c.heading,
       c.body_text, c.chunk_index, c.chunk_hash, c.embedding, c.embedding_model,
       c.effective_from, c.effective_to, c.quality_score, c.source_type, c.licence_status
FROM corpus_chunks c
WHERE c.is_current = true
  AND COALESCE(c.is_prospective,false) = false
  AND c.jurisdiction_code IN ('GB','EW','S','UK')         -- supported jurisdictions (NI excluded until implemented)
  AND c.source_url IS NOT NULL AND c.source_url <> ''
  AND c.chunk_hash IS NOT NULL AND c.chunk_hash <> ''
  AND c.body_text IS NOT NULL AND c.body_text <> ''
  AND COALESCE(c.quality_score, 0) >= 0.6
  AND (c.licence_status IS NULL OR c.licence_status IN ('open','GRANTED','granted'));
CREATE UNIQUE INDEX IF NOT EXISTS mv_current_chunks_hash_idx ON mv_current_employment_legal_chunks (chunk_hash);
CREATE INDEX IF NOT EXISTS mv_current_chunks_juris_idx ON mv_current_employment_legal_chunks (jurisdiction_code, claim_type);
