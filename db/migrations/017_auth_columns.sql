-- Migration 016: Auth columns
-- Adds password_hash to users table for Phase 11 auth.

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text;
