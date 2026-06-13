-- Phase 4 / Fix 2 — Add indexes for CRM list/queue queries
-- Cuts list latency dramatically once crm_leads grows past a few hundred rows.
-- Project has no Alembic; apply manually once on each environment.
--
-- Postgres:
--   psql $DATABASE_URL -f backend/migrations_manual/004_add_crm_leads_indexes.sql

CREATE INDEX IF NOT EXISTS idx_crm_leads_updated
    ON crm_leads (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_crm_leads_status_contact
    ON crm_leads (customer_status, last_contact_at);

CREATE INDEX IF NOT EXISTS idx_crm_drafts_lead_status
    ON crm_email_drafts (lead_id, status);

CREATE INDEX IF NOT EXISTS idx_crm_tasks_owner_status
    ON crm_tasks (owner_user_id, status, due_date);
