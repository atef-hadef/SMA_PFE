# FlowPilot AI Backend

Minimal FastAPI backend skeleton for the FlowPilot AI project.

This backend currently mixes PostgreSQL-backed MVP flows with mock service
responses for modules that have not been persisted yet. It does not connect
Odoo, real authentication, or real RBAC yet.

## Setup

From the `backend` folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python -m uvicorn app.main:app --reload
```

## PostgreSQL

PostgreSQL Docker database is available. FastAPI has a minimal database
connection health check, and selected MVP flows now use persisted data.

From the project root:

```powershell
docker compose up -d postgres
```

Install backend dependencies after pulling this step:

```powershell
python -m pip install -r requirements.txt
```

Test the database connection:

- Database health: http://127.0.0.1:8000/api/health/db

## Create Database Tables

From the `backend` folder:

```powershell
python scripts/create_tables.py
```

This creates the initial MVP tables manually for local development. Alembic
migrations are not configured yet.

## Upgrade CRM Schema

For an existing database, run the safe CRM schema upgrade before reseeding:

```powershell
python scripts/upgrade_crm_schema.py
```

## Seed Database

From the `backend` folder:

```powershell
python scripts/seed_database.py
```

The seed script is idempotent and can be run multiple times without duplicating
the initial roles, permissions, users, sample leave requests, CRM leads,
workflow executions, or agent runs.

## Leave Request Persistence

Leave Request and Manager Approval endpoints now read and write PostgreSQL
`leave_requests` data. Until real authentication is added, new leave requests
use `user_010` as the employee and approval decisions use `user_020` as the
reviewing manager.

## CRM Lead Data Preparation

The `crm_leads` table and initial CRM lead seed data are available for CRM
persistence.

## CRM Lead Persistence

CRM lead list, detail, and create endpoints now read and write PostgreSQL
`crm_leads` data. AI scoring, sentiment generation, urgency detection, n8n, and
Odoo sync are still not connected.

## Workflow And Agent Data Preparation

The `workflow_executions` and `agent_runs` tables and initial seed data are
available for Workflow Monitoring and AI Agent Center persistence. Those API
endpoints now read from PostgreSQL. Manual workflow retry and manual agent run
actions create queued MVP records, but they do not call n8n yet.

## n8n CRM Callback Skeletons

FastAPI exposes CRM callback endpoints under `/api/n8n/crm/*` so n8n workflows
can write collection, analysis, scoring, routing, and communication results
into PostgreSQL.

## n8n CRM Communication Draft Trigger

FastAPI can trigger the active `FP_CRM_02_Communication_Draft` n8n workflow from
CRM Lead Details:

- `POST /api/crm/leads/{lead_id}/generate-communication-draft`

Local development defaults:

```env
N8N_WEBHOOK_BASE_URL=http://localhost:5678/webhook
FLOWPILOT_N8N_SHARED_SECRET=flowpilot-test-secret
```

## Test URLs

- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health
- Database health: http://127.0.0.1:8000/api/health/db
- Dashboard summary: http://127.0.0.1:8000/api/dashboard/summary

## Current Endpoints

- `GET /api/health`
- `GET /api/health/db`
- `GET /api/dashboard/summary`
- `POST /api/leave-requests`
- `GET /api/leave-requests/pending`
- `POST /api/leave-requests/{request_id}/approve`
- `POST /api/leave-requests/{request_id}/reject`
- `GET /api/crm/leads`
- `GET /api/crm/leads/{lead_id}`
- `POST /api/crm/leads`
- `POST /api/crm/leads/{lead_id}/generate-communication-draft`
- `GET /api/workflow-executions`
- `GET /api/workflow-executions/{execution_id}`
- `POST /api/workflow-executions/{execution_id}/retry`
- `GET /api/agents`
- `GET /api/agents/{agent_id}`
- `POST /api/agents/{agent_id}/run`
- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/{user_id}`
- `POST /api/users/{user_id}/deactivate`
- `GET /api/roles`
- `PUT /api/roles/{role_id}/permissions`
- `POST /api/n8n/crm/collect-result`
- `POST /api/n8n/crm/analysis-result`
- `POST /api/n8n/crm/scoring-result`
- `POST /api/n8n/crm/routing-result`
- `POST /api/n8n/crm/communication-result`

## Not Implemented Yet

- Admin PostgreSQL persistence
- Additional n8n workflow calls beyond the CRM communication draft trigger
- Real authentication
- Protected routes
- Odoo sync
- Alembic migrations
