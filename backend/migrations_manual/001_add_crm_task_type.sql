-- Phase 3 / Fix 3 — Add task_type column to crm_tasks
-- Required for automated follow-up task creation by handle_email_sent_result.
-- Project has no Alembic; apply manually once on each environment.
--
-- Postgres:
--   psql $DATABASE_URL -f backend/migrations_manual/001_add_crm_task_type.sql

ALTER TABLE crm_tasks
    ADD COLUMN IF NOT EXISTS task_type VARCHAR(40);

CREATE INDEX IF NOT EXISTS ix_crm_tasks_task_type
    ON crm_tasks (task_type);
