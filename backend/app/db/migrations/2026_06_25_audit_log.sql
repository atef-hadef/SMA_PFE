-- Migration FIX 4 : table d'audit centralisée (audit_log). Idempotente.
BEGIN;

CREATE TABLE IF NOT EXISTS audit_log (
  id          VARCHAR(64) PRIMARY KEY,
  entity_type VARCHAR(40) NOT NULL,
  entity_id   VARCHAR(64),
  action      VARCHAR(40) NOT NULL,
  actor_id    VARCHAR(64) REFERENCES users(id),
  actor_name  VARCHAR(160),
  details     JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_log_created_at  ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS ix_audit_log_entity_type ON audit_log(entity_type);
CREATE INDEX IF NOT EXISTS ix_audit_log_actor_id    ON audit_log(actor_id);

COMMIT;
