-- Apply through Alembic or a controlled migration runner; do not execute manually against production.
BEGIN;

CREATE TABLE IF NOT EXISTS workflow_outbox_events (
    event_id VARCHAR(40) PRIMARY KEY,
    dedupe_key VARCHAR(192) NOT NULL UNIQUE,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(40) NOT NULL,
    event_type VARCHAR(96) NOT NULL,
    schema_version VARCHAR(16) NOT NULL DEFAULT '1.0',
    payload JSONB NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at TIMESTAMPTZ NULL,
    locked_by VARCHAR(128) NULL,
    published_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_workflow_outbox_status CHECK (status IN ('pending', 'processing', 'published', 'retry', 'dead_letter'))
);

CREATE INDEX IF NOT EXISTS ix_workflow_outbox_claim
    ON workflow_outbox_events (status, available_at, created_at);
CREATE INDEX IF NOT EXISTS ix_workflow_outbox_aggregate
    ON workflow_outbox_events (aggregate_type, aggregate_id);
CREATE INDEX IF NOT EXISTS ix_workflow_outbox_correlation
    ON workflow_outbox_events (correlation_id);

CREATE TABLE IF NOT EXISTS processed_event_deliveries (
    delivery_id VARCHAR(40) PRIMARY KEY,
    consumer_name VARCHAR(96) NOT NULL,
    event_id VARCHAR(40) NOT NULL REFERENCES workflow_outbox_events(event_id),
    status VARCHAR(24) NOT NULL DEFAULT 'processing',
    completed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_processed_event_delivery UNIQUE (consumer_name, event_id),
    CONSTRAINT ck_processed_event_delivery_status CHECK (status IN ('processing', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_processed_event_delivery_status
    ON processed_event_deliveries (consumer_name, status, created_at);

-- P0 already defines this table. Verify it exists before this migration becomes production baseline.
CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_command_idempotency
    ON processed_workflow_commands (actor_id, command_type, idempotency_key);

COMMIT;
