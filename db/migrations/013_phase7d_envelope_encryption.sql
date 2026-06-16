-- Migration 013: Phase 7D  -  envelope encryption key metadata columns
-- Adds encryption_key_metadata jsonb to tables that store encrypted data.
-- Stores EncryptedKeyBundle (CiphertextBlob + provider metadata)  -  NOT plaintext keys.
--
-- GUARDRAIL: encryption_key_metadata must NEVER contain plaintext key material.
--            It contains the KMS CiphertextBlob which is safe to persist.

ALTER TABLE cases ADD COLUMN IF NOT EXISTS encryption_key_metadata jsonb;
ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS encryption_key_metadata jsonb;

-- Index for querying unencrypted records (NULL = not yet envelope-encrypted)
CREATE INDEX IF NOT EXISTS cases_enc_meta_idx
    ON cases (id) WHERE encryption_key_metadata IS NULL;
CREATE INDEX IF NOT EXISTS handoff_enc_meta_idx
    ON handoff_leads (id) WHERE encryption_key_metadata IS NULL;

COMMENT ON COLUMN cases.encryption_key_metadata IS
    'EncryptedKeyBundle JSON: CiphertextBlob + provider metadata. NOT plaintext key.';
COMMENT ON COLUMN handoff_leads.encryption_key_metadata IS
    'EncryptedKeyBundle JSON: CiphertextBlob + provider metadata. NOT plaintext key.';
