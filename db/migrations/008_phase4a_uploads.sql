-- Migration 008: Phase 4A  -  document upload metadata columns
-- Augments the existing `documents` table with upload/extraction metadata.
-- NOTE: storage_ref in Phase 4A points to local filesystem path.
-- Encryption at rest is Phase 5. This migration is safe to apply multiple times.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS original_filename  text;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_type       text;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size_bytes    bigint;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_status  text DEFAULT 'pending';
-- extraction_status: pending | extracted | reviewed

CREATE INDEX IF NOT EXISTS documents_upload_idx
    ON documents (case_id, is_user_upload)
    WHERE is_user_upload = true;
