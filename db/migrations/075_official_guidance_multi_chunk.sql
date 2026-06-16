-- Allow multiple official_guidance rows per source_url (chunk_index).
-- Conflicts with official_guidance_url_chunk_uq which remains the canonical key.
ALTER TABLE official_guidance DROP CONSTRAINT IF EXISTS official_guidance_source_url_key;
DROP INDEX IF EXISTS official_guidance_source_url_key;
