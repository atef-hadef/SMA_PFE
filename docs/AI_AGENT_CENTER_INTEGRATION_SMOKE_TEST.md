# FlowPilot AI AI Agent Center Integration Smoke Test

Date: 2026-04-27  
Status: Step 40 completed

## 1. Step 40 completion summary

Step 40 is complete.

The AI Agent Center frontend integration slice was validated successfully.

Confirmed outcomes:

- AI Agent Center page is connected to FastAPI.
- Agent list is loaded from the backend.
- Selected agent detail is loaded from the backend.
- Manual Run Agent action sends a POST request to the backend.
- Success message appears after manual agent run.
- Backend API calls returned HTTP 200.
- Page remained stable with no blank screen.
- Console warnings observed were caused by browser/extension injected scripts and did not block the application.
- PostgreSQL, n8n, real authentication, and protected routes are still not connected.

## 2. Integration flow tested

The following frontend-backend AI Agent Center flows were tested:

```text
React AI Agent Center Page
→ frontend agent service
→ FastAPI backend
→ mock agent list response
```

```text
React AI Agent Center Page
→ frontend agent service
→ FastAPI backend
→ mock selected agent detail response
```

```text
React AI Agent Center Page
→ Run Agent button
→ frontend agent service
→ FastAPI backend
→ mock agent run queued response
```

Success path:

```text
AI Agent Center page
→ GET /api/agents
→ backend returns mock agents
→ agent list appears in frontend
```

```text
AI Agent Center page
→ GET /api/agents/agent_lead_scoring
→ backend returns selected agent details
→ selected agent panel appears in UI
```

```text
AI Agent Center page
→ Run Agent clicked
→ POST /api/agents/agent_lead_scoring/run
→ backend returns run queued response
→ success message appears in UI
```

## 3. Backend endpoints used

The following backend endpoints were used:

```text
GET  http://127.0.0.1:8000/api/agents
GET  http://127.0.0.1:8000/api/agents/agent_lead_scoring
POST http://127.0.0.1:8000/api/agents/agent_lead_scoring/run
```

## 4. Frontend page tested

Frontend route tested:

```text
http://localhost:5173/ai-agents
```

## 5. Files likely involved in the integration

Frontend files likely involved:

```text
frontend/src/pages/AIAgentCenterPage.tsx
frontend/src/services/agentService.ts
frontend/src/services/apiClient.ts
frontend/src/services/index.ts
frontend/src/data/aiAgentsData.ts
```

Backend files likely involved:

```text
backend/app/api/agents.py
backend/app/services/agent_service.py
backend/app/schemas/agents.py
backend/app/main.py
```

Note:

This list is used for traceability. It is not a complete dependency map.

## 6. Manual AI Agent Center page test procedure

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

### Step 3: Open AI Agent Center page

Open:

```text
http://localhost:5173/ai-agents
```

Confirmed behavior:

- AI Agent Center page opened normally.
- Sidebar appeared.
- Top header appeared.
- AI Agent Center sidebar item was accessible.
- Agent list appeared.
- Selected agent detail section appeared.
- Run Agent action was available.
- No blank page appeared.

## 7. Network tab verification for agent list

Browser DevTools Network tab was used to verify the backend request.

Confirmed request:

```text
GET http://127.0.0.1:8000/api/agents
```

Confirmed response:

```text
Status Code: 200 OK
```

Expected response shape:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "agent_leave_validation",
        "name": "Leave Validation Agent",
        "process": "Leave Management",
        "status": "active",
        "type": "rule_ai_hybrid",
        "success_rate": 94
      },
      {
        "id": "agent_lead_scoring",
        "name": "Lead Scoring Agent",
        "process": "CRM",
        "status": "active",
        "type": "ai_scoring",
        "success_rate": 89
      }
    ]
  },
  "error": null
}
```

This confirms that the AI Agent Center page loads agent records from FastAPI.

## 8. Network tab verification for selected agent details

Browser DevTools Network tab was used to verify the selected agent detail request.

Confirmed request:

```text
GET http://127.0.0.1:8000/api/agents/agent_lead_scoring
```

Confirmed response:

```text
Status Code: 200 OK
```

Expected response shape:

```json
{
  "success": true,
  "data": {
    "id": "agent_lead_scoring",
    "name": "Lead Scoring Agent",
    "process": "CRM",
    "status": "active",
    "type": "ai_scoring",
    "success_rate": 89,
    "description": "Scores CRM leads using sentiment, urgency, and business intent.",
    "input_description": "CRM lead profile, source, message, sentiment, urgency, and interaction history.",
    "output_description": "Lead score, priority level, suggested routing, and recommended action.",
    "tools": [
      "sentiment_analyzer",
      "urgency_detector",
      "lead_score_calculator"
    ],
    "related_workflows": [
      "CRM Lead Scoring Flow",
      "CRM Lead Routing Flow"
    ]
  },
  "error": null
}
```

This confirms that the selected agent detail is loaded from FastAPI.

## 9. Network tab verification for manual agent run

The Run Agent action was tested from the AI Agent Center interface.

Confirmed request:

```text
POST http://127.0.0.1:8000/api/agents/agent_lead_scoring/run
```

Expected request body:

```json
{
  "payload": {
    "reason": "Manual test run from AI Agent Center"
  }
}
```

Confirmed response:

```text
Status Code: 200 OK
```

Expected response shape:

```json
{
  "success": true,
  "data": {
    "agent_id": "agent_lead_scoring",
    "run_status": "queued",
    "message": "Agent run queued successfully.",
    "requested_at": "ISO datetime"
  },
  "error": null
}
```

Confirmed UI behavior:

- Request was sent from the frontend.
- Backend returned HTTP 200.
- UI showed a success message.
- Page did not crash.

## 10. Console warning note

During browser testing, many console warnings appeared, such as:

```text
The kernel ... for backend 'webgl' is already registered
The kernel ... for backend 'cpu' is already registered
```

These warnings were associated with injected browser scripts such as:

```text
content.js
classifier.js
```

They are not produced by the FlowPilot AI React source files and did not block the integration.

The actual verification was done through the Network tab, where all required API requests returned HTTP 200.

## 11. Backend unavailable fallback test

The backend fallback behavior should remain supported by the page.

Expected fallback behavior when FastAPI is stopped:

```text
AI Agent Center page still opens.
Mock AI agent data remains visible.
Backend AI agents unavailable, showing mock data.
Run Agent does not crash the page.
Agent run could not be submitted. Backend unavailable.
```

## 12. Confirmed UI behavior

Confirmed UI behavior:

- AI Agent Center page renders correctly.
- Agent list remains visible.
- Selected agent detail remains visible.
- Run Agent action works when backend is running.
- Success feedback appears after successful backend run.
- Existing visual style remained stable.
- No UI redesign was introduced.

## 13. What remains mock-only

The following AI Agent Center parts remain mock-only:

- Agent list is returned from mock backend data.
- Agent detail is returned from mock backend data.
- Manual agent run response is simulated.
- Agent run does not trigger real n8n execution.
- Agent run state is not persisted.
- KPI cards remain mock/static.
- Agent summary cards remain mock/static.
- Dynamic row selection remains limited or mock-based.
- Inspect Webhook action remains mock/static.

Other modules still mock-only or partially connected:

- Admin Users.
- Roles & Permissions.

## 14. What is intentionally not implemented yet

The following features were intentionally not implemented in this step:

- No PostgreSQL persistence.
- No n8n workflow calls.
- No real agent execution.
- No real authentication.
- No protected routes.
- No real RBAC enforcement.
- No Odoo integration.
- No Docker setup.
- No deployment setup.
- No Admin Users backend integration.
- No Roles & Permissions backend integration.

## 15. Recommended next step

Recommended next step:

```text
Step 42 — Add backend mock endpoints for Admin Users and Roles & Permissions.
```

Suggested backend endpoints:

```text
GET    /api/users
POST   /api/users
PUT    /api/users/{user_id}
POST   /api/users/{user_id}/deactivate
GET    /api/roles
PUT    /api/roles/{role_id}/permissions
```

Step 42 should remain backend-only first.

Do not connect Admin Users or Roles & Permissions frontend pages until the backend endpoints are created and tested in Swagger.

After Step 42, continue with:

```text
Step 43 — Connect Admin Users and Roles & Permissions pages to FastAPI.
```