BEGIN;

CREATE TABLE IF NOT EXISTS freemius_webhook_events (
    event_id VARCHAR(255) PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    received_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITHOUT TIME ZONE NULL
);

ALTER TABLE users
ADD COLUMN IF NOT EXISTS searches_rollover_remaining INTEGER NOT NULL DEFAULT 0;

-- Ensure legacy paid rows have at least their normal allowance. This keeps
-- the migration safe to re-run after rollover credits have started accruing.
UPDATE users
SET searches_limit = 500,
    searches_rollover_remaining = 0
WHERE LOWER(COALESCE(plan, 'free')) = 'pro'
  AND COALESCE(searches_limit, 0) < 500;

UPDATE users
SET searches_limit = 1000,
    searches_rollover_remaining = 0
WHERE LOWER(COALESCE(plan, 'free')) = 'business'
  AND COALESCE(searches_limit, 0) < 1000;

UPDATE users
SET searches_limit = 10,
    searches_rollover_remaining = 0
WHERE LOWER(COALESCE(plan, 'free')) = 'free';

-- Paid accounts have already left the one-time Free entitlement. Mark users
-- who consumed all ten Free searches as used as well.
UPDATE users
SET free_trial_used = TRUE
WHERE LOWER(COALESCE(plan, 'free')) IN ('pro', 'business')
   OR LOWER(COALESCE(payment_provider, '')) = 'freemius'
   OR COALESCE(searches_used, 0) >= 10;

COMMIT;
