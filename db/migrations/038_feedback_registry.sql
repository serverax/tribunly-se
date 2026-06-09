-- 038_feedback_registry.sql
-- Evolving Intelligence Stack — Component C: Feedback Registry.
-- Post-outcome learning: when a case closes (e.g. tribunal ruling) the PII-stripped
-- outcome is recorded as "Strategy X + Fact Y + Law Z = Outcome (win/loss)". The DSPy
-- optimizer reads this registry + agent_validation_failures to propose better prompts.
-- NB: corrected migration number (the spec said 028, but 028 is already taken —
-- repo is at 037). Idempotent; additive. No PII stored (deidentify before insert).

CREATE TABLE IF NOT EXISTS feedback_registry (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_ref_hash      TEXT,                       -- one-way hash of case id (no raw id/PII)
    outcome_label      TEXT NOT NULL,              -- win | loss | settled | withdrawn | struck_out | unknown
    claim_type         TEXT,
    jurisdiction_code  TEXT REFERENCES legal_jurisdictions(jurisdiction_code),
    strategy_snapshot  JSONB NOT NULL,             -- {arguments:[...], cited_authorities:[...], rules_used:[...]}
    fact_pattern_tags  TEXT[],                     -- de-identified, generalised fact tags only
    law_refs           TEXT[],                     -- authority_ref list (ERA 1996 s.98, ...)
    court_reference    TEXT,                       -- neutral citation / tribunal ref where public
    grounding_score    NUMERIC,
    pii_stripped       BOOLEAN NOT NULL DEFAULT true,
    source             TEXT NOT NULL DEFAULT 'manual',   -- manual | tribunal_feed | agent_outcome
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS feedback_registry_outcome_idx ON feedback_registry (outcome_label);
CREATE INDEX IF NOT EXISTS feedback_registry_claim_idx   ON feedback_registry (claim_type, jurisdiction_code);
CREATE INDEX IF NOT EXISTS feedback_registry_law_gin     ON feedback_registry USING gin (law_refs);

-- Prompt-version registry: DSPy compiled prompts are versioned data, never edited by
-- hand in production. Promotion only when a candidate beats production on the metric
-- with zero safety/AIA regression (enforced by the optimizer gate + CI).
CREATE TABLE IF NOT EXISTS prompt_versions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name         TEXT NOT NULL,              -- ART | SEA | AEE | critic
    prompt_key         TEXT NOT NULL,
    version            INT NOT NULL,
    prompt_text        TEXT NOT NULL,
    metric_name        TEXT,
    metric_score       NUMERIC,
    is_production       BOOLEAN NOT NULL DEFAULT false,
    safety_regression  BOOLEAN,                     -- true => blocked from promotion
    created_by         TEXT NOT NULL DEFAULT 'dspy_optimizer',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_name, prompt_key, version)
);
CREATE INDEX IF NOT EXISTS prompt_versions_prod_idx ON prompt_versions (agent_name, prompt_key, is_production);
