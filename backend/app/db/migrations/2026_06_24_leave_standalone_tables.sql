-- Migration TAC-TIC : tables du module Congés STANDALONE (sans Odoo).
-- Cree les types de conges et les allocations par employe, stockees dans
-- PostgreSQL (le solde n'est plus calcule depuis Odoo).
--
-- Idempotente : CREATE TABLE IF NOT EXISTS + ON CONFLICT DO NOTHING.

BEGIN;

-- Types de congés
CREATE TABLE IF NOT EXISTS leave_types (
  id VARCHAR(64) PRIMARY KEY,
  code VARCHAR(40) UNIQUE NOT NULL,
  label_fr VARCHAR(120) NOT NULL,
  label_en VARCHAR(120),
  default_days INTEGER DEFAULT 0,
  requires_document BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE
);

INSERT INTO leave_types
  (id, code, label_fr, label_en,
   default_days, requires_document)
VALUES
  ('lt_vacation','vacation',
   'Congés payés','Paid Leave',25,false),
  ('lt_sick','sick',
   'Congé maladie','Sick Leave',15,true),
  ('lt_personal','personal',
   'Congé personnel','Personal Leave',5,false),
  ('lt_rtt','rtt','RTT','RTT',10,false),
  ('lt_unpaid','unpaid',
   'Congé sans solde','Unpaid Leave',0,false)
ON CONFLICT (code) DO NOTHING;

-- Allocations par employé
CREATE TABLE IF NOT EXISTS leave_allocations (
  id VARCHAR(64) PRIMARY KEY,
  employee_id VARCHAR(64) NOT NULL
    REFERENCES users(id),
  year INTEGER NOT NULL,
  leave_type VARCHAR(80) NOT NULL,
  allocated_days NUMERIC(8,2) NOT NULL DEFAULT 0,
  created_by VARCHAR(64) REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT uq_alloc_emp_year_type
    UNIQUE(employee_id, year, leave_type)
);

COMMIT;
