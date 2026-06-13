# CRM PostgreSQL Model And Seed

## Purpose

Step 53 adds the PostgreSQL model, table creation support, and seed data for CRM leads. This prepares CRM persistence for a later step without changing the current CRM API behavior or frontend integration.

## Table Added

- `crm_leads`

## Columns Created

- `id`
- `full_name`
- `company_name`
- `email`
- `phone`
- `source`
- `status`
- `lead_score`
- `sentiment`
- `urgency`
- `intention`
- `message`
- `ai_summary`
- `recommended_action`
- `owner_user_id`
- `assigned_to`
- `notes`
- `created_at`
- `updated_at`

## Seeded CRM Leads

- `lead_001` - Northwind Logistics, hot lead, score 94
- `lead_002` - Atlas Retail, warm lead, score 72
- `lead_003` - Medina Services, cold lead, score 38

## Required Commands

From the project root:

```powershell
docker compose up -d postgres
```

Then from the backend folder:

```powershell
cd backend
python scripts/create_tables.py
python scripts/seed_database.py
```

## Verify With psql

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Then run:

```sql
SELECT id, full_name, company_name, status, lead_score FROM crm_leads;
```

## Not Implemented Yet

- CRM endpoint replacement
- Frontend changes
- n8n CRM workflow
- Odoo CRM sync
- Real AI scoring
- Authentication/RBAC enforcement
