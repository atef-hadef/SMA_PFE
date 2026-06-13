# FlowPilot AI API Contracts

Date: 2026-04-27  
Status: Contract-only document for future FastAPI backend implementation

## 1. Purpose of this API contract document
This document defines the initial HTTP API contracts between the React frontend and the future FastAPI backend.

Goals:
- Align frontend and backend on endpoint shapes before coding backend logic
- Keep payloads consistent across modules
- Reduce integration risk by defining request and response models early
- Clarify which endpoints are database-only and which will trigger n8n later

Scope:
- Contract definitions only
- No backend code, no migrations, no frontend service wiring

## 2. Global API conventions
### 2.1 Base path
- All endpoints are under: /api

### 2.2 Content type
- Request and response format: JSON
- Content-Type: application/json

### 2.3 Date and time format
- Use ISO 8601 strings (UTC preferred), for example: 2026-04-27T14:30:00Z

### 2.4 Standard success response shape
```json
{
  "success": true,
  "message": "Optional human-readable message",
  "data": {}
}
```

### 2.5 Standard error response shape
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error message",
    "details": []
  }
}
```

### 2.6 Standard pagination shape for list endpoints
```json
{
  "success": true,
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 0,
      "total_pages": 0
    }
  }
}
```

## 3. Auth API contracts
### POST /api/auth/login
- Purpose: authenticate user and return session/auth context
- Request body:
```json
{
  "email": "admin@flowpilot.ai",
  "password": "string"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "user_001",
      "name": "Admin User",
      "email": "admin@flowpilot.ai",
      "role": "Admin"
    },
    "access_token": "placeholder-token",
    "token_type": "bearer"
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 INVALID_CREDENTIALS, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/authService.ts (planned, not created yet)
- Integration type: database-only

### POST /api/auth/logout
- Purpose: invalidate user session/token
- Request body: optional empty body
- Response body example:
```json
{
  "success": true,
  "message": "Logged out successfully",
  "data": null
}
```
- Possible errors: 401 UNAUTHORIZED, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/authService.ts (planned)
- Integration type: database-only

### GET /api/auth/me
- Purpose: return current authenticated user profile and role
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "user_001",
    "name": "Admin User",
    "email": "admin@flowpilot.ai",
    "role": "Admin"
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/authService.ts (planned)
- Integration type: database-only

## 4. Dashboard API contracts
### GET /api/dashboard/summary
- Purpose: fetch dashboard KPI summary
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "leave_requests": 24,
    "pending_approvals": 8,
    "crm_leads": 128,
    "active_agents": 7
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/dashboardService.ts (planned)
- Integration type: database-only

### GET /api/dashboard/recent-activity
- Purpose: fetch recent cross-module operational events
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "evt_001",
        "module": "CRM",
        "title": "Lead scored",
        "status": "success",
        "created_at": "2026-04-27T09:35:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1
    }
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/dashboardService.ts (planned)
- Integration type: database-only

## 5. Leave Request API contracts
### POST /api/leave-requests
- Purpose: create a new leave request
- Request body:
```json
{
  "leave_type": "Annual Leave",
  "start_date": "2026-05-03",
  "end_date": "2026-05-05",
  "reason": "Family event"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "lr_1024",
    "employee_id": "user_010",
    "leave_type": "Annual Leave",
    "start_date": "2026-05-03",
    "end_date": "2026-05-05",
    "status": "pending",
    "created_at": "2026-04-27T10:00:00Z"
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 409 BUSINESS_RULE_CONFLICT, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/leaveService.ts
- Integration type: database-only first, may trigger n8n later

### GET /api/leave-requests/my
- Purpose: list leave requests for current user
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "lr_1024",
        "leave_type": "Annual Leave",
        "status": "pending",
        "start_date": "2026-05-03",
        "end_date": "2026-05-05"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1
    }
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/leaveService.ts
- Integration type: database-only

### GET /api/leave-requests/pending
- Purpose: list pending leave requests for manager/HR review
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "lr_1024",
        "employee_name": "Sarah N.",
        "leave_type": "Annual Leave",
        "status": "pending"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1
    }
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 403 FORBIDDEN, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/leaveService.ts
- Integration type: database-only

### GET /api/leave-requests/{request_id}
- Purpose: fetch details of a leave request
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "lr_1024",
    "employee_name": "Sarah N.",
    "leave_type": "Annual Leave",
    "reason": "Family event",
    "status": "pending",
    "start_date": "2026-05-03",
    "end_date": "2026-05-05"
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 403 FORBIDDEN, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/leaveService.ts
- Integration type: database-only

### POST /api/leave-requests/{request_id}/approve
- Purpose: approve a leave request
- Request body:
```json
{
  "comment": "Approved"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "lr_1024",
    "status": "approved",
    "updated_at": "2026-04-27T10:05:00Z"
  }
}
```
- Possible errors: 400 INVALID_STATE, 401 UNAUTHORIZED, 403 FORBIDDEN, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/leaveService.ts
- Integration type: database-only first, may trigger n8n later

### POST /api/leave-requests/{request_id}/reject
- Purpose: reject a leave request
- Request body:
```json
{
  "comment": "Insufficient coverage"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "lr_1024",
    "status": "rejected",
    "updated_at": "2026-04-27T10:07:00Z"
  }
}
```
- Possible errors: 400 INVALID_STATE, 401 UNAUTHORIZED, 403 FORBIDDEN, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/leaveService.ts
- Integration type: database-only first, may trigger n8n later

## 6. CRM API contracts
### GET /api/crm/leads
- Purpose: list CRM leads
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "lead_001",
        "name": "Northwind Logistics",
        "company": "Northwind Group",
        "score": 94
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1
    }
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/crmService.ts
- Integration type: database-only

### GET /api/crm/leads/{lead_id}
- Purpose: fetch a specific lead
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "lead_001",
    "name": "Northwind Logistics",
    "company": "Northwind Group",
    "email": "ops@northwind.com",
    "score": 94,
    "status": "hot"
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/crmService.ts
- Integration type: database-only

### POST /api/crm/leads
- Purpose: create a new CRM lead
- Request body:
```json
{
  "name": "Northwind Logistics",
  "company": "Northwind Group",
  "email": "ops@northwind.com",
  "source": "web"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "lead_001",
    "name": "Northwind Logistics",
    "company": "Northwind Group",
    "score": 0
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 409 CONFLICT, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/crmService.ts
- Integration type: database-only

### POST /api/crm/leads/{lead_id}/analyze
- Purpose: run AI analysis for lead sentiment/intention/urgency
- Request body:
```json
{
  "lead_id": "lead_001"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "lead_id": "lead_001",
    "sentiment": "positive",
    "intention": "purchase-ready",
    "urgency": "high"
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/crmService.ts
- Integration type: will trigger n8n later

### POST /api/crm/leads/{lead_id}/score
- Purpose: compute or refresh lead score
- Request body:
```json
{
  "lead_id": "lead_001"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "lead_id": "lead_001",
    "score": 94
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/crmService.ts
- Integration type: will trigger n8n later

### POST /api/crm/leads/{lead_id}/send-email
- Purpose: send generated follow-up email for a lead
- Request body:
```json
{
  "subject": "Thanks for your interest",
  "body": "Hello, ..."
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "lead_id": "lead_001",
    "delivery_status": "queued"
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/crmService.ts
- Integration type: will trigger n8n later

## 7. AI Agents API contracts
### GET /api/agents
- Purpose: list AI agents
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "agent_a5",
        "name": "Routing Agent A5",
        "process": "CRM",
        "status": "success"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1
    }
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/agentService.ts
- Integration type: database-only

### GET /api/agents/{agent_id}
- Purpose: fetch agent details
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "agent_a5",
    "name": "Routing Agent A5",
    "process": "CRM",
    "status": "success",
    "webhook_path": "/webhook/ai-agent-center/routing-a5"
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/agentService.ts
- Integration type: database-only

### POST /api/agents/{agent_id}/run
- Purpose: manually trigger agent execution
- Request body:
```json
{
  "payload": {}
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "agent_id": "agent_a5",
    "run_status": "queued"
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/agentService.ts
- Integration type: will trigger n8n later

## 8. Workflow Monitoring API contracts
### GET /api/workflow-executions
- Purpose: list workflow execution records
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "exec_9081",
        "workflow_name": "CRM Lead Scoring Flow",
        "status": "success",
        "duration": "1.0 min"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1
    }
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/workflowService.ts
- Integration type: database-only

### GET /api/workflow-executions/{execution_id}
- Purpose: fetch execution details
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "exec_9081",
    "workflow_name": "CRM Lead Scoring Flow",
    "status": "success",
    "input_summary": "...",
    "output_summary": "..."
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/workflowService.ts
- Integration type: database-only

### POST /api/workflow-executions/{execution_id}/retry
- Purpose: retry a failed workflow execution
- Request body:
```json
{
  "reason": "Manual retry from monitoring UI"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "execution_id": "exec_9081",
    "retry_status": "queued"
  }
}
```
- Possible errors: 400 INVALID_STATE, 401 UNAUTHORIZED, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/workflowService.ts
- Integration type: will trigger n8n later

## 9. Admin Users API contracts
### GET /api/users
- Purpose: list users for admin management
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "user_001",
        "name": "Admin User",
        "email": "admin@flowpilot.ai",
        "role": "Admin",
        "status": "active"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1
    }
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 403 FORBIDDEN, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/adminService.ts
- Integration type: database-only

### POST /api/users
- Purpose: create a user
- Request body:
```json
{
  "name": "New User",
  "email": "new@flowpilot.ai",
  "role": "Manager",
  "department": "Operations"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "user_010",
    "name": "New User",
    "email": "new@flowpilot.ai",
    "role": "Manager",
    "status": "active"
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 403 FORBIDDEN, 409 CONFLICT, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/adminService.ts
- Integration type: database-only

### PUT /api/users/{user_id}
- Purpose: update user details
- Request body:
```json
{
  "name": "Updated Name",
  "role": "CRM Manager",
  "department": "Sales"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "user_010",
    "name": "Updated Name",
    "role": "CRM Manager"
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 403 FORBIDDEN, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/adminService.ts
- Integration type: database-only

### POST /api/users/{user_id}/deactivate
- Purpose: deactivate user account
- Request body:
```json
{
  "reason": "No longer active in team"
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "user_010",
    "status": "inactive"
  }
}
```
- Possible errors: 400 INVALID_STATE, 401 UNAUTHORIZED, 403 FORBIDDEN, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/adminService.ts
- Integration type: database-only

## 10. Roles and Permissions API contracts
### GET /api/roles
- Purpose: list roles and summary permissions
- Request body: none
- Response body example:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "role_001",
        "name": "Operations Manager",
        "permissions": ["dashboard.read", "leave.approve"]
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1
    }
  }
}
```
- Possible errors: 401 UNAUTHORIZED, 403 FORBIDDEN, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/adminService.ts
- Integration type: database-only

### PUT /api/roles/{role_id}/permissions
- Purpose: update permission set for role
- Request body:
```json
{
  "permissions": [
    "dashboard.read",
    "leave.read",
    "leave.approve",
    "crm.read"
  ]
}
```
- Response body example:
```json
{
  "success": true,
  "data": {
    "id": "role_001",
    "name": "Operations Manager",
    "permissions": [
      "dashboard.read",
      "leave.read",
      "leave.approve",
      "crm.read"
    ]
  }
}
```
- Possible errors: 400 VALIDATION_ERROR, 401 UNAUTHORIZED, 403 FORBIDDEN, 404 NOT_FOUND, 500 INTERNAL_ERROR
- Frontend service file: frontend/src/services/adminService.ts
- Integration type: database-only

## 11. Endpoint ownership summary (frontend service + integration type)
- Auth endpoints: frontend/src/services/authService.ts (planned), database-only
- Dashboard endpoints: frontend/src/services/dashboardService.ts (planned), database-only
- Leave endpoints: frontend/src/services/leaveService.ts, database-first then optional n8n trigger
- CRM endpoints: frontend/src/services/crmService.ts, mixed database and future n8n trigger
- Agent endpoints: frontend/src/services/agentService.ts, mixed database and future n8n trigger
- Workflow endpoints: frontend/src/services/workflowService.ts, mixed database and future n8n trigger
- Admin users/roles endpoints: frontend/src/services/adminService.ts, database-only

## 12. Initial DTO names for future FastAPI/Pydantic models
Core DTOs:
- LoginRequest
- AuthUserResponse
- DashboardSummaryResponse
- LeaveRequestCreate
- LeaveRequestResponse
- LeaveDecisionRequest
- CrmLeadCreate
- CrmLeadResponse
- CrmLeadAnalysisResponse
- AgentResponse
- WorkflowExecutionResponse
- UserCreate
- UserResponse
- RoleResponse
- UpdateRolePermissionsRequest

Additional helpful DTOs:
- ApiSuccess[T]
- ApiError
- PaginationMeta
- PaginatedResponse[T]
- DashboardRecentActivityItem
- RetryWorkflowExecutionRequest
- SendLeadEmailRequest
- DeactivateUserRequest

## 13. Implementation rule
- This document is a contract only.
- Do not implement everything at once.
- Backend implementation should start with a small vertical slice.

## 14. Recommended first backend implementation slice
Start with a minimal, low-risk slice:
1. Health check endpoint:
   - GET /api/health
2. Dashboard read-only endpoint:
   - GET /api/dashboard/summary
3. Leave request create endpoint with mock/in-memory response first:
   - POST /api/leave-requests
4. No real auth yet
5. No n8n call until basic backend is running

This slice validates FastAPI structure, request/response contracts, and frontend-to-backend integration basics before adding auth, DB persistence, or workflow orchestration.
