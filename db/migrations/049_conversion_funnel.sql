-- 049_conversion_funnel.sql
-- SUBAGENT 5: Conversion Funnel Engineer.
--
-- Acquisition / conversion funnel event tracking.
--
-- WHY A NEW TABLE (not the existing funnel_events):
--   funnel_events (migration 010) is CASE-SCOPED (case_id uuid REFERENCES cases).
--   It records IN-PRODUCT events that happen AFTER a case exists. It structurally
--   cannot represent the acquisition funnel  -  landing_view, tool_preview,
--   signup_started, signup_completed all occur for an ANONYMOUS visitor BEFORE any
--   user or case exists, so there is nothing to hang a case_id on. conversion_events
--   is therefore keyed on an anonymous session_id (the visitor spine) and carries
--   first-touch attribution. The two tables are complementary, not duplicates.
--
-- PRIVACY / GUARDRAIL (constitution §8, §19):
--   * No raw IP is stored  -  only ip_hash (salted SHA256), and only when
--     ANALYTICS_IP_SALT is configured; otherwise NULL.
--   * referrer / landing_page are stored host+path only (query strings stripped at
--     the API layer) so tracking parameters carrying PII never land in the table.
--   * properties jsonb must not contain personal facts, free-text narrative, names,
--     emails, addresses, or uploaded file content  -  enforced at the API layer.
--   * user_id is NULL for anonymous pre-signup events; it is backfilled onto a
--     session's earlier events when that session signs up (signup_completed),
--     which is what makes first-touch attribution of a converted user work.
--
-- Idempotent (CREATE ... IF NOT EXISTS)  -  safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS conversion_events (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Anonymous visitor/session identifier (client-generated, persisted in the
    -- browser). The funnel spine: one session is followed landing_view → payment.
    session_id   text        NOT NULL,
    -- One of the canonical funnel events  -  validated at the API layer (no DB CHECK
    -- so new event types can be added without a migration), mirroring how
    -- users.role is validated in 048.
    event_name   text        NOT NULL,
    -- Linked to a real user once the session signs up; NULL while anonymous.
    user_id      uuid        REFERENCES users(id) ON DELETE SET NULL,

    -- ── First-touch attribution (carried per session) ───────────────────────────
    source       text,       -- utm_source, else derived referrer host, else 'direct'
    medium       text,       -- utm_medium  (e.g. cpc | organic | referral | none)
    campaign     text,       -- utm_campaign
    referrer     text,       -- document.referrer, host+path only (no query string)
    landing_page text,       -- first path the visitor hit, path only (no query)

    -- ── Event-specific metadata (NO PII) ────────────────────────────────────────
    properties   jsonb       NOT NULL DEFAULT '{}'::jsonb,

    -- ── Request fingerprints (privacy-safe) ─────────────────────────────────────
    ip_hash      text,       -- salted SHA256(ip); NULL when ANALYTICS_IP_SALT unset
    user_agent   text,

    occurred_at  timestamptz NOT NULL DEFAULT now()
);

-- Funnel counts group by event_name within a time window.
CREATE INDEX IF NOT EXISTS ce_event_time_idx ON conversion_events (event_name, occurred_at);
-- Per-session reconstruction (first-touch, stage reach, backfill).
CREATE INDEX IF NOT EXISTS ce_session_idx    ON conversion_events (session_id);
-- Converted-user lookups + backfill targeting.
CREATE INDEX IF NOT EXISTS ce_user_idx       ON conversion_events (user_id) WHERE user_id IS NOT NULL;
-- Attribution breakdown by source.
CREATE INDEX IF NOT EXISTS ce_source_idx     ON conversion_events (source);
-- Date-range scans for the dashboard.
CREATE INDEX IF NOT EXISTS ce_time_idx       ON conversion_events (occurred_at);

-- First-touch attribution per session: the source/medium/campaign/landing_page of
-- the EARLIEST event in the session, plus the linked user (if any) and the session
-- lifespan. DISTINCT ON (session_id) ordered by occurred_at takes the first row.
CREATE OR REPLACE VIEW conversion_session_attribution AS
SELECT DISTINCT ON (session_id)
       session_id,
       COALESCE(source, 'direct') AS first_source,
       medium                     AS first_medium,
       campaign                   AS first_campaign,
       landing_page               AS first_landing_page,
       occurred_at                AS first_seen
  FROM conversion_events
 ORDER BY session_id, occurred_at ASC, id ASC;

COMMIT;
