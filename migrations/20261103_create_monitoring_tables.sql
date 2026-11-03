-- Create the monitoring tables required by the ORM schema validator.
-- Safe to re-run; this migration is for manual execution in Neon SQL Editor.
BEGIN;

CREATE TABLE IF NOT EXISTS error_events (
    id SERIAL PRIMARY KEY,
    event_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    severity VARCHAR(16) NOT NULL,
    component VARCHAR(32) NOT NULL,
    category VARCHAR(48) NOT NULL,
    route_template VARCHAR(255) NOT NULL,
    http_status INTEGER NULL,
    request_id VARCHAR(36) NOT NULL,
    safe_summary VARCHAR(240) NOT NULL,
    exception_type VARCHAR(100) NULL,
    fingerprint VARCHAR(64) NOT NULL,
    first_seen_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT uq_error_event_request_fingerprint
        UNIQUE (request_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS ix_error_events_timestamp
    ON error_events (event_timestamp);
CREATE INDEX IF NOT EXISTS ix_error_events_component
    ON error_events (component);
CREATE INDEX IF NOT EXISTS ix_error_events_category
    ON error_events (category);
CREATE INDEX IF NOT EXISTS ix_error_events_severity
    ON error_events (severity);
CREATE INDEX IF NOT EXISTS ix_error_events_status
    ON error_events (http_status);
CREATE INDEX IF NOT EXISTS ix_error_events_fingerprint
    ON error_events (fingerprint);
CREATE INDEX IF NOT EXISTS ix_error_events_request_id
    ON error_events (request_id);
CREATE INDEX IF NOT EXISTS ix_error_events_component_timestamp
    ON error_events (component, event_timestamp);
CREATE INDEX IF NOT EXISTS ix_error_events_category_timestamp
    ON error_events (category, event_timestamp);
CREATE INDEX IF NOT EXISTS ix_error_events_severity_timestamp
    ON error_events (severity, event_timestamp);

CREATE TABLE IF NOT EXISTS component_health (
    component VARCHAR(32) PRIMARY KEY,
    status VARCHAR(16) NOT NULL DEFAULT 'degraded',
    last_checked_at TIMESTAMP WITHOUT TIME ZONE NULL,
    last_success_at TIMESTAMP WITHOUT TIME ZONE NULL,
    last_failure_at TIMESTAMP WITHOUT TIME ZONE NULL,
    last_failure_event_id INTEGER NULL,
    check_source VARCHAR(48) NULL,
    safe_status_detail VARCHAR(240) NULL,
    CONSTRAINT component_health_last_failure_event_id_fkey
        FOREIGN KEY (last_failure_event_id)
        REFERENCES error_events (id)
        ON DELETE SET NULL
);

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_error_event_request_fingerprint'
          AND conrelid = 'error_events'::regclass
    ) THEN
        ALTER TABLE error_events
            ADD CONSTRAINT uq_error_event_request_fingerprint
            UNIQUE (request_id, fingerprint);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'component_health_last_failure_event_id_fkey'
          AND conrelid = 'component_health'::regclass
    ) THEN
        ALTER TABLE component_health
            ADD CONSTRAINT component_health_last_failure_event_id_fkey
            FOREIGN KEY (last_failure_event_id)
            REFERENCES error_events (id)
            ON DELETE SET NULL;
    END IF;
END;
$migration$;

COMMIT;
