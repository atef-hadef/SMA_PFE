-- Migration FIX 3 : table des réponses client (crm_lead_responses).
-- Idempotente : CREATE TABLE / INDEX IF NOT EXISTS.
BEGIN;

CREATE TABLE IF NOT EXISTS crm_lead_responses (
  id               VARCHAR(64) PRIMARY KEY,
  lead_id          VARCHAR(64) NOT NULL REFERENCES crm_leads(id),
  response_type    VARCHAR(40) NOT NULL,
  notes            TEXT,
  next_action      TEXT,
  next_action_date TIMESTAMPTZ,
  recorded_by      VARCHAR(64) REFERENCES users(id),
  recorded_at      TIMESTAMPTZ DEFAULT NOW(),
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_crm_lead_responses_lead_id
  ON crm_lead_responses(lead_id);

COMMIT;
