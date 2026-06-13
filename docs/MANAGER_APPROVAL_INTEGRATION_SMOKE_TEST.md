# FlowPilot AI Manager Approval Integration Smoke Test

Date: 2026-04-27  
Status: Step 31 completed

## 1. Step 31 completion summary

Step 31 is complete.

The Manager Approval page integration slice was validated successfully.

Confirmed outcomes:

- Manager Approval page is connected to FastAPI.
- Pending approval requests are loaded from the backend.
- Approve action sends a POST request to the backend.
- Reject action sends a POST request to the backend.
- Success messages appear in the frontend after approve/reject actions.
- Page remains stable with no blank screen.
- No console errors appeared while backend was running.
- Backend-unavailable fallback was tested successfully.
- Page did not crash when backend was stopped.
- Mock fallback data appeared when backend was unavailable.
- Decision error message appeared when backend was unavailable.

## 2. Integration flow tested

The following frontend-backend flow was tested:

```text
React Manager Approval Page
→ frontend leave service
→ FastAPI backend
→ mock backend approval response
```

Success path:

```text
Manager Approval page
→ GET /api/leave-requests/pending
→ pending requests displayed in UI
→ approve/reject button clicked
→ POST approve/reject endpoint
→ success message shown in UI
```

Fallback path:

```text
Backend stopped
→ Manager Approval page refresh
→ frontend keeps page usable
→ mock fallback data appears
→ backend unavailable message appears
```

## 3. Backend endpoints used

The following backend endpoints were used:

```text
GET  http://127.0.0.1:8000/api/leave-requests/pending
POST http://127.0.0.1:8000/api/leave-requests/{request_id}/approve
POST http://127.0.0.1:8000/api/leave-requests/{request_id}/reject
```

Example concrete endpoints tested:

```text
GET  http://127.0.0.1:8000/api/leave-requests/pending
POST http://127.0.0.1:8000/api/leave-requests/lr_1001/approve
POST http://127.0.0.1:8000/api/leave-requests/lr_1001/reject
```

## 4. Frontend page tested

Frontend route tested:

```text
http://localhost:5173/manager-approvals
```

## 5. Files likely involved in the integration

Frontend files likely involved:

```text
frontend/src/pages/ManagerApprovalPage.tsx
frontend/src/services/leaveService.ts
frontend/src/services/apiClient.ts
frontend/src/services/index.ts
frontend/src/data/managerApprovalData.ts
```

Backend files likely involved:

```text
backend/app/api/leave_requests.py
backend/app/services/leave_service.py
backend/app/schemas/leave_requests.py
backend/app/main.py
```

Note:

This list is used for traceability. It is not a complete dependency map.

## 6. Manual success-path test procedure

### Step 1: Start backend

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

### Step 2: Start frontend

From the frontend folder:

```powershell
cd D:\SMA_PFE\frontend
npm.cmd run dev
```

Expected frontend URL:

```text
http://localhost:5173
```

### Step 3: Open Manager Approval page

Open:

```text
http://localhost:5173/manager-approvals
```

Confirmed behavior:

- Page opened normally.
- Sidebar appeared.
- Top header appeared.
- Manager Approvals sidebar item was active.
- Pending requests section appeared.
- Selected request summary appeared.
- AI recommendation section appeared.
- Approve Request and Reject Request buttons appeared.
- No blank page appeared.

## 7. Network tab verification for pending requests

Browser DevTools Network tab was used to verify the backend request.

Confirmed request:

```text
GET http://127.0.0.1:8000/api/leave-requests/pending
```

Confirmed response:

```text
Status Code: 200 OK
```

Response contained pending leave request data, including fields such as:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "lr_1001",
        "employee_id": "user_010",
        "employee_name": "Sarah N.",
        "department": "Operations",
        "leave_type": "Annual Leave",
        "start_date": "2026-05-03",
        "end_date": "2026-05-05",
        "reason": "Family event",
        "status": "pending",
        "ai_recommendation": "approve",
        "risk_level": "low",
        "conflict_detected": false
      }
    ]
  }
}
```

This confirms that the Manager Approval page loads pending requests from FastAPI.

## 8. Network tab verification for approve action

Approve action was tested from the Manager Approval interface.

Confirmed request:

```text
POST http://127.0.0.1:8000/api/leave-requests/lr_1001/approve
```

Expected request body:

```json
{
  "comment": "Approved"
}
```

Confirmed behavior:

- Request was sent from the frontend.
- Backend returned HTTP 200.
- UI showed a success message.
- Page did not crash.

Expected response shape:

```json
{
  "success": true,
  "data": {
    "id": "lr_1001",
    "status": "approved",
    "manager_comment": "Approved",
    "updated_at": "ISO datetime"
  },
  "error": null
}
```

## 9. Network tab verification for reject action

Reject action was tested from the Manager Approval interface.

Confirmed request:

```text
POST http://127.0.0.1:8000/api/leave-requests/lr_1001/reject
```

Expected request body:

```json
{
  "comment": "Insufficient team coverage"
}
```

Confirmed behavior:

- Request was sent from the frontend.
- Backend returned HTTP 200.
- UI showed a success message.
- Page did not crash.

Expected response shape:

```json
{
  "success": true,
  "data": {
    "id": "lr_1001",
    "status": "rejected",
    "manager_comment": "Insufficient team coverage",
    "updated_at": "ISO datetime"
  },
  "error": null
}
```

## 10. Backend unavailable fallback test

The backend was stopped with:

```text
Ctrl + C
```

Then the Manager Approval page was refreshed:

```text
http://localhost:5173/manager-approvals
```

Confirmed fallback behavior:

- Page still opened.
- No blank page appeared.
- Mock approval data remained visible.
- Backend unavailable message appeared.
- Sidebar and top header remained usable.

Approve/reject behavior while backend was unavailable:

- Page did not crash.
- Decision error message appeared.
- User was informed that the decision could not be submitted.

## 11. Confirmed UI behavior

Confirmed UI behavior:

- Manager Approval page renders correctly.
- Pending requests are displayed.
- Selected request summary remains visible.
- AI recommendation panel remains visible.
- Approve Request button remains usable.
- Reject Request button remains usable.
- Success feedback appears after successful backend decision.
- Error feedback appears if backend is unavailable.
- No layout redesign was introduced.
- Existing visual style remained stable.

## 12. What remains mock-only

The following parts remain mock-only:

- Pending approval records are returned from mock backend data.
- Approve/reject decisions are not persisted.
- After refresh, approval state may reset.
- Leave request history is not persisted.
- Employee balance is not connected to a real database.
- AI recommendation is mock/static.
- Conflict detection is mock/static.
- Policy status is mock/static.

Other modules still mostly mock-only:

- CRM Leads
- CRM Lead Details
- AI Agent Center
- Workflow Monitoring
- Admin Users
- Roles & Permissions

## 13. What is intentionally not implemented yet

The following features were intentionally not implemented in this step:

- No PostgreSQL persistence.
- No n8n workflow calls.
- No real authentication.
- No protected routes.
- No real RBAC enforcement.
- No Odoo integration.
- No deployment setup.
- No Docker setup.
- No CRM backend integration.
- No workflow monitoring backend integration.

## 14. Recommended next step

Recommended next step:

```text
Step 33 — Add backend mock endpoints for CRM Leads before connecting the CRM frontend pages.
```

Suggested Step 33 backend endpoints:

```text
GET  /api/crm/leads
GET  /api/crm/leads/{lead_id}
POST /api/crm/leads
```

Step 33 should remain backend-only first.

Do not connect CRM frontend pages until the backend CRM endpoints are created and tested in Swagger.

After Step 33, continue with:

```text
Step 34 — Connect CRM Leads Page and CRM Lead Details Page to FastAPI
```