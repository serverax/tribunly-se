-- 085_user_preferences_locale.sql
-- Presentation-layer locale preference (not legal content translation).

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    default_locale  VARCHAR(10) NOT NULL DEFAULT 'en'
        CHECK (default_locale IN ('en', 'ar')),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_preferences_locale_idx
    ON user_preferences (default_locale);

COMMENT ON TABLE user_preferences IS
    'UI and reasoning phrasing locale. Does not change RAG/rules retrieval language.';
