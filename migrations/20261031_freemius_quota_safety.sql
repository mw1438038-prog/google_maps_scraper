-- Apply manually before deploying the code that validates this schema.
-- This migration is intentionally DDL-only and safe to re-run on PostgreSQL.
BEGIN;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS searches_rollover_remaining INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS freemius_webhook_events (
    event_id VARCHAR(255) PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    received_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITHOUT TIME ZONE NULL
);

COMMIT;
