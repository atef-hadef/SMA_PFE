-- Phase 4 / Fix 1 — Create webhook_outbox table
-- Durable retry queue for outbound webhooks to n8n. Required by
-- webhook_outbox_service.enqueue / sync_attempt / process_pending.
--
-- Postgres:
--   psql $DATABASE_URL -f backend/migrations_manual/005_add_webhook_outbox.sql

CREATE TABLE IF NOT EXISTS webhook_outbox (
    id                   VARCHAR(64) PRIMARY KEY,
    webhook_url          VARCHAR(512) NOT NULL,
    payload              JSONB NOT NULL,
    status               VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts             INTEGER NOT NULL DEFAULT 0,
    max_attempts         INTEGER NOT NULL DEFAULT 3,
    next_retry_at        TIMESTAMPTZ,
    last_error           TEXT,
    related_object_type  VARCHAR(40),
    related_object_id    VARCHAR(64),
    workflow_name        VARCHAR(120),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_webhook_outbox_status_retry
    ON webhook_outbox (status, next_retry_at);

CREATE INDEX IF NOT EXISTS ix_webhook_outbox_related
    ON webhook_outbox (related_object_type, related_object_id);
