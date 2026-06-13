# FlowPilot AI Workflow Monitoring and AI Agent Center PostgreSQL Persistence Smoke Test

Date: 2026-04-30  
Status: Step 57 completed

## 1. Step 57 completion summary

Step 57 is complete.

Workflow Monitoring and AI Agent Center backend logic has been replaced with PostgreSQL-backed logic.

Confirmed outcomes:

- `GET /api/workflow-executions` now reads workflow executions from PostgreSQL.
- `GET /api/workflow-executions/{execution_id}` now reads workflow execution details from PostgreSQL.
- `POST /api/workflow-executions/{execution_id}/retry` now creates or returns a PostgreSQL-backed queued retry record.
- `GET /api/agents` now derives agent summaries from `agent_runs`.
- `GET /api/agents/{agent_id}` now reads agent details and recent runs from PostgreSQL.
- `POST /api/agents/{agent_id}/run` now creates a queued agent run in PostgreSQL.
- Workflow Monitoring frontend page still works.
- AI Agent Center frontend page still works.
- No n8n execution is connected yet.
- No Odoo integration is connected yet.
- Real authentication and RBAC enforcement are not implemented yet.

## 2. Integration flows tested

### Workflow execution list flow

```text
React Workflow Monitoring Page
→ GET /api/workflow-executions
→ FastAPI workflow endpoint
→ SQLAlchemy service logic
→ PostgreSQL workflow_executions table
```

### Workflow execution detail flow

```text
React Workflow Monitoring Page
→ GET /api/workflow-executions/exec_001
→ FastAPI workflow endpoint
→ PostgreSQL workflow_executions table
→ related agent_runs if available
```

### Workflow retry flow

```text
Retry Execution button
→ POST /api/workflow-executions/{execution_id}/retry
→ FastAPI creates queued retry record
→ PostgreSQL workflow_executions table
```

### AI agent list flow

```text
React AI Agent Center Page
→ GET /api/agents
→ FastAPI agent endpoint
→ SQLAlchemy derives agent summaries from agent_runs
→ PostgreSQL agent_runs table
```

### AI agent detail flow

```text
React AI Agent Center Page
→ GET /api/agents/agent_lead_scoring
→ FastAPI agent endpoint
→ PostgreSQL agent_runs table
→ recent_runs returned to frontend
```

### Manual agent run flow

```text
Run Agent button
→ POST /api/agents/{agent_id}/run
→ FastAPI creates queued agent run
→ PostgreSQL agent_runs table
```

## 3. Backend endpoints tested

The following endpoints were tested:

```text
GET  /api/workflow-executions
GET  /api/workflow-executions/{execution_id}
POST /api/workflow-executions/{execution_id}/retry

GET  /api/agents
GET  /api/agents/{agent_id}
POST /api/agents/{agent_id}/run
```

Example local URLs:

```text
GET  http://127.0.0.1:8000/api/workflow-executions
GET  http://127.0.0.1:8000/api/workflow-executions/exec_001
POST http://127.0.0.1:8000/api/workflow-executions/exec_002/retry

GET  http://127.0.0.1:8000/api/agents
GET  http://127.0.0.1:8000/api/agents/agent_lead_scoring
POST http://127.0.0.1:8000/api/agents/agent_lead_scoring/run
```

## 4. Frontend pages tested

Frontend routes tested:

```text
http://localhost:5173/workflow-monitoring
http://localhost:5173/ai-agents
```

## 5. Database tables used

The following PostgreSQL tables are involved:

```text
workflow_executions
agent_runs
```

Supporting tables already exist:

```text
users
crm_leads
leave_requests
```

## 6. Manual test procedure

### Step 1: Start PostgreSQL

From the project root:

```powershell
cd D:\SMA_PFE
docker compose up -d postgres
```

Verify the container:

```powershell
docker ps
```

Expected container:

```text
flowpilot_postgres
```

### Step 2: Start FastAPI backend

From the backend folder:

```powershell
cd D:\SMA_PFE\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Expected backend URL:

```text
http://127.0.0.1:8000
```

### Step 3: Start React frontend

From the frontend folder:

```powershell
cd D:\SMA_PFE\frontend
npm.cmd run dev
```

Expected frontend URL:

```text
http://localhost:5173
```

## 7. Test A — Workflow Monitoring page

Open:

```text
http://localhost:5173/workflow-monitoring
```

Expected frontend behavior:

```text
Workflow Monitoring page opens normally.
Workflow execution rows appear.
No blank screen appears.
No frontend crash occurs.
```

Expected visible workflows:

```text
Leave Request Approval Flow
CRM Lead Scoring Flow
Agent Manual Run Flow
```

Expected network behavior:

```text
GET /api/workflow-executions
Status Code: 200
```

Expected backend behavior:

```text
FastAPI reads workflow executions from workflow_executions.
```

## 8. Test B — Workflow execution detail

In the Workflow Monitoring page, confirm the selected execution details load.

Expected network behavior:

```text
GET /api/workflow-executions/exec_001
Status Code: 200
```

Expected detail data:

```text
workflow_name
process
status
trigger_source
duration_seconds
input_summary
output_summary
result_summary
agent_name
related_agent_runs
```

## 9. Test C — Retry workflow execution

Click:

```text
Retry Execution
```

Expected frontend behavior:

```text
Success message appears.
Page does not crash.
```

Expected network behavior:

```text
POST /api/workflow-executions/{execution_id}/retry
Status Code: 200
```

Expected backend behavior:

```text
A queued retry execution is created or returned using PostgreSQL-backed logic.
```

Verify in PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Run:

```sql
SELECT id, workflow_name, process, status, trigger_source, created_at
FROM workflow_executions
ORDER BY created_at DESC;
```

Expected result:

```text
A new queued retry execution appears, or a retry response is returned.
status = queued
trigger_source = Manual Retry
```

Exit:

```sql
\q
```

## 10. Test D — AI Agent Center page

Open:

```text
http://localhost:5173/ai-agents
```

Expected frontend behavior:

```text
AI Agent Center page opens normally.
Agent list appears.
No blank screen appears.
No frontend crash occurs.
```

Expected visible agents:

```text
Lead Scoring Agent
Leave Validation Agent
```

Expected network behavior:

```text
GET /api/agents
Status Code: 200
```

Expected backend behavior:

```text
FastAPI derives agent summaries from agent_runs.
```

## 11. Test E — AI agent details

Open or refresh:

```text
http://localhost:5173/ai-agents
```

Expected network behavior:

```text
GET /api/agents/agent_lead_scoring
Status Code: 200
```

Expected detail fields:

```text
agent id
agent name
process
status
success rate
description
tools
related workflows
recent runs
```

Expected backend behavior:

```text
recent_runs are read from agent_runs.
```

## 12. Test F — Manual agent run

Click:

```text
Run Agent
```

Expected frontend behavior:

```text
Agent run queued successfully.
Page does not crash.
```

Expected network behavior:

```text
POST /api/agents/agent_lead_scoring/run
Status Code: 200
```

Expected backend behavior:

```text
A new queued row is inserted into agent_runs.
```

Verify in PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Run:

```sql
SELECT id, agent_id, agent_name, process, status, requested_at, created_at
FROM agent_runs
ORDER BY created_at DESC;
```

Expected result:

```text
A new manual agent run appears.
agent_id = agent_lead_scoring
status = queued
```

Exit:

```sql
\q
```

## 13. SQL verification summary

Workflow executions:

```sql
SELECT id, workflow_name, process, status
FROM workflow_executions;
```

Expected seeded rows include:

```text
exec_001 | Leave Request Approval Flow | Leave Management | success
exec_002 | CRM Lead Scoring Flow       | CRM              | failed
exec_003 | Agent Manual Run Flow       | AI Agents        | queued
```

Agent runs:

```sql
SELECT id, agent_id, agent_name, process, status
FROM agent_runs;
```

Expected seeded rows include:

```text
run_001 | agent_lead_scoring     | Lead Scoring Agent     | CRM              | failed
run_002 | agent_leave_validation | Leave Validation Agent | Leave Management | success
run_003 | agent_lead_scoring     | Lead Scoring Agent     | CRM              | queued
```

## 14. What is now real

The following parts are now backed by PostgreSQL:

```text
Workflow execution list
Workflow execution details
Workflow retry queue record
Agent list derived from agent runs
Agent details
Recent agent runs
Manual agent run queue record
```

## 15. What remains computed or temporary

The following parts remain computed or static for MVP purposes:

```text
Agent descriptions
Agent tools
Related workflow labels
Success rate calculation logic
Manual retry execution does not trigger real n8n yet
Manual agent run does not trigger real n8n yet
```

## 16. What is intentionally not implemented yet

The following features were intentionally not implemented in Step 57:

```text
No n8n real workflow execution
No Odoo integration
No real authentication
No real RBAC enforcement
No frontend redesign
No new database tables
No Alembic migrations
No production monitoring
```

## 17. Completion checklist

Step 57 is considered complete if:

```text
GET /api/workflow-executions reads from PostgreSQL.
Workflow Monitoring page displays PostgreSQL workflow executions.
GET /api/workflow-executions/exec_001 reads from PostgreSQL.
Retry Execution creates or returns PostgreSQL-backed queued execution.
GET /api/agents derives agents from PostgreSQL agent_runs.
AI Agent Center page displays PostgreSQL-derived agents.
GET /api/agents/agent_lead_scoring returns PostgreSQL-backed recent runs.
Run Agent creates queued row in agent_runs.
Leave persistence still works.
CRM persistence still works.
Database health endpoint still works.
Frontend pages still work.
```

## 18. Recommended next step

Recommended next step:

```text
Step 59 — CRM n8n Database Alignment Plan
```

Purpose:

```text
Align existing n8n CRM workflows with the current FlowPilot AI database schema.
```

Current important tables for n8n alignment:

```text
crm_leads
crm_interactions
workflow_executions
agent_runs
```

Legacy workflow tables that should not remain the final source of truth:

```text
leads
lead_analysis
lead_scores
lead_actions
lead_communications
lead_followups
```

The recommended integration strategy is:

```text
FastAPI remains the source of truth for PostgreSQL.
n8n executes automation workflows.
n8n returns results to FastAPI callbacks.
FastAPI updates crm_leads, crm_interactions, workflow_executions, and agent_runs.
```