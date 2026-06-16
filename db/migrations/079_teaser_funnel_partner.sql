-- 079_teaser_funnel_partner.sql
-- Owner Feature §5 #8: strip special-category teaser persistence; funnel signals only.
-- Owner Feature §5 #5: partner_registry scaffold for F12 referrals.

BEGIN;

-- Non-sensitive funnel analytics (legitimate interest; no case facts)
CREATE TABLE IF NOT EXISTS funnel_signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool            TEXT NOT NULL,
    coarse_outcome  TEXT,
    session_id      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS funnel_signals_tool_idx ON funnel_signals (tool, created_at DESC);

-- Deprecate encrypted answer blob on teaser_sessions (GDPR Article 9 alignment)
ALTER TABLE teaser_sessions
    ADD COLUMN IF NOT EXISTS deprecated_at TIMESTAMPTZ;

COMMENT ON COLUMN teaser_sessions.state_encrypted IS
    'DEPRECATED 2026-06-16: special-category answers must not persist anonymously. Use funnel_signals.';

-- Partner registry (no hardcoded partners; owner signs orgs later)
CREATE TABLE IF NOT EXISTS partner_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    webhook_url     TEXT,
    notify_email    TEXT,
    fee_basis       TEXT NOT NULL DEFAULT 'referral_fee'
                    CHECK (fee_basis IN ('referral_fee')),
    sra_disclosure_required BOOLEAN NOT NULL DEFAULT true,
    active          BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Link spec referral rows to registry when partner is known
ALTER TABLE referral
    ADD COLUMN IF NOT EXISTS partner_registry_id UUID REFERENCES partner_registry(id);

COMMIT;
