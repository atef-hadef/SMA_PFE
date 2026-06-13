# Step 69 - Authentication and RBAC

## 1. Objective

Implement a permission-based authentication and authorization layer for FlowPilot AI so that users can access only the pages and backend actions allowed by their role.

This step protects both sides:

- Frontend route/menu/action visibility.
- Backend FastAPI authorization with `401 Unauthorized` and `403 Forbidden`.

## 2. Existing State Before Changes

Audit findings:

- Backend already had PostgreSQL models for `users`, `roles`, and `role_permissions`.
- The existing admin UI used mock/fallback role permission names such as `crm.read`, `leave.read`, and `workflow.read`.
- There was no complete JWT auth router, auth dependency, login flow, or `/api/auth/me`.
- CRM, leave, dashboard, workflow, agents, admin, and assistant endpoints were callable without role permission checks.
- Frontend routing in `App.tsx` was not protected.
- Sidebar/menu filtering existed only as mock UI behavior and was not enough for security.
- Seed data existed, but roles and permissions were incomplete for the required Admin, Manager, Sales, HR, Employee, and AI Supervisor model.

## 3. Architecture

Backend:

- `POST /api/auth/login` verifies email/password against PostgreSQL.
- Passwords are hashed with PBKDF2-HMAC-SHA256 and never returned.
- JWT access tokens are signed server-side with `JWT_SECRET_KEY`.
- `GET /api/auth/me` returns the current user and permissions from PostgreSQL.
- `get_current_user` validates the bearer token.
- `require_permission(permission)` enforces one permission.
- `require_any_permission([...])` enforces one of several permissions.
- n8n callback-style integration keeps FastAPI as the central layer; selected callback endpoints use the shared internal secret.

Frontend:

- `AuthContext` loads the current user from `/api/auth/me`.
- `useAuth()` exposes `login`, `logout`, `hasPermission`, and `hasAnyPermission`.
- `ProtectedRoute` requires authentication.
- `RequirePermission` requires route permissions and renders `AccessDeniedPage` for forbidden URLs.
- `apiClient` attaches the JWT and routes `401` to login and `403` to access denied.
- Sidebar items and sensitive action buttons are permission-aware.

## 4. Role-Permission Matrix

Admin:
All permissions.

Manager:
`dashboard.view`, `crm.leads.view`, `crm.interactions.create`, `crm.drafts.review`, `crm.email.approve`, `crm.customer.convert`, `leave.request.view_all`, `leave.request.approve`, `leave.request.reject`, `workflow.monitor.view`, `workflow.executions.view`, `agents.view`.

Sales:
`dashboard.view`, `crm.leads.view`, `crm.leads.create`, `crm.leads.update`, `crm.interactions.create`, `crm.drafts.generate`, `crm.drafts.review`, `crm.email.send`.

HR:
`dashboard.view`, `leave.request.view_all`, `leave.request.approve`, `leave.request.reject`, `leave.request.hr_validate`.

Employee:
`dashboard.view`, `leave.request.create`, `leave.request.view_own`.

AI Supervisor:
`dashboard.view`, `workflow.monitor.view`, `workflow.executions.view`, `workflow.executions.retry`, `agents.view`, `agents.run`.

## 5. Backend Protected Endpoints

Examples of enforced permissions:

- Auth: `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`.
- Dashboard: `GET /api/dashboard/summary` -> `dashboard.view`.
- CRM:
  - `GET /api/crm/leads` -> `crm.leads.view`
  - `POST /api/crm/leads` -> `crm.leads.create`
  - `GET /api/crm/leads/{lead_id}` -> `crm.leads.view`
  - `POST /api/crm/leads/{lead_id}/interactions` -> `crm.interactions.create`
  - `POST /api/crm/leads/{lead_id}/generate-communication-draft` -> `crm.drafts.generate`
  - draft review/update/reject/upload/delete attachment -> `crm.drafts.review`
  - draft approve -> `crm.email.approve`
  - draft send -> `crm.email.send`
  - convert to customer -> `crm.customer.convert`
- Leave:
  - `POST /api/leave-requests` -> `leave.request.create`
  - `GET /api/leave-requests/my` -> `leave.request.view_own`
  - `GET /api/leave-requests` -> `leave.request.view_all`
  - `GET /api/leave-requests/pending` -> `leave.request.view_all` or `leave.request.approve`
  - approve -> `leave.request.approve`
  - reject -> `leave.request.reject`
- Workflow monitoring:
  - list -> `workflow.monitor.view` or `workflow.executions.view`
  - detail -> `workflow.executions.view`
  - retry -> `workflow.executions.retry`
- Agents:
  - list/detail -> `agents.view`
  - run -> `agents.run`
- Admin:
  - user routes -> `admin.users.manage`
  - role/permission routes -> `admin.roles.manage`

## 6. Frontend Protected Pages and Actions

Protected pages:

- Dashboard -> `dashboard.view`
- Assistant -> `dashboard.view`
- CRM Leads and CRM Lead Details -> `crm.leads.view`
- Leave Request -> `leave.request.create` or `leave.request.view_own`
- Manager Approval -> `leave.request.approve` or `leave.request.view_all`
- Workflow Monitoring -> `workflow.monitor.view` or `workflow.executions.view`
- AI Agent Center -> `agents.view`
- Admin Users -> `admin.users.manage`
- Roles & Permissions -> `admin.roles.manage`

Protected actions:

- Leave create, approve, reject.
- Workflow retry.
- Agent run.
- Admin deactivate user and role permission save.
- CRM interaction creation, draft generation, draft review/edit/attachment, draft approval, email send, and customer conversion.

## 7. Seed Users

Development-only test password for all seed users:

`FlowPilot@123`

Seed accounts:

- `admin@flowpilot.ai` -> Admin
- `manager@flowpilot.ai` -> Manager
- `sales@flowpilot.ai` -> Sales
- `hr@flowpilot.ai` -> HR
- `employee@flowpilot.ai` -> Employee
- `ai.supervisor@flowpilot.ai` -> AI Supervisor

The password is hashed in PostgreSQL. It must not be reused outside local PFE demo/testing.

Seed command:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\seed_database.py
```

If tables are not created yet:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\create_tables.py
```

## 8. Test Results

Executed validation:

- `npm.cmd install` -> up to date, 0 vulnerabilities.
- `npm.cmd run lint` -> passed.
- `npm.cmd run build` -> passed when run outside the sandbox; the sandbox blocked Vite/Tailwind native dependency loading with `EPERM`.
- `python -m compileall backend` -> passed.
- `$env:PYTHONPATH='backend'; .\backend\.venv\Scripts\python.exe -m unittest discover backend/tests` -> 15 tests passed.

## 9. Known Limitations

- JWT logout is stateless; the frontend removes the token, but there is no server-side token denylist yet.
- The local default `JWT_SECRET_KEY` is development-only and must be overridden for any real deployment.
- Some n8n callback/integration endpoints intentionally allow shared-secret access so existing workflows can continue to call FastAPI.
- The manual smoke checklist still needs to be executed in a running browser/API environment with the seeded database.

## 10. Next Recommended Step

Add focused automated API security tests for representative `401`, `403`, and `200/201` cases per role. This will lock the RBAC behavior before the final demo and prevent future route regressions.

## Manual Smoke Checklist

- Admin can see and use all pages.
- Manager can view CRM, Manager Approval, Workflow Monitoring, and Agents, but not Admin pages.
- Sales can use CRM lead/draft/interactions and cannot approve leave or access Admin pages.
- HR can access leave approval and cannot access CRM advanced actions or Admin pages.
- Employee can create/view own leave requests and cannot access CRM, workflows, agents, or Admin pages.
- AI Supervisor can monitor/retry workflows and run agents, but cannot manage users or approve leave.
- Direct API calls without token return `401`.
- Direct API calls with a token lacking the permission return `403`.
- Authorized API calls return `200` or `201`.
