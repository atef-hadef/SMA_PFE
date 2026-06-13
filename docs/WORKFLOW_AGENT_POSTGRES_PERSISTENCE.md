# FlowPilot AI Workflow and Agent PostgreSQL Persistence

Date: 2026-04-30  
Status: Step 57 completed

## 1. Purpose

Step 57 replaces the mock backend logic for Workflow Monitoring and AI Agent
Center with PostgreSQL-backed service logic.

The frontend routes and API endpoint paths are unchanged. The responses keep
the existing frontend-compatible aliases while adding database-oriented fields
from the persisted tables.

## 2. Endpoints changed

Workflow Monitoring:

- `GET /api/workflow-executions`
- `GET /api/workflow-executions/{execution_id}`
- `POST /api/workflow-executions/{execution_id}/retry`

AI Agent Center:

- `GET /api/agents`
- `GET /api/agents/{agent_id}`
- `POST /api/agents/{agent_id}/run`

## 3. Tables used

- `workflow_executions`
- `agent_runs`

## 4. Workflow Monitoring behavior

`GET /api/workflow-executions` reads from `workflow_executions` and returns
workflow execution rows ordered by creation time.

`GET /api/workflow-executions/{execution_id}` reads one execution by id and
loads related agent runs from `agent_runs.workflow_execution_id`.

The response keeps frontend aliases:

- `related_object`
- `triggered_by`
- `duration`
- `agent`

It also includes database fields such as:

- `related_object_type`
- `related_object_id`
- `trigger_source`
- `duration_seconds`
- `agent_name`
- `created_at`
- `updated_at`
- `related_agent_runs`

## 5. Retry behavior in MVP

`POST /api/workflow-executions/{execution_id}/retry` checks the original
execution exists, then creates a new queued `workflow_executions` row.

The retry row uses:

- `id`: `exec_retry_<timestamp>`
- `trigger_source`: `Manual Retry`
- `status`: `queued`
- `input_summary`: `Manual retry requested from Workflow Monitoring UI`
- `result_summary`: `Retry queued`
- `agent_name`: copied from the original execution

No real n8n workflow is executed yet.

## 6. Agent summaries derived from `agent_runs`

There is no dedicated `agents` table yet, so `GET /api/agents` derives agent
records from distinct `agent_runs.agent_id` groups.

Computed fields:

- `name`: latest run `agent_name`
- `process`: latest run `process`
- `status`: `active`
- `type`: `automation_agent`
- `success_rate`: successful runs divided by total runs
- `last_execution`: latest `requested_at`, `started_at`, or `created_at`
- `total_runs`: count of runs per agent

## 7. Manual agent run in MVP

`POST /api/agents/{agent_id}/run` checks the agent exists in `agent_runs`, then
creates a queued `agent_runs` row.

The manual run uses:

- `id`: `run_manual_<timestamp>`
- `requested_by`: `user_030`
- `requested_at`: current UTC datetime
- `status`: `queued`
- `input_summary`: `Manual test run requested from AI Agent Center`
- `output_summary`: `Awaiting execution`

No real n8n execution is triggered yet.

## 8. How to test

Frontend routes:

- `/workflow-monitoring`
- `/ai-agents`

Swagger endpoints:

- `GET /api/workflow-executions`
- `GET /api/workflow-executions/exec_001`
- `POST /api/workflow-executions/exec_001/retry`
- `GET /api/agents`
- `GET /api/agents/agent_lead_scoring`
- `POST /api/agents/agent_lead_scoring/run`

## 9. SQL verification

```sql
SELECT id, workflow_name, process, status FROM workflow_executions;
```

```sql
SELECT id, agent_id, agent_name, process, status FROM agent_runs;
```

## 10. What remains mock/computed

- Static agent descriptions
- Static tools list
- No real n8n execution
- No real Odoo sync
- No real auth/RBAC
