# n8n CRM Callback Endpoints

## Purpose

Step 60 adds FastAPI callback endpoint skeletons for future n8n CRM workflows. These endpoints let n8n post CRM collection, analysis, scoring, routing, and communication results back into PostgreSQL without changing the frontend or n8n workflows yet.

## Endpoints Added

- `POST /api/n8n/crm/collect-result`
- `POST /api/n8n/crm/analysis-result`
- `POST /api/n8n/crm/scoring-result`
- `POST /api/n8n/crm/routing-result`
- `POST /api/n8n/crm/communication-result`

## Tables Updated

- `crm_leads`
- `crm_interactions`
- `workflow_executions` when optional workflow data is provided
- `agent_runs` when optional agent run data is provided

## Example Payloads

### Collect Result

```json
{
  "lead_id": "lead_n8n_001",
  "full_name": "New Prospect",
  "email": "prospect@example.com",
  "phone": "+216 00 000 004",
  "company_name": "Prospect Group",
  "source": "web",
  "message": "We want to automate CRM follow-up.",
  "workflow": {
    "workflow_name": "CRM Lead Collection Flow",
    "process": "CRM",
    "trigger_source": "n8n webhook",
    "status": "success",
    "agent_name": "Lead Collection Agent"
  },
  "agent_run": {
    "agent_id": "agent_lead_collection",
    "agent_name": "Lead Collection Agent",
    "process": "CRM",
    "status": "success"
  }
}
```

### Analysis Result

```json
{
  "lead_id": "lead_001",
  "sentiment": "positive",
  "intention": "purchase-ready",
  "urgency": "high",
  "ai_summary": "Lead has strong intent and a clear automation need."
}
```

### Scoring Result

```json
{
  "lead_id": "lead_001",
  "lead_score": 94,
  "status": "hot",
  "priority": "high"
}
```

### Routing Result

```json
{
  "lead_id": "lead_001",
  "recommended_action": "Assign to CRM Manager and schedule a discovery call.",
  "next_action": "Schedule discovery call",
  "customer_status": "qualified"
}
```

### Communication Result

```json
{
  "lead_id": "lead_001",
  "channel": "email",
  "subject": "Follow-up on your automation request",
  "summary": "Drafted a personalized CRM automation follow-up email.",
  "next_action": "Review email draft",
  "status": "draft",
  "sent": false
}
```

## How To Test In Swagger

1. Start PostgreSQL:

   ```powershell
   docker compose up -d postgres
   ```

2. Start FastAPI from the backend folder:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

3. Open Swagger:

   ```text
   http://127.0.0.1:8000/docs
   ```

4. Use the `n8n_callbacks` endpoints to submit the example payloads.

5. Verify the database rows with psql:

   ```sql
   SELECT id, full_name, status, lead_score, priority FROM crm_leads;
   SELECT id, lead_id, interaction_type, summary FROM crm_interactions;
   SELECT id, workflow_name, status FROM workflow_executions;
   SELECT id, agent_id, status FROM agent_runs;
   ```

## Not Implemented Yet

- n8n workflow modification
- Odoo sync
- Real auth/RBAC
- Frontend changes
- Email sending approval flow
