# FlowPilot AI CRM n8n Database Alignment Plan

Date: 2026-04-30  
Status: Step 59 planning only

## 1. Purpose of this document

This document defines how the existing CRM n8n workflows should be aligned with the current FlowPilot AI PostgreSQL schema.

The goal is to avoid database duplication and make sure the web application, FastAPI backend, PostgreSQL database, and n8n workflows all work with the same business data model.

This is a planning step only.

No backend code is changed in this step.  
No n8n workflow is modified in this step.  
No frontend code is changed in this step.

## 2. Current project state

The main FlowPilot AI MVP pages are now backed by PostgreSQL:

```text
Leave Request
Manager Approval
CRM Leads
CRM Lead Details
Workflow Monitoring
AI Agent Center
```

The current important PostgreSQL tables are:

```text
users
roles
role_permissions
leave_requests
crm_leads
crm_interactions
workflow_executions
agent_runs
```

For the CRM process, the current application source of truth should be:

```text
crm_leads
crm_interactions
workflow_executions
agent_runs
```

## 3. Current problem

The existing n8n CRM workflows were built before the current FlowPilot AI schema was stabilized.

They currently use legacy CRM tables such as:

```text
leads
lead_analysis
lead_scores
lead_actions
lead_communications
lead_followups
```

These tables should not remain the final source of truth for the FlowPilot AI web application.

The current FlowPilot AI site uses:

```text
crm_leads
crm_interactions
workflow_executions
agent_runs
```

Therefore, the n8n workflows must be aligned with the current schema before final integration.

## 4. Target architecture

The target architecture is:

```text
React Frontend
→ FastAPI Backend
→ PostgreSQL
```

For automation:

```text
FastAPI
→ n8n Webhook
→ AI / routing / communication / Odoo later
→ FastAPI callback
→ PostgreSQL update
```

Important rule:

```text
React must not call n8n directly.
```

FastAPI is the secure API layer and database controller.  
n8n is the automation engine.  
PostgreSQL stores the durable business state.  
React displays clean business information.

## 5. Recommended integration strategy

The recommended strategy is:

```text
Do not let n8n directly control the final application tables.
```

Instead:

```text
n8n executes automation
n8n returns results to FastAPI callback endpoints
FastAPI validates and updates PostgreSQL
```

This keeps the architecture clean and easier to defend.

Recommended flow:

```text
CRM lead created
→ FastAPI stores lead in crm_leads
→ FastAPI triggers n8n CRM workflow
→ n8n analyzes/scoring/routing
→ n8n calls FastAPI callback
→ FastAPI updates crm_leads, crm_interactions, workflow_executions, agent_runs
→ React displays updated data
```

## 6. Source of truth decision

Final CRM source of truth:

```text
crm_leads
```

CRM interaction history source of truth:

```text
crm_interactions
```

Workflow monitoring source of truth:

```text
workflow_executions
```

AI agent execution source of truth:

```text
agent_runs
```

Legacy workflow tables should be avoided as final source of truth:

```text
leads
lead_analysis
lead_scores
lead_actions
lead_communications
lead_followups
```

These legacy tables can be used temporarily during migration if absolutely necessary, but the final application should rely on the current FlowPilot AI tables.

## 7. Mapping from legacy n8n tables to current FlowPilot tables

### 7.1 Legacy `leads` → current `crm_leads`

| Legacy field | Current field |
|---|---|
| `lead_id` | `crm_leads.id` |
| `full_name` | `crm_leads.full_name` |
| `email` | `crm_leads.email` |
| `company` | `crm_leads.company_name` |
| `source` | `crm_leads.source` |
| `message` | `crm_leads.message` |
| `status` | `crm_leads.status` |
| `priority` | `crm_leads.priority` |
| `created_at` | `crm_leads.created_at` |
| `updated_at` | `crm_leads.updated_at` |

### 7.2 Legacy `lead_analysis` → current `crm_leads`

| Legacy field | Current field |
|---|---|
| `sentiment` | `crm_leads.sentiment` |
| `intention` | `crm_leads.intention` |
| `urgency_level` | `crm_leads.urgency` |
| `ai_summary` | `crm_leads.ai_summary` |
| `analyzed_at` | `crm_leads.updated_at` |

### 7.3 Legacy `lead_scores` → current `crm_leads`

| Legacy field | Current field |
|---|---|
| `total_score` | `crm_leads.lead_score` |
| `score_category` | `crm_leads.status` or `crm_leads.priority` |
| `scored_at` | `crm_leads.updated_at` |

Recommended mapping:

```text
score_category = hot  → crm_leads.status = hot, priority = high
score_category = warm → crm_leads.status = warm, priority = medium
score_category = cold → crm_leads.status = cold, priority = low
```

### 7.4 Legacy `lead_actions` → current `crm_interactions`

| Legacy field | Current field |
|---|---|
| `lead_id` | `crm_interactions.lead_id` |
| `action_type` | `crm_interactions.interaction_type` |
| `action_details` | `crm_interactions.summary` |
| `triggered_at` | `crm_interactions.interaction_date` |
| `action_status` | included in `summary` or future metadata |

### 7.5 Legacy `lead_communications` → current `crm_interactions`

| Legacy field | Current field |
|---|---|
| `lead_id` | `crm_interactions.lead_id` |
| `email_type` | `crm_interactions.interaction_type` |
| `recipient_email` | included in `summary` |
| `subject` | included in `summary` |
| `sent_at` | `crm_interactions.interaction_date` |
| `send_status` | included in `summary` |

Recommended interaction example:

```text
interaction_type = email_generated
channel = email
summary = Personalized follow-up email generated for the lead.
```

## 8. Workflow-by-workflow alignment plan

## 8.1 A1 — Lead Collection workflow

Current role:

```text
Collect leads from web form, email, or external API.
Normalize and validate data.
Check duplicates.
Insert or update a lead.
Trigger AI analysis workflow.
```

Current issue:

```text
The workflow writes directly to legacy table leads.
```

Recommended final behavior:

```text
A1 should call FastAPI instead of writing directly to PostgreSQL.
```

Recommended FastAPI endpoint:

```text
POST /api/n8n/crm/collect-result
```

Payload example:

```json
{
  "lead_id": "lead_xxx",
  "full_name": "Northwind Logistics",
  "email": "ops@northwind.com",
  "company_name": "Northwind Group",
  "source": "web_form",
  "message": "We are interested in sales automation.",
  "phone": "+21600000000"
}
```

FastAPI responsibility:

```text
Validate data.
Create or update crm_leads.
Insert crm_interactions row with interaction_type = lead_collected.
Create workflow_executions row.
Create agent_runs row if needed.
```

## 8.2 A2 — AI Analysis workflow

Current role:

```text
Analyze sentiment.
Detect intention.
Detect urgency.
Generate AI summary.
```

Current issue:

```text
The workflow writes to lead_analysis and updates legacy leads.
```

Recommended final behavior:

```text
A2 should return analysis results to FastAPI.
```

Recommended FastAPI endpoint:

```text
POST /api/n8n/crm/analysis-result
```

Payload example:

```json
{
  "lead_id": "lead_001",
  "sentiment": "positive",
  "intention": "purchase-ready",
  "urgency": "high",
  "ai_summary": "High-value lead with strong buying intent.",
  "processing_time_ms": 1200,
  "model_used": "mistral + sentiment-model"
}
```

FastAPI responsibility:

```text
Update crm_leads.sentiment.
Update crm_leads.intention.
Update crm_leads.urgency.
Update crm_leads.ai_summary.
Update crm_leads.updated_at.
Insert crm_interactions row with interaction_type = ai_analysis.
Update workflow_executions and agent_runs.
```

## 8.3 A3 — Predictive Scoring workflow

Current role:

```text
Compute conversion score.
Categorize lead as hot, warm, or cold.
Trigger routing workflow.
```

Current issue:

```text
The workflow writes to lead_scores and updates legacy leads.
```

Recommended final behavior:

```text
A3 should return scoring result to FastAPI.
```

Recommended FastAPI endpoint:

```text
POST /api/n8n/crm/scoring-result
```

Payload example:

```json
{
  "lead_id": "lead_001",
  "lead_score": 94,
  "score_category": "hot",
  "priority": "high",
  "scoring_details": {
    "sentiment_score": 20,
    "intention_score": 25,
    "urgency_score": 15
  }
}
```

FastAPI responsibility:

```text
Update crm_leads.lead_score.
Update crm_leads.status.
Update crm_leads.priority.
Insert crm_interactions row with interaction_type = scoring_completed.
Update workflow_executions and agent_runs.
```

## 8.4 A4 — Decision and Routing workflow

Current role:

```text
Route hot, warm, and cold leads.
Recommend next commercial action.
Optionally trigger notifications and communication workflow.
```

Current issue:

```text
The workflow writes to lead_actions and lead_followups.
```

Recommended final behavior:

```text
A4 should return routing decision to FastAPI.
```

Recommended FastAPI endpoint:

```text
POST /api/n8n/crm/routing-result
```

Payload example:

```json
{
  "lead_id": "lead_001",
  "recommended_action": "Assign to senior sales representative and schedule discovery call.",
  "next_action": "Schedule discovery call",
  "customer_status": "prospect",
  "routing_category": "hot",
  "actions": [
    {
      "type": "sales_assignment",
      "priority": "high"
    },
    {
      "type": "follow_up_call",
      "priority": "high"
    }
  ]
}
```

FastAPI responsibility:

```text
Update crm_leads.recommended_action.
Update crm_leads.next_action.
Update crm_leads.customer_status.
Update crm_leads.last_contact_at if applicable.
Insert crm_interactions row with interaction_type = routing_decision.
Update workflow_executions and agent_runs.
```

## 8.5 A5/A6 — Communication workflow

Current role:

```text
Generate personalized email.
Optionally send email via Gmail.
Store communication log.
Update lead status.
```

Current issue:

```text
The workflow writes to lead_communications and may send email automatically.
```

Recommended MVP behavior:

```text
Generate communication draft, but do not auto-send email without human validation.
```

Recommended FastAPI endpoint:

```text
POST /api/n8n/crm/communication-result
```

Payload example:

```json
{
  "lead_id": "lead_001",
  "email_subject": "Automating your sales process",
  "email_body": "Hello...",
  "communication_status": "draft_generated",
  "email_priority": "hot"
}
```

FastAPI responsibility:

```text
Insert crm_interactions row with interaction_type = communication_draft.
Update crm_leads.next_action.
Do not mark the email as sent unless human approval exists.
Update workflow_executions and agent_runs.
```

## 9. Recommended FastAPI callback endpoints

The following endpoints should be added later:

```text
POST /api/n8n/crm/collect-result
POST /api/n8n/crm/analysis-result
POST /api/n8n/crm/scoring-result
POST /api/n8n/crm/routing-result
POST /api/n8n/crm/communication-result
```

Optional generic endpoint:

```text
POST /api/n8n/workflow-event
```

This generic endpoint can record workflow execution status into:

```text
workflow_executions
agent_runs
```

## 10. Recommended database updates by callback

### collect-result

Updates:

```text
crm_leads
crm_interactions
workflow_executions
agent_runs
```

### analysis-result

Updates:

```text
crm_leads.sentiment
crm_leads.intention
crm_leads.urgency
crm_leads.ai_summary
crm_interactions
workflow_executions
agent_runs
```

### scoring-result

Updates:

```text
crm_leads.lead_score
crm_leads.status
crm_leads.priority
crm_interactions
workflow_executions
agent_runs
```

### routing-result

Updates:

```text
crm_leads.recommended_action
crm_leads.next_action
crm_leads.customer_status
crm_interactions
workflow_executions
agent_runs
```

### communication-result

Updates:

```text
crm_interactions
crm_leads.next_action
workflow_executions
agent_runs
```

## 11. Recommended n8n changes later

The n8n workflows should gradually replace direct PostgreSQL nodes with HTTP Request nodes that call FastAPI.

Example replacement:

Before:

```text
n8n Postgres node → INSERT INTO lead_analysis
```

After:

```text
n8n HTTP Request node → POST /api/n8n/crm/analysis-result
```

Before:

```text
n8n Postgres node → INSERT INTO lead_scores
```

After:

```text
n8n HTTP Request node → POST /api/n8n/crm/scoring-result
```

Before:

```text
n8n Postgres node → INSERT INTO lead_actions
```

After:

```text
n8n HTTP Request node → POST /api/n8n/crm/routing-result
```

## 12. Security rules

n8n should not expose secrets in exported workflow JSON files.

API keys should be stored in:

```text
n8n credentials
environment variables
backend .env
```

Do not store secrets in:

```text
workflow JSON exports
frontend code
database plain text columns
public documentation
```

FastAPI callback endpoints should later use a shared secret header:

```text
X-N8N-SIGNATURE
```

or a simpler MVP header:

```text
X-N8N-SECRET
```

For the MVP, this can be added later before final demo.

## 13. Human validation rule

For CRM communication, the recommended MVP rule is:

```text
Generate email draft first.
Do not auto-send email without human validation.
```

This is safer for the demo and easier to defend.

Final flow:

```text
n8n generates email draft
→ FastAPI saves communication draft as crm_interaction
→ FlowPilot AI displays recommended communication
→ user validates or sends later
```

## 14. Odoo integration note

Odoo should not be connected in this step.

Later, Odoo can be integrated after the CRM n8n alignment is stable.

Possible Odoo CRM sync later:

```text
crm_leads qualified/hot lead
→ FastAPI or n8n creates opportunity in Odoo
→ Odoo opportunity ID stored in crm_leads or crm_interactions
```

This should be a future step, not part of Step 59.

## 15. Implementation order after this plan

Recommended next implementation steps:

```text
Step 60 — Add FastAPI CRM n8n callback endpoint skeletons
Step 61 — Adapt A2/A3/A4 CRM workflows to call FastAPI callbacks
Step 62 — Test CRM end-to-end n8n analysis/scoring/routing
Step 63 — Add communication draft workflow safely
Step 64 — Odoo CRM sync planning
```

Alternative if time is limited:

```text
Step 60 — Add only analysis/scoring/routing callbacks
Step 61 — Adapt only A2, A3, A4
Step 62 — Demo CRM lead update from n8n to FlowPilot UI
```

## 16. What is intentionally not implemented yet

This step does not implement:

```text
No backend callback endpoints
No n8n workflow modification
No Odoo sync
No real email sending approval flow
No authentication
No RBAC enforcement
No database migrations
No frontend changes
```

## 17. Final recommendation

The final recommended architecture for CRM is:

```text
crm_leads = current business state of the lead/client
crm_interactions = historical timeline of CRM interactions
workflow_executions = workflow-level traceability
agent_runs = AI agent-level traceability
```

n8n should become the automation engine, not the database owner.

FastAPI should remain the source-of-truth controller for PostgreSQL.

This keeps the project clean, explainable, and suitable for a final-year project defense.