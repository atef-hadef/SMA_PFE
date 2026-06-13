# FlowPilot AI Backend API Plan

Date: 2026-04-27  
Status: Planning only, no backend code implemented

## 1. Backend purpose in FlowPilot AI
The backend will serve as the secure integration and business API layer between the frontend and automation systems. It will expose stable APIs to the React app, orchestrate calls to automation workflows, and centralize business logic that should not live in the frontend.

## 2. Recommended backend framework: FastAPI
Recommended framework: FastAPI.

## 3. Why FastAPI is recommended for this project
- Strong fit for Python-based AI and automation ecosystems
- Fast development speed with clear, typed request and response models
- Automatic OpenAPI and Swagger documentation generation
- Built-in validation through Pydantic models
- Clean structure for modular domain-based APIs
- High performance for API services
- Easy integration with webhook-based orchestration and future async tasks

## 4. Planned architecture
React Frontend -> FastAPI Backend -> n8n Webhooks -> Odoo/PostgreSQL

## 5. Backend responsibilities
- Expose clean REST APIs to React
- Call n8n webhooks securely
- Hide n8n URLs and secrets from frontend
- Manage users, roles, and permissions later
- Manage leave requests
- Manage CRM leads
- Store workflow execution summaries later
- Expose monitoring data

## 6. API modules
- auth
- dashboard
- leave_requests
- crm
- agents
- workflow_monitoring
- admin_users
- roles_permissions

## 7. Initial API endpoint plan
### Auth
- POST /api/auth/login
- POST /api/auth/logout
- GET /api/auth/me

### Dashboard
- GET /api/dashboard/summary
- GET /api/dashboard/recent-activity

### Leave
- POST /api/leave-requests
- GET /api/leave-requests/my
- GET /api/leave-requests/pending
- GET /api/leave-requests/:id
- POST /api/leave-requests/:id/approve
- POST /api/leave-requests/:id/reject

### CRM
- GET /api/crm/leads
- GET /api/crm/leads/:leadId
- POST /api/crm/leads
- POST /api/crm/leads/:leadId/analyze
- POST /api/crm/leads/:leadId/score
- POST /api/crm/leads/:leadId/send-email

### AI Agents
- GET /api/agents
- GET /api/agents/:id
- POST /api/agents/:id/run

### Workflow Monitoring
- GET /api/workflow-executions
- GET /api/workflow-executions/:id
- POST /api/workflow-executions/:id/retry

### Admin
- GET /api/users
- POST /api/users
- PUT /api/users/:id
- POST /api/users/:id/deactivate
- GET /api/roles
- PUT /api/roles/:id/permissions

## 8. n8n integration rule
React must never call n8n directly.  
FastAPI will call n8n later.

## 9. Future database plan
Start later with:
- users
- roles
- leave_requests
- crm_leads
- workflow_executions

## 10. Security notes
- No n8n secrets in frontend
- No real JWT implementation yet
- Protected routes later
- Backend authorization later

## 11. What not to implement yet
- No backend code in this step
- No database schema yet
- No Docker setup yet
- No frontend service wiring yet
- No real authentication yet

## 12. Recommended next step
Step 23: Define detailed API contracts and DTOs before coding backend.
