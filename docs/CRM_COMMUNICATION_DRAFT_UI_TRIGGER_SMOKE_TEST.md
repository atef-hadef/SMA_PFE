# FlowPilot AI CRM Communication Draft UI Trigger Smoke Test

Date: 2026-05-01  
Status: Step 61.4 completed

---

## 1. Purpose

This document validates the integration of the CRM Communication Draft workflow trigger from the FlowPilot AI user interface.

The goal is to confirm that the user can generate a CRM communication draft directly from the CRM Lead Details page instead of manually calling the n8n webhook with PowerShell.

Validated feature:

```text
CRM Lead Details
→ Generate Communication Draft button
→ FastAPI endpoint
→ n8n Workflow 02
→ FastAPI callback
→ PostgreSQL
→ React interaction history refresh
```

---

## 2. Feature validated

The following feature was added and tested:

```text
Generate Communication Draft
```

Location:

```text
CRM Lead Details page
```

Backend endpoint:

```text
POST /api/crm/leads/{lead_id}/generate-communication-draft
```

n8n workflow triggered:

```text
FP_CRM_02_Communication_Draft
```

n8n webhook path:

```text
flowpilot-crm-communication-draft
```

FastAPI callback used by n8n:

```text
POST /api/n8n/crm/communication-result
```

---

## 3. Architecture validated

```text
React CRM Lead Details
→ FastAPI trigger endpoint
→ n8n Workflow 02
→ OpenRouter / fallback draft generation
→ FastAPI communication-result callback
→ PostgreSQL
→ React refreshes lead detail
```

PostgreSQL tables involved:

```text
crm_leads
crm_interactions
workflow_executions
agent_runs
```

---

## 4. Backend endpoint added

Endpoint:

```text
POST /api/crm/leads/{lead_id}/generate-communication-draft
```

Purpose:

```text
Trigger the n8n communication draft workflow for an existing CRM lead.
```

Backend behavior:

```text
1. Load the CRM lead from PostgreSQL.
2. Build a payload using the lead context.
3. Send the payload to n8n Workflow 02.
4. Wait for the n8n webhook response.
5. Return a clean response to the React frontend.
```

Expected success response shape:

```json
{
  "success": true,
  "message": "Communication draft workflow triggered successfully.",
  "data": {
    "lead_id": "lead_n8n_trace_test_001",
    "n8n_response": {
      "ok": true,
      "message": "Communication draft generated",
      "lead_id": "lead_n8n_trace_test_001"
    }
  },
  "error": null
}
```

---

## 5. Frontend behavior added

Page:

```text
/crm-lead-details
```

Button added:

```text
Generate Communication Draft
```

Expected frontend behavior:

```text
1. User opens CRM Lead Details.
2. User clicks Generate Communication Draft.
3. Button enters loading state.
4. React calls FastAPI.
5. FastAPI triggers n8n.
6. n8n generates the communication draft.
7. n8n calls FastAPI communication-result callback.
8. PostgreSQL stores the communication draft interaction.
9. React refreshes the lead detail.
10. Interaction History shows the new communication_draft entry.
```

Expected success message:

```text
Communication draft generated successfully.
```

Expected error message:

```text
Communication draft could not be generated.
```

---

## 6. Required runtime services

Before testing, the following services must be running:

```text
PostgreSQL
FastAPI backend
n8n
React frontend
```

---

## 7. Environment configuration

The backend uses the following n8n webhook base URL:

```text
N8N_WEBHOOK_BASE_URL=http://localhost:5678/webhook
```

The local MVP shared secret is:

```text
FLOWPILOT_N8N_SHARED_SECRET=flowpilot-test-secret
```

The backend sends this header to n8n:

```text
X-FlowPilot-Secret: flowpilot-test-secret
```

Important:

```text
For production-like usage, this value should be moved to a secure environment variable.
```

---

## 8. Manual test procedure

### Step 1: Start PostgreSQL

```powershell
cd D:\SMA_PFE
docker compose up -d postgres
```

### Step 2: Start FastAPI backend

```powershell
cd D:\SMA_PFE\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Expected backend URL:

```text
http://127.0.0.1:8000
```

### Step 3: Start n8n

Open:

```text
http://localhost:5678
```

Open workflow:

```text
FP_CRM_02_Communication_Draft
```

Activate the workflow.

Important:

```text
The UI trigger uses the production webhook URL:
http://localhost:5678/webhook/flowpilot-crm-communication-draft
```

It does not use:

```text
/webhook-test/flowpilot-crm-communication-draft
```

### Step 4: Start React frontend

```powershell
cd D:\SMA_PFE\frontend
npm.cmd run dev
```

Expected frontend URL:

```text
http://localhost:5173
```

### Step 5: Open CRM Lead Details

Open:

```text
http://localhost:5173/crm-lead-details
```

Click:

```text
Generate Communication Draft
```

---

## 9. Expected FastAPI logs

After clicking the button, the FastAPI terminal should show:

```text
POST /api/crm/leads/{lead_id}/generate-communication-draft 200 OK
```

Then, after n8n calls the callback:

```text
POST /api/n8n/crm/communication-result 200 OK
```

---

## 10. Expected n8n behavior

Workflow:

```text
FP_CRM_02_Communication_Draft
```

Expected nodes executed successfully:

```text
FastAPI Trigger - Generate Communication Draft
Prepare Communication Context
Authorized + Valid?
OpenRouter - Generate Email Draft
Parse Communication Draft
Callback Communication Result
Respond Draft Generated
```

Expected webhook response from n8n:

```json
{
  "ok": true,
  "message": "Communication draft generated",
  "lead_id": "..."
}
```

---

## 11. SQL verification

Open PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

### Verify communication draft interaction

```sql
SELECT lead_id, interaction_type, channel, summary, created_at
FROM crm_interactions
WHERE interaction_type = 'communication_draft'
ORDER BY created_at DESC
LIMIT 5;
```

Expected:

```text
A recent row exists.
interaction_type = communication_draft
channel = email
```

### Verify Workflow 02 execution trace

```sql
SELECT id, workflow_name, process, status, related_object_id, created_at
FROM workflow_executions
WHERE workflow_name ILIKE '%Communication Draft%'
ORDER BY created_at DESC
LIMIT 5;
```

Expected:

```text
workflow_name contains Communication Draft
process = CRM
status = success
```

### Verify communication agent run

```sql
SELECT id, agent_id, agent_name, process, status, created_at
FROM agent_runs
WHERE agent_id = 'crm_communication_agent'
ORDER BY created_at DESC
LIMIT 5;
```

Expected:

```text
agent_id = crm_communication_agent
agent_name = CRM Communication Agent
process = CRM
status = success
```

Exit PostgreSQL:

```sql
\q
```

---

## 12. Frontend verification

After clicking the button, verify:

```text
The button shows a loading state.
A success message appears.
The CRM Lead Details page refreshes.
The Interaction History includes communication_draft.
No email is sent automatically.
```

Pages to verify:

```text
/crm-lead-details
/workflow-monitoring
/ai-agents
```

Expected:

```text
CRM Lead Details shows the communication draft in the interaction history.
Workflow Monitoring shows the Communication Draft workflow trace.
AI Agent Center shows crm_communication_agent in recent runs.
```

---

## 13. What is now real

The following feature is now implemented and tested:

```text
User-triggered CRM communication draft generation from the FlowPilot AI interface.
```

The validated flow is:

```text
React UI
→ FastAPI
→ n8n
→ FastAPI callback
→ PostgreSQL
→ React UI refresh
```

This makes the CRM process more realistic because the user can trigger a business automation directly from the web application.

---

## 14. What is intentionally not implemented

The following features are intentionally not included in Step 61.4:

```text
No automatic email sending
No email approval/send UI yet
No Odoo CRM synchronization
No real authentication
No real RBAC enforcement
No Workflow 03 trigger yet
No inactive customer automation
No VIP customer automation
```

---

## 15. Security notes

Current local test secret:

```text
flowpilot-test-secret
```

For future production-like usage:

```text
Use environment variables.
Do not commit real secrets.
Do not expose API keys in workflow JSON.
Do not send emails automatically without human validation.
```

Recommended future environment variables:

```text
N8N_WEBHOOK_BASE_URL
FLOWPILOT_N8N_SHARED_SECRET
FLOWPILOT_FASTAPI_CALLBACK_SECRET
OPENROUTER_API_KEY
OPENROUTER_MODEL
FLOWPILOT_APP_URL
```

---

## 16. Completion checklist

Step 61.4 is considered complete if:

```text
[OK] Generate Communication Draft button appears in CRM Lead Details.
[OK] Button calls FastAPI successfully.
[OK] FastAPI triggers n8n Workflow 02.
[OK] n8n returns ok = true.
[OK] n8n calls FastAPI communication-result callback.
[OK] FastAPI communication-result returns 200 OK.
[OK] crm_interactions contains communication_draft.
[OK] workflow_executions contains Communication Draft trace.
[OK] agent_runs contains crm_communication_agent.
[OK] CRM Lead Details refreshes after generation.
[OK] No email is sent automatically.
```

---

## 17. Completion status

Step 61.4 completed:

```text
FastAPI and React trigger for CRM communication draft added and tested.
```

Workflow 01 and Workflow 02 are now fully integrated and user-triggerable from the FlowPilot AI project.

---

## 18. Recommended next step

Recommended next step:

```text
Step 62 — Decide Next CRM Integration Direction
```

Available options:

```text
Option A — Test Workflow 03 Human Conversion to Customer
Option B — Add email approval/send UI later
Option C — Add inactive customer and VIP backend endpoints
Option D — Start Odoo CRM synchronization planning
Option E — Pause CRM workflows and focus on authentication/RBAC
```

Recommended realistic next step:

```text
Test Workflow 03 only if the project needs a complete Lead → Prospect → Customer demo.
Otherwise, keep Workflow 03+ for later and focus on final MVP polish, auth/RBAC, or Odoo planning.
```