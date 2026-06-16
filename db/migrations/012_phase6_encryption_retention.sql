-- Migration 012: Phase 6  -  encryption at rest + retention/deletion support
-- Adds soft-delete timestamps and encrypted PII columns.
-- Encryption uses Fernet (AES-128-CBC + HMAC-SHA256) from cryptography package.
-- Full production requires HSM-backed key management (Phase 7).

-- ── Soft delete on cases ──────────────────────────────────────────────────────
ALTER TABLE cases ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS encryption_version text DEFAULT 'none';
-- encryption_version: 'none' | 'fernet_v1'

CREATE INDEX IF NOT EXISTS cases_deleted_idx ON cases (deleted_at)
    WHERE deleted_at IS NULL;

-- ── Encryption + soft delete on handoff_leads ────────────────────────────────
ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS name_encrypted  text;
ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS email_encrypted text;
ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS phone_encrypted text;
ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS pii_encrypted   boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS hl_deleted_idx ON handoff_leads (deleted_at)
    WHERE deleted_at IS NULL;

-- ── Retention metadata ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS retention_runs (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at      timestamptz NOT NULL DEFAULT now(),
    records_processed int  NOT NULL DEFAULT 0,
    records_deleted   int  NOT NULL DEFAULT 0,
    policy_days int         NOT NULL,
    notes       text
);
