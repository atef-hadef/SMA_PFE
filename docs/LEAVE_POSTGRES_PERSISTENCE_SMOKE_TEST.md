# FlowPilot AI Leave PostgreSQL Persistence Smoke Test

Date: 2026-04-28  
Status: Step 51 completed

## 1. Step 51 completion summary

Step 51 is complete.

The Leave Request and Manager Approval backend logic has been replaced with PostgreSQL-backed persistence.

Confirmed outcomes:

- `POST /api/leave-requests` now creates a real row in the `leave_requests` table.
- `GET /api/leave-requests/pending` now reads pending leave requests from PostgreSQL.
- `POST /api/leave-requests/{request_id}/approve` now updates leave request status in PostgreSQL.
- `POST /api/leave-requests/{request_id}/reject` now updates leave request status in PostgreSQL.
- The Leave Request frontend page still works.
- The Manager Approval frontend page still works.
- Existing API response shapes remain compatible with the frontend.
- No frontend changes were required.
- n8n is not connected yet.
- Real authentication and RBAC enforcement are not implemented yet.

## 2. Integration flow tested

### Leave request submission flow

```text
React Leave Request Page
→ POST /api/leave-requests
→ FastAPI leave request endpoint
→ SQLAlchemy service logic
→ PostgreSQL leave_requests table
```

### Manager approval loading flow

```text
React Manager Approval Page
→ GET /api/leave-requests/pending
→ FastAPI manager approval endpoint
→ SQLAlchemy service logic
→ PostgreSQL leave_requests + users tables
```

### Approval decision flow

```text
Manager clicks Approve
→ POST /api/leave-requests/{request_id}/approve
→ FastAPI updates leave_requests.status
→ PostgreSQL stores reviewed_by, reviewed_at, decision_comment
```

### Rejection decision flow

```text
Manager clicks Reject
→ POST /api/leave-requests/{request_id}/reject
→ FastAPI updates leave_requests.status
→ PostgreSQL stores reviewed_by, reviewed_at, decision_comment
```

## 3. Backend endpoints tested

The following endpoints were tested:

```text
POST /api/leave-requests
GET  /api/leave-requests/pending
POST /api/leave-requests/{request_id}/approve
POST /api/leave-requests/{request_id}/reject
```

Example local URLs:

```text
POST http://127.0.0.1:8000/api/leave-requests
GET  http://127.0.0.1:8000/api/leave-requests/pending
POST http://127.0.0.1:8000/api/leave-requests/leave_001/approve
POST http://127.0.0.1:8000/api/leave-requests/{new_request_id}/reject
```

## 4. Frontend pages tested

Frontend routes tested:

```text
http://localhost:5173/leave-requests
http://localhost:5173/manager-approvals
```

## 5. Database tables used

The following PostgreSQL tables are involved:

```text
users
leave_requests
```

Supporting tables already exist but are not directly required for this persistence test:

```text
roles
role_permissions
```

## 6. Default users used before real authentication

Real authentication is not implemented yet, so temporary default users are used by the backend service logic.

### Default employee

```text
user_010
```

Used when creating a leave request from the frontend form.

Represents:

```text
Sarah N.
Operations Specialist
Operations department
```

### Default manager/reviewer

```text
user_020
```

Used when approving or rejecting leave requests.

Represents:

```text
Manager User
Operations Manager
Operations department
```

These defaults are temporary and will be replaced later by real authenticated user context.

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

## 8. Test A — Submit leave request from frontend

Open:

```text
http://localhost:5173/leave-requests
```

Submit a leave request using the form.

Example form values:

```text
Leave Type: Annual Leave
Start Date: 2026-05-10
End Date: 2026-05-12
Reason: Family event
```

Expected frontend behavior:

```text
Success message appears.
Page does not crash.
No blank screen appears.
```

Expected network behavior:

```text
POST /api/leave-requests
Status Code: 200
```

Expected backend behavior:

```text
A new row is inserted into leave_requests.
The status is pending.
The user_id is user_010.
```

## 9. PostgreSQL verification after submission

Open PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Run:

```sql
SELECT id, user_id, leave_type, start_date, end_date, status, created_at
FROM leave_requests
ORDER BY created_at DESC;
```

Expected result:

```text
A new leave request appears.
user_id = user_010
status = pending
```

Exit PostgreSQL:

```sql
\q
```

## 10. Test B — Load pending approvals from frontend

Open:

```text
http://localhost:5173/manager-approvals
```

Expected frontend behavior:

```text
Manager Approval page opens normally.
Pending leave requests appear.
Seeded pending request appears if still pending.
Newly submitted leave request appears if still pending.
No blank screen appears.
```

Expected network behavior:

```text
GET /api/leave-requests/pending
Status Code: 200
```

Expected backend behavior:

```text
FastAPI reads pending records from the leave_requests table.
User information is fetched from the users table.
```

The pending approval items should include business-friendly fields such as:

```text
employee_name
department
leave_type
start_date
end_date
reason
status
created_at
```

## 11. Test C — Approve leave request

From the Manager Approval page, select a pending leave request and click:

```text
Approve Request
```

Expected frontend behavior:

```text
Success message appears.
Page does not crash.
```

Expected network behavior:

```text
POST /api/leave-requests/{request_id}/approve
Status Code: 200
```

Expected backend behavior:

```text
leave_requests.status becomes approved.
reviewed_by is set to user_020.
reviewed_at is set.
decision_comment is saved.
updated_at is updated.
```

Verify in PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Run:

```sql
SELECT id, status, reviewed_by, reviewed_at, decision_comment, updated_at
FROM leave_requests
WHERE status = 'approved'
ORDER BY updated_at DESC;
```

Expected result:

```text
The approved request appears.
status = approved
reviewed_by = user_020
reviewed_at is not null
decision_comment is saved
```

Exit:

```sql
\q
```

## 12. Test D — Reject leave request

Create another leave request from:

```text
http://localhost:5173/leave-requests
```

Then open:

```text
http://localhost:5173/manager-approvals
```

Click:

```text
Reject Request
```

Expected frontend behavior:

```text
Success message appears.
Page does not crash.
```

Expected network behavior:

```text
POST /api/leave-requests/{request_id}/reject
Status Code: 200
```

Expected backend behavior:

```text
leave_requests.status becomes rejected.
reviewed_by is set to user_020.
reviewed_at is set.
decision_comment is saved.
updated_at is updated.
```

Verify in PostgreSQL:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Run:

```sql
SELECT id, status, reviewed_by, reviewed_at, decision_comment, updated_at
FROM leave_requests
WHERE status = 'rejected'
ORDER BY updated_at DESC;
```

Expected result:

```text
The rejected request appears.
status = rejected
reviewed_by = user_020
reviewed_at is not null
decision_comment is saved
```

Exit:

```sql
\q
```

## 13. Error handling checked

The following error behavior should remain supported:

```text
If a leave request ID does not exist, backend returns a clean 404 response.
If PostgreSQL is unavailable, backend returns an error instead of silently using fake persistence.
Frontend page should not crash.
```

Example backend test:

```text
POST /api/leave-requests/unknown_request/approve
```

Expected:

```text
404 Not Found
Clear error message
```

## 14. Fields still computed or sample-based

The following fields are still not real business logic yet:

```text
ai_recommendation
risk_level
conflict_detected
```

They may still be computed or returned as sample fields by the backend.

Current behavior is acceptable for this step because the goal is leave request persistence, not full AI policy analysis.

Later, these fields can be generated by:

```text
FastAPI business rules
n8n workflow results
Odoo leave balance checks
AI/LLM analysis
```

## 15. What is now real

The following parts are now backed by PostgreSQL:

```text
Leave request creation
Pending approval retrieval
Approve decision
Reject decision
Reviewed by manager field
Review timestamp
Decision comment
Leave request status lifecycle
```

This means the leave process is now persistent.

## 16. What remains mock-only or temporary

The following parts remain mock-only or temporary:

```text
AI recommendation
Risk level
Conflict detection
Leave balance validation
Odoo employee/leave synchronization
n8n leave workflow execution
Authentication
Real logged-in employee identity
Real manager identity
RBAC enforcement
Dashboard summary persistence
CRM persistence
Workflow monitoring persistence
AI Agent Center persistence
Admin/Roles persistence behavior
```

## 17. What is intentionally not implemented yet

The following features were intentionally not implemented in Step 51:

```text
No frontend redesign
No frontend route changes
No n8n integration
No Odoo integration
No real authentication
No real RBAC enforcement
No dashboard persistence
No CRM persistence
No workflow execution persistence
No agent run persistence
No Alembic migrations
```

## 18. Completion checklist

Step 51 is considered complete if:

```text
POST /api/leave-requests writes to PostgreSQL.
A new leave request appears in leave_requests.
GET /api/leave-requests/pending reads from PostgreSQL.
Manager Approval page displays database-backed pending requests.
Approve action updates status to approved in PostgreSQL.
Reject action updates status to rejected in PostgreSQL.
reviewed_by is saved.
reviewed_at is saved.
decision_comment is saved.
Leave Request frontend page still works.
Manager Approval frontend page still works.
Other mock modules still work.
```

## 19. Recommended next step

Recommended next step:

```text
Step 53 — Add CRM Lead PostgreSQL Model, Table, and Seed Data
```

Purpose:

```text
Prepare PostgreSQL persistence for CRM Leads and CRM Lead Details.
```

Suggested future tables:

```text
crm_leads
```

Then continue with:

```text
Step 54 — Replace CRM Mock Services with PostgreSQL
```

After that, CRM Leads and CRM Lead Details will become database-backed instead of mock-backed.