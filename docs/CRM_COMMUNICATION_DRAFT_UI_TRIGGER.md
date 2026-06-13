# CRM Communication Draft UI Trigger

## Purpose

Step 61.4 adds a user-facing trigger for the validated CRM communication draft workflow.

Target flow:

```text
CRM Lead Details -> Generate Communication Draft -> FastAPI -> n8n Workflow 02 -> FastAPI callback -> PostgreSQL -> refreshed CRM Lead Details
```

## Backend Endpoint

FastAPI endpoint:

```text
POST /api/crm/leads/{lead_id}/generate-communication-draft
```

Behavior:

- Loads the CRM lead from PostgreSQL.
- Returns `404` if the lead does not exist.
- Sends the current lead context to n8n.
- Returns a clean API response with the lead id and n8n response.

Success response shape:

```json
{
  "success": true,
  "message": "Communication draft workflow triggered successfully.",
  "data": {
    "lead_id": "lead_n8n_trace_test_001",
    "n8n_response": {}
  },
  "error": null
}
```

## n8n Workflow Triggered

Workflow:

```text
FP_CRM_02_Communication_Draft
```

Webhook path:

```text
flowpilot-crm-communication-draft
```

FastAPI calls:

```text
{N8N_WEBHOOK_BASE_URL}/flowpilot-crm-communication-draft
```

The n8n workflow must be active when using the production webhook URL.

## Environment Variables

Backend defaults for local development:

```env
N8N_WEBHOOK_BASE_URL=http://localhost:5678/webhook
FLOWPILOT_N8N_SHARED_SECRET=flowpilot-test-secret
```

FastAPI sends the shared secret header:

```text
X-FlowPilot-Secret: flowpilot-test-secret
```

## Frontend Button Behavior

Page:

```text
/crm-lead-details
```

Button:

```text
Generate Communication Draft
```

Behavior:

- Disabled while the lead detail is loading.
- Disabled when the page is showing offline sample fallback data.
- Shows `Generating...` while the request is in progress.
- Shows `Communication draft generated successfully.` on success.
- Shows `Communication draft could not be generated.` on failure.
- Refetches the current lead detail after success so `interaction_history` updates.

## Test Steps

1. Start PostgreSQL:

   ```powershell
   cd D:\SMA_PFE
   docker compose up -d postgres
   ```

2. Start FastAPI:

   ```powershell
   cd D:\SMA_PFE\backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

3. Start n8n and activate:

   ```text
   FP_CRM_02_Communication_Draft
   ```

4. Start React:

   ```powershell
   cd D:\SMA_PFE\frontend
   npm.cmd run dev
   ```

5. Open:

   ```text
   /crm-lead-details
   ```

6. Click `Generate Communication Draft`.

7. Confirm FastAPI logs show the trigger endpoint being called.

8. Confirm n8n execution succeeds.

9. Confirm the n8n callback returns `200` for:

   ```text
   POST /api/n8n/crm/communication-result
   ```

10. Confirm the CRM Lead Details page refreshes and shows the new draft interaction.

## SQL Verification

CRM interaction:

```sql
SELECT lead_id, interaction_type, channel, summary, created_at
FROM crm_interactions
WHERE lead_id = 'lead_n8n_trace_test_001'
ORDER BY created_at DESC;
```

Expected:

```text
communication_draft
```

Workflow trace:

```sql
SELECT id, workflow_name, status, related_object_id, created_at
FROM workflow_executions
WHERE related_object_id = 'lead_n8n_trace_test_001'
ORDER BY created_at DESC;
```

Expected workflow:

```text
FP_CRM_02_Communication_Draft
```

Agent trace:

```sql
SELECT id, agent_id, agent_name, status, workflow_execution_id, created_at
FROM agent_runs
ORDER BY created_at DESC
LIMIT 10;
```

Expected agent:

```text
crm_communication_agent
```

## Not Implemented

- No email sending.
- No Odoo sync.
- No auth/RBAC.
- No Workflow 03 trigger yet.
