-- Align stored plan limits with the current Free, Pro, and Business plans.
-- Does not alter subscription status, provider, or payment references.
BEGIN;

ALTER TABLE users
ALTER COLUMN searches_limit DROP NOT NULL;

UPDATE users
SET searches_limit = 10
WHERE plan = 'free' AND searches_limit IS DISTINCT FROM 10;

UPDATE users
SET searches_limit = 1000
WHERE plan = 'pro' AND searches_limit IS DISTINCT FROM 1000;

UPDATE users
SET searches_limit = NULL
WHERE plan = 'business' AND searches_limit IS NOT NULL;

COMMIT;
