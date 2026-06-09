-- Migration 046: Payment sessions and upload/document tables
-- Supports payment checkout sessions and document storage metadata.

-- Payment sessions (tracks Stripe checkout sessions)
CREATE TABLE IF NOT EXISTS payment_sessions (
    id                BIGSERIAL PRIMARY KEY,
    case_id           UUID        NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    user_id           UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_session_id TEXT        NOT NULL UNIQUE,
    status            TEXT        NOT NULL DEFAULT 'pending',  -- pending | paid | cancelled
    package_id        TEXT        NOT NULL DEFAULT 'full_documents',
    amount_pence      INTEGER     NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ,
    CONSTRAINT payment_sessions_status_check CHECK (
        status IN ('pending', 'paid', 'cancelled')
    )
);

CREATE INDEX IF NOT EXISTS payment_sessions_case_idx   ON payment_sessions (case_id);
CREATE INDEX IF NOT EXISTS payment_sessions_user_idx   ON payment_sessions (user_id);
CREATE INDEX IF NOT EXISTS payment_sessions_status_idx ON payment_sessions (status);

-- Ensure documents table has necessary columns for uploads
DO $$
BEGIN
    -- Add extraction-related columns if they don't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='documents' AND column_name='extracted_content'
    ) THEN
        ALTER TABLE documents ADD COLUMN extracted_content TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='documents' AND column_name='extraction_error'
    ) THEN
        ALTER TABLE documents ADD COLUMN extraction_error TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='documents' AND column_name='document_type'
    ) THEN
        ALTER TABLE documents ADD COLUMN document_type TEXT;
    END IF;
END
$$;

-- Index for document lookups
CREATE INDEX IF NOT EXISTS documents_case_type_idx ON documents (case_id, document_type)
    WHERE is_user_upload = false;
