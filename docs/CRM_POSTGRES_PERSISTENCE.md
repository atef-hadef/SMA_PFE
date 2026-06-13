# CRM PostgreSQL Persistence

## Purpose

Step 54 replaces CRM mock backend logic with PostgreSQL-backed service logic while preserving the existing CRM API routes and frontend-compatible response shapes.

## Endpoints Changed

- `GET /api/crm/leads`
- `GET /api/crm/leads/{lead_id}`
- `POST /api/crm/leads`

## Table Used

- `crm_leads`

## Field Mappings

- `full_name` -> `name`
- `company_name` -> `company`
- `lead_score` -> `score`

The `assigned_to` field is resolved to the assigned user's name when possible. If the user cannot be found, the stored user id is returned.

## How To Test From Frontend

1. Start PostgreSQL:

   ```powershell
   docker compose up -d postgres
   ```

2. Ensure tables and seed data exist:

   ```powershell
   cd backend
   python scripts/create_tables.py
   python scripts/seed_database.py
   ```

3. Start FastAPI:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

4. Open the CRM Leads page:

   ```text
   /crm-leads
   ```

5. Open the CRM Lead Details page:

   ```text
   /crm-lead-details
   ```

The details page should continue loading `lead_001`.

## How To Verify With psql

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Then run:

```sql
SELECT id, full_name, company_name, status, lead_score FROM crm_leads;
```

## What Remains Mock-Only

- AI scoring logic
- Sentiment generation
- Urgency detection
- CRM analysis workflow
- Email sending
- n8n integration
- Odoo sync
- Authentication/RBAC enforcement
