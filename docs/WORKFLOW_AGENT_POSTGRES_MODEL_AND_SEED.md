# Workflow And Agent PostgreSQL Model And Seed

## Purpose

Step 56 adds PostgreSQL models, table creation support, and seed data for Workflow Monitoring and AI Agent Center data. This prepares persistence for a later step without changing the current Workflow Monitoring or AI Agent Center API behavior.

## Tables Added

- `workflow_executions`
- `agent_runs`

## Workflow Execution Columns Created

- `id`
- `related_object_type`
- `related_object_id`
- `workflow_name`
- `process`
- `trigger_source`
- `status`
- `started_at`
- `finished_at`
- `duration_seconds`
- `error_message`
- `result_summary`
- `input_summary`
- `output_summary`
- `agent_name`
- `created_at`
- `updated_at`

## Agent Run Columns Created

- `id`
- `agent_id`
- `agent_name`
- `process`
- `workflow_execution_id`
- `requested_by`
- `requested_at`
- `status`
- `started_at`
- `finished_at`
- `input_summary`
- `output_summary`
- `error_message`
- `created_at`
- `updated_at`

## Seeded Workflow Executions

- `exec_001` - Leave Request Approval Flow, Leave Management, success
- `exec_002` - CRM Lead Scoring Flow, CRM, failed
- `exec_003` - Agent Manual Run Flow, AI Agents, queued

## Seeded Agent Runs

- `run_001` - Lead Scoring Agent, CRM, failed
- `run_002` - Leave Validation Agent, Leave Management, success
- `run_003` - Lead Scoring Agent, CRM, queued

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
SELECT id, workflow_name, process, status FROM workflow_executions;
SELECT id, agent_id, agent_name, process, status FROM agent_runs;
```

## Not Implemented Yet

- Workflow Monitoring endpoint replacement
- AI Agent Center endpoint replacement
- Frontend changes
- n8n real execution
- Odoo sync
- Real AI execution
- Authentication/RBAC enforcement
