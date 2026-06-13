# FlowPilot AI CRM PostgreSQL Persistence Smoke Test

Date: 2026-04-28  
Status: Step 54 completed

## 1. Step 54 completion summary

Step 54 is complete.

The CRM backend logic has been replaced with PostgreSQL-backed persistence.

Confirmed outcomes:

- `GET /api/crm/leads` now reads CRM leads from the `crm_leads` table.
- `GET /api/crm/leads/{lead_id}` now reads lead details from PostgreSQL.
- `POST /api/crm/leads` now inserts a new CRM lead into PostgreSQL.
- The CRM Leads frontend page still works.
- The CRM Lead Details frontend page still works.
- Existing API response shapes remain compatible with the frontend.
- No frontend changes were required.
- n8n is not connected yet.
- Odoo is not connected yet.
- Real authentication and RBAC enforcement are not implemented yet.

## 2. Integration flow tested

### CRM lead list flow

```text
React CRM Leads Page
→ GET /api/crm/leads
→ FastAPI CRM endpoint
→ SQLAlchemy service logic
→ PostgreSQL crm_leads table
```

### CRM lead details flow

```text
React CRM Lead Details Page
→ GET /api/crm/leads/lead_001
→ FastAPI CRM endpoint
→ SQLAlchemy service logic
→ PostgreSQL crm_leads table
```

### CRM lead creation flow

```text
POST /api/crm/leads
→ FastAPI CRM endpoint
→ SQLAlchemy service logic
→ PostgreSQL crm_leads table
```

## 3. Backend endpoints tested

The following endpoints were tested:

```text
GET  /api/crm/leads
GET  /api/crm/leads/{lead_id}
POST /api/crm/leads
```

Example local URLs:

```text
GET  http://127.0.0.1:8000/api/crm/leads
GET  http://127.0.0.1:8000/api/crm/leads/lead_001
POST http://127.0.0.1:8000/api/crm/leads
```

## 4. Frontend pages tested

Frontend routes tested:

```text
http://localhost:5173/crm-leads
http://localhost:5173/crm-lead-details
```

## 5. Database table used

The following PostgreSQL table is involved:

```text
crm_leads
```

The table stores:

```text
lead identity
company information
contact information
lead status
lead score
sentiment
urgency
intention
message
AI summary
recommended action
assigned user references
timestamps
```

## 6. Field mapping

The backend maps database columns to frontend-compatible fields.

```text
full_name     → name
company_name  → company
lead_score    → score
```

Example database fields:

```text
full_name = Northwind Logistics
company_name = Northwind Group
lead_score = 94
```

Example API response fields:

```text
name = Northwind Logistics
company = Northwind Group
score = 94
```

## 7. Manual test procedure

### Step 1: Start PostgreSQL

From the project root:

```powershell
cd D:\SMA_PFE
docker compose up -d postgres
```

Verify the container is running:

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

## 8. Test A — CRM Leads page

Open:

```text
http://localhost:5173/crm-leads
```

Expected frontend behavior:

```text
CRM Leads page opens normally.
CRM lead rows appear.
No blank screen appears.
No frontend crash occurs.
```

Expected visible leads:

```text
Northwind Logistics
Atlas Retail
Medina Services
```

Expected network behavior:

```text
GET /api/crm/leads
Status Code: 200
```

Expected backend behavior:

```text
FastAPI reads CRM leads from the crm_leads table.
```

## 9. PostgreSQL verification for CRM lead list

Open PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Run:

```sql
SELECT id, full_name, company_name, status, lead_score
FROM crm_leads;
```

Expected result:

```text
lead_001 | Northwind Logistics | Northwind Group      | hot  | 94
lead_002 | Atlas Retail        | Atlas Retail Group   | warm | 72
lead_003 | Medina Services     | Medina Services      | cold | 38
```

Exit PostgreSQL:

```sql
\q
```

## 10. Test B — CRM Lead Details page

Open:

```text
http://localhost:5173/crm-lead-details
```

Expected frontend behavior:

```text
CRM Lead Details page opens normally.
Lead profile appears.
Lead score appears.
Sentiment appears.
Urgency appears.
AI summary appears.
Recommended action appears.
No blank screen appears.
```

Expected network behavior:

```text
GET /api/crm/leads/lead_001
Status Code: 200
```

Expected visible data:

```text
Northwind Logistics
Lead Score: 94
Sentiment: positive
Urgency: high
Recommended action appears
```

Expected backend behavior:

```text
FastAPI reads lead_001 from the crm_leads table.
```

## 11. Test C — CRM lead creation

If the frontend does not yet provide a full Create Lead form, this test can be done through Swagger.

Open:

```text
http://127.0.0.1:8000/docs
```

Test:

```text
POST /api/crm/leads
```

Example request body:

```json
{
  "name": "New Business Lead",
  "company": "New Business Group",
  "email": "contact@newbusiness.com",
  "source": "web",
  "message": "We are interested in process automation."
}
```

Expected response:

```text
Status Code: 200 or 201
success: true
A new lead id is returned.
status = new
score = 0
```

Expected backend behavior:

```text
A new row is inserted into the crm_leads table.
```

## 12. PostgreSQL verification after lead creation

Open PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Run:

```sql
SELECT id, full_name, company_name, status, lead_score, created_at
FROM crm_leads
ORDER BY created_at DESC;
```

Expected result:

```text
The newly created CRM lead appears.
status = new
lead_score = 0
```

Exit:

```sql
\q
```

## 13. Error handling checked

The following error behavior should remain supported:

```text
If a CRM lead ID does not exist, backend returns a clean 404 response.
If PostgreSQL is unavailable, backend returns a controlled error.
Frontend fallback behavior should prevent blank pages.
```

Example backend test:

```text
GET /api/crm/leads/unknown_lead
```

Expected:

```text
404 Not Found
Clear error message
```

## 14. What is now real

The following CRM parts are now backed by PostgreSQL:

```text
CRM lead list
CRM lead details
CRM lead creation
Lead status field
Lead score field
Sentiment field
Urgency field
Intention field
AI summary field
Recommended action field
Assigned user reference
CRM lead timestamps
```

## 15. What remains mock-only or temporary

The following CRM parts remain mock-only or temporary:

```text
Real AI scoring logic
Real sentiment generation
Real urgency detection
Real intention classification
CRM analysis workflow
Email sending workflow
Lead enrichment workflow
Odoo CRM synchronization
n8n CRM workflow execution
Authentication
Real logged-in sales user identity
RBAC enforcement
```

## 16. What is intentionally not implemented yet

The following features were intentionally not implemented in Step 54:

```text
No frontend redesign
No frontend route changes
No n8n integration
No Odoo integration
No real authentication
No real RBAC enforcement
No CRM AI analysis endpoint integration
No CRM scoring endpoint integration
No email sending workflow
No Alembic migrations
```

## 17. Completion checklist

Step 54 is considered complete if:

```text
GET /api/crm/leads reads from PostgreSQL.
CRM Leads page displays PostgreSQL leads.
GET /api/crm/leads/lead_001 reads from PostgreSQL.
CRM Lead Details page displays PostgreSQL lead_001.
POST /api/crm/leads inserts into PostgreSQL.
New CRM lead appears in crm_leads.
Frontend CRM pages still work.
Leave persistence still works.
Database health endpoint still works.
Other mock modules still work.
```

## 18. Recommended next step

Recommended next step:

```text
Step 56 — Add Workflow Execution and Agent Run PostgreSQL Models, Tables, and Seed Data
```

Purpose:

```text
Prepare PostgreSQL persistence for Workflow Monitoring and AI Agent Center.
```

Suggested future tables:

```text
workflow_executions
agent_runs
```

Then continue with:

```text
Step 57 — Replace Workflow Monitoring and AI Agent Center Mock Services with PostgreSQL
```

After that, Workflow Monitoring and AI Agent Center will become database-backed instead of mock-backed.