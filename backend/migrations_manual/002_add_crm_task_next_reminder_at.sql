-- Phase 3 / Fix 4 — Add next_reminder_at to crm_tasks
-- Enables repeated reminders: WF06 re-includes a task once next_reminder_at
-- has passed, instead of skipping forever after the first reminder.
--
-- Postgres:
--   psql $DATABASE_URL -f backend/migrations_manual/002_add_crm_task_next_reminder_at.sql

ALTER TABLE crm_tasks
    ADD COLUMN IF NOT EXISTS next_reminder_at TIMESTAMPTZ;
