-- Migration 021 — Payment events audit table
-- Idempotent Stripe webhook processing.
-- Prevents duplicate event handling and stores payment audit trail.

CREATE TABLE IF NOT EXISTS payment_events (
    id              BIGSERIAL PRIMARY KEY,
    stripe_event_id TEXT        NOT NULL UNIQUE,   -- Stripe event.id — idempotency key
    event_type      TEXT        NOT NULL,           -- e.g. checkout.session.completed
    payment_mode    TEXT        NOT NULL,           -- test_simulator | stripe_test | stripe_live
    session_id      TEXT,                           -- Stripe checkout session ID
    payment_intent  TEXT,                           -- Stripe payment intent ID
    case_id         UUID,                           -- Associated lawapp case (if known)
    user_id         UUID,                           -- Associated user (if known)
    amount_total    INTEGER,                        -- Amount in pence/cents
    currency        TEXT,                           -- ISO currency code
    payment_status  TEXT        NOT NULL DEFAULT 'pending',  -- pending | paid | failed | refunded
    raw_event       JSONB       NOT NULL DEFAULT '{}',       -- Full Stripe event (no PII)
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS payment_events_stripe_idx ON payment_events (stripe_event_id);
CREATE INDEX IF NOT EXISTS payment_events_case_idx   ON payment_events (case_id);
CREATE INDEX IF NOT EXISTS payment_events_user_idx   ON payment_events (user_id);
CREATE INDEX IF NOT EXISTS payment_events_status_idx ON payment_events (payment_status);

-- Cases payment tier (add column if not present)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='cases' AND column_name='payment_status'
    ) THEN
        ALTER TABLE cases ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='cases' AND column_name='stripe_session_id'
    ) THEN
        ALTER TABLE cases ADD COLUMN stripe_session_id TEXT;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS cases_payment_status_idx ON cases (payment_status);
