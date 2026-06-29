-- Migration TAC-TIC : colonnes de scoring Machine Learning sur crm_leads.
-- Module Data Science — le score ML devient la référence principale, le score
-- LLM (lead_score) reste conservé en parallèle.
--
-- Idempotente : ADD COLUMN IF NOT EXISTS -> rejouable sans danger.

BEGIN;

ALTER TABLE crm_leads
ADD COLUMN IF NOT EXISTS ml_score INTEGER;

ALTER TABLE crm_leads
ADD COLUMN IF NOT EXISTS ml_probability FLOAT;

ALTER TABLE crm_leads
ADD COLUMN IF NOT EXISTS ml_category VARCHAR(10);

ALTER TABLE crm_leads
ADD COLUMN IF NOT EXISTS ml_confidence FLOAT;

ALTER TABLE crm_leads
ADD COLUMN IF NOT EXISTS shap_explanation JSONB;

COMMIT;
