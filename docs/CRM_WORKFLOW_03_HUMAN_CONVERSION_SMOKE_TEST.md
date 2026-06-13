# FlowPilot AI CRM Workflow 03 Human Conversion Smoke Test

Date: 2026-05-01  
Status: Step 62.1 completed

---

## 1. Purpose

This document validates the integration and smoke test of the third CRM n8n workflow with FlowPilot AI:

```text
FP_CRM_03_Human_Conversion_Customer_Welcome
```

The goal of this workflow is to complete the core CRM lifecycle by converting a qualified prospect into a customer after explicit human validation.

Validated business flow:

```text
Qualified prospect
→ Human validation
→ Customer conversion
→ Customer status update
→ Welcome communication draft
→ CRM interaction history
→ Workflow monitoring trace
→ AI agent trace
```

This workflow confirms that FlowPilot AI supports the CRM lifecycle:

```text
Lead → Prospect → Customer
```

---

## 2. Architecture Validated

The validated architecture is:

```text
n8n Workflow 03
→ FastAPI CRM callback endpoints
→ PostgreSQL
→ React CRM / Workflow Monitoring / AI Agent Center
```

PostgreSQL source-of-truth tables involved:

```text
crm_leads
crm_interactions
workflow_executions
agent_runs
```

FastAPI callbacks involved:

```text
POST /api/n8n/crm/routing-result
POST /api/n8n/crm/communication-result
```

The workflow does not write directly to PostgreSQL.  
n8n executes the business automation and sends results back to FastAPI callbacks.  
FastAPI remains the controller responsible for updating PostgreSQL.

---

## 3. Workflow Validated

Workflow name:

```text
FP_CRM_03_Human_Conversion_Customer_Welcome
```

Webhook path:

```text
flowpilot-crm-customer-converted
```

Purpose:

```text
Convert a prospect into a customer only after human validation.
Generate a welcome communication draft.
Persist customer conversion history.
Persist workflow and AI agent traces.
```

Important business rule:

```text
The workflow must not convert the lead automatically without human validation.
```

Required field:

```text
human_validated = true
```

Email safety rule:

```text
No email is sent automatically.
The welcome email is saved as a draft for human validation.
```

---

## 4. Validated Behavior

The workflow was tested end-to-end and confirmed to perform the following actions:

```text
Webhook receives human conversion payload.
Request is authorized using X-FlowPilot-Secret.
Request is validated.
human_validated is required.
OpenRouter or fallback logic generates welcome message.
FastAPI routing-result callback is called successfully.
FastAPI communication-result callback is called successfully.
crm_leads is updated.
crm_interactions receives conversion and welcome draft history.
workflow_executions receives Workflow 03 traces.
agent_runs receives the welcome communication agent trace.
No email is sent automatically.
```

---

## 5. FastAPI Callbacks Validated

The following callbacks returned success:

```text
POST /api/n8n/crm/routing-result          200 OK
POST /api/n8n/crm/communication-result    200 OK
```

The routing callback updates the CRM lead status and stores the customer conversion event.  
The communication callback stores the welcome communication draft and agent/workflow traces.

---

## 6. Test Lead Used

The test used the same lead previously created by Workflow 01 and enriched by Workflow 02:

```text
lead_n8n_trace_test_001
```

Example payload used:

```json
{
  "lead_id": "lead_n8n_trace_test_001",
  "full_name": "Nour Ben Salem",
  "email": "nour.bensalem@example.com",
  "phone": "+21622333444",
  "company_name": "Smart Business Tunisia",
  "customer_status": "prospect",
  "new_customer_status": "customer",
  "conversion_status": "converted",
  "human_validated": true,
  "validated_by": "user_030",
  "requested_by": "user_030",
  "product_service": "AI CRM Automation",
  "estimated_value": 18000,
  "priority": "high",
  "source": "crm_ui",
  "customer_category": "new",
  "conversion_note": "Prospect validated by CRM manager after successful AI scoring and communication draft.",
  "next_action": "Start onboarding / customer follow-up",
  "send_welcome_email": false
}
```

---

## 7. Manual Test Procedure

### Step 1: Start PostgreSQL

```powershell
cd D:\SMA_PFE
docker compose up -d postgres
```

---

### Step 2: Start FastAPI Backend

```powershell
cd D:\SMA_PFE\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Expected backend URL:

```text
http://127.0.0.1:8000
```

---

### Step 3: Start n8n

Open n8n in the browser:

```text
http://localhost:5678
```

Open the workflow:

```text
FP_CRM_03_Human_Conversion_Customer_Welcome
```

Keep the workflow inactive while testing with the test webhook.

Webhook test URL:

```text
http://localhost:5678/webhook-test/flowpilot-crm-customer-converted
```

---

### Step 4: Send the Human Conversion Request

Use PowerShell:

```powershell
$body = @{
  lead_id = "lead_n8n_trace_test_001"
  full_name = "Nour Ben Salem"
  email = "nour.bensalem@example.com"
  phone = "+21622333444"
  company_name = "Smart Business Tunisia"
  customer_status = "prospect"
  new_customer_status = "customer"
  conversion_status = "converted"
  human_validated = $true
  validated_by = "user_030"
  requested_by = "user_030"
  product_service = "AI CRM Automation"
  estimated_value = 18000
  priority = "high"
  source = "crm_ui"
  customer_category = "new"
  conversion_note = "Prospect validated by CRM manager after successful AI scoring and communication draft."
  next_action = "Start onboarding / customer follow-up"
  send_welcome_email = $false
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Uri "http://localhost:5678/webhook-test/flowpilot-crm-customer-converted" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{ "X-FlowPilot-Secret" = "flowpilot-test-secret" } `
  -Body $body
```

---

## 8. Expected n8n Result

Expected response:

```json
{
  "ok": true,
  "lead_id": "lead_n8n_trace_test_001",
  "message": "Customer conversion and welcome flow completed"
}
```

Expected successful nodes:

```text
FastAPI Trigger - Customer Converted by Human
Validate Human Conversion
Valid Human Conversion?
OpenRouter - Generate Welcome Email
Prepare Welcome + Customer Callback
Callback Routing Customer Status
Callback Welcome Communication
Respond Customer Welcome Done
```

---

## 9. Expected FastAPI Logs

The FastAPI terminal should show successful callback requests:

```text
POST /api/n8n/crm/routing-result HTTP/1.1" 200 OK
POST /api/n8n/crm/communication-result HTTP/1.1" 200 OK
```

If these callbacks return `200 OK`, it means n8n successfully sent the conversion and welcome communication results to FastAPI.

---

## 10. SQL Verification

Open PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

---

### 10.1 Verify Lead Conversion

```sql
SELECT id, full_name, email, customer_status, customer_category, next_action, updated_at
FROM crm_leads
WHERE id = 'lead_n8n_trace_test_001';
```

Expected:

```text
customer_status = customer
customer_category = new
next_action = Start onboarding / customer follow-up
```

This confirms that the lead has been converted into a customer.

---

### 10.2 Verify CRM Interactions

```sql
SELECT lead_id, interaction_type, channel, summary, created_at
FROM crm_interactions
WHERE lead_id = 'lead_n8n_trace_test_001'
ORDER BY created_at DESC
LIMIT 10;
```

Expected recent interaction history:

```text
routing_decision       Customer converted by human validation. Start onboarding.
communication_draft    Welcome communication draft / CRM communication draft.
```

Interpretation:

```text
routing_decision
```

represents the customer conversion event.

```text
communication_draft
```

represents the welcome email draft generated after conversion.

---

### 10.3 Verify Workflow Executions

```sql
SELECT id, workflow_name, process, status, related_object_id, created_at
FROM workflow_executions
WHERE related_object_id = 'lead_n8n_trace_test_001'
ORDER BY created_at DESC
LIMIT 10;
```

Expected workflow traces:

```text
FP CRM 03 - Human Conversion to Customer + Welcome
FP CRM 03 - Welcome Communication Step
```

Expected status:

```text
success
```

This confirms that Workflow Monitoring can trace the conversion process.

---

### 10.4 Verify Agent Runs

```sql
SELECT id, agent_id, agent_name, process, status, workflow_execution_id, created_at
FROM agent_runs
ORDER BY created_at DESC
LIMIT 10;
```

Expected agent:

```text
crm_welcome_email_agent
CRM Welcome Email Agent
```

Expected status:

```text
success
```

This confirms that the AI Agent Center can trace the welcome communication agent execution.

---

### 10.5 Exit PostgreSQL

```sql
\q
```

---

## 11. Frontend Verification

Open:

```text
http://localhost:5173/crm-lead-details
```

Expected result:

```text
Interaction History displays the conversion event.
Interaction History displays the welcome communication draft.
The lead is now classified as a customer.
```

Also verify:

```text
http://localhost:5173/workflow-monitoring
http://localhost:5173/ai-agents
```

Expected:

```text
Workflow Monitoring shows Workflow 03 traces.
AI Agent Center shows the welcome email agent run.
```

---

## 12. Issues Fixed During Testing

### Issue 1: Callback Welcome Communication JSON body invalid

Initial error:

```text
The value in the "JSON Body" field is not valid JSON.
"undefined" is not valid JSON.
```

Root cause:

```text
After the routing callback, $json became the FastAPI response.
Therefore, $json.communication_payload was undefined.
```

Fix:

```javascript
{{ JSON.stringify($('🎁 Prepare Welcome + Customer Callback').first().json.communication_payload) }}
```

---

### Issue 2: Extra equals sign in n8n expression

Initial error:

```text
Unexpected token '=', "={"lead_id"... is not valid JSON.
```

Root cause:

```text
The JSON Body field already used expression mode.
The expression incorrectly started with ={{ ... }}.
```

Fix for the communication callback:

```javascript
{{ JSON.stringify($('🎁 Prepare Welcome + Customer Callback').first().json.communication_payload) }}
```

Fix for the routing callback:

```javascript
{{ JSON.stringify($('🎁 Prepare Welcome + Customer Callback').first().json.routing_payload) }}
```

---

## 13. Safety Rules Validated

The workflow respects the following MVP safety rules:

```text
Human validation is required.
human_validated must be true.
No email is sent automatically.
Welcome email is saved as a draft.
FastAPI remains the source-of-truth controller.
n8n does not write directly to PostgreSQL.
```

This behavior is important because FlowPilot AI is designed as a supervised business automation system, not a fully autonomous system that performs sensitive business actions without human control.

---

## 14. What Is Now Real

The CRM process now covers:

```text
Lead collection
AI analysis
Lead scoring
Lead routing
Communication draft generation
Human conversion
Customer status update
Welcome communication draft
CRM interaction history
Workflow monitoring
AI agent traceability
```

This validates the CRM lifecycle:

```text
Lead → Prospect → Customer
```

---

## 15. What Remains for Later

The following items are not implemented yet:

```text
React/FastAPI trigger button for Workflow 03
Email approval/send UI
Workflow 04 inactive customer follow-up
Workflow 05 loyal/VIP update
Workflow 06 customer activity analysis
Odoo CRM synchronization
Real authentication
Real RBAC enforcement
Production monitoring
Automated tests
```

Workflow 04 and Workflow 05 must remain disabled until these backend endpoints exist:

```text
GET /api/n8n/crm/inactive-customers
GET /api/n8n/crm/vip-candidates
```

---

## 16. Completion Checklist

Step 62.1 is complete if:

```text
[OK] Workflow 03 imports successfully.
[OK] Test webhook receives payload.
[OK] human_validated = true is required.
[OK] send_welcome_email = false prevents automatic sending.
[OK] routing-result returns 200 OK.
[OK] communication-result returns 200 OK.
[OK] crm_leads.customer_status = customer.
[OK] crm_interactions contains conversion/welcome history.
[OK] workflow_executions contains Workflow 03 traces.
[OK] agent_runs contains CRM welcome email agent trace.
[OK] React CRM displays the updated customer state.
```

---

## 17. Completion Status

Step 62.1 completed:

```text
FP_CRM_03 Human Conversion to Customer workflow imported and tested.
```

---

## 18. Recommended Next Step

Recommended next step:

```text
Step 62.3 — Small CRM Lead Details Wording Improvement
```

Purpose:

```text
Improve how Workflow 03 events appear in the CRM Lead Details interaction history.
```

Recommended UI improvement:

```text
routing_decision + summary contains "Customer converted"
→ display as Customer Converted

communication_draft + summary contains welcome/customer
→ display as Welcome Communication Draft
```

This is not a backend requirement, but it improves clarity for the final demo and academic defense.

---

## 19. Conclusion

Workflow 03 is successfully integrated and tested.

It confirms that FlowPilot AI now supports a meaningful CRM business lifecycle:

```text
Lead → Prospect → Customer
```

The workflow respects the human-in-the-loop principle by requiring explicit human validation before conversion and by generating a welcome communication draft without automatically sending email.

The current CRM automation system is now suitable for demonstrating:

```text
AI-supported CRM qualification
Business process automation with n8n
FastAPI-controlled persistence
PostgreSQL CRM traceability
Human-supervised customer conversion
React-based process supervision
```