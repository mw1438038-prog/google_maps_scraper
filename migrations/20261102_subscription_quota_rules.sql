-- Apply manually before deploying the subscription quota policy.
-- This migration alters the schema and updates per-user plan limits.
BEGIN;

ALTER TABLE users
ALTER COLUMN searches_limit DROP NOT NULL;

UPDATE users
SET searches_limit = searches_limit + 500
WHERE plan = 'pro' AND searches_limit IS NOT NULL;

UPDATE users
SET searches_limit = NULL
WHERE plan = 'business';

UPDATE users
SET searches_limit = 10
WHERE plan = 'free';

COMMIT;
