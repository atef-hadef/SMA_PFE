# FlowPilot AI Admin Users and Roles Integration Smoke Test

Date: 2026-04-27  
Status: Step 43 and Step 43.5 completed

## 1. Step 43 completion summary

Step 43 is complete.

The Admin Users and Roles & Permissions frontend integration slices were validated successfully.

Confirmed outcomes:

- Admin Users page is connected to FastAPI.
- Roles & Permissions page is connected to FastAPI.
- Admin Users page loads users from the backend.
- Roles & Permissions page loads roles and permissions from the backend.
- Deactivate User action sends a POST request to the backend.
- Save Changes action sends a PUT request to the backend.
- Roles & Permissions matrix is now editable from the UI.
- Permission checkboxes update local state immediately.
- Success messages appear after successful backend actions.
- Backend unavailable fallback was tested.
- Pages remain usable when backend is stopped.
- Mock fallback data appears when backend is unavailable.
- No blank page appeared.
- PostgreSQL, real authentication, real RBAC enforcement, and protected routes are still not connected.

## 2. Step 43.5 completion summary

Step 43.5 was added as a correction before Step 44.

Reason:

The Roles & Permissions page was connected to the backend, but the permission matrix was not truly editable. The Save Changes button existed, but the admin could not clearly modify permissions before saving.

Correction implemented:

- Permission matrix cells now include editable checkboxes.
- Admin can toggle permissions for the selected role.
- Enabled and disabled states update visually.
- Save Changes serializes the current selected role permissions.
- The updated permission list is sent to FastAPI using:

```text
PUT /api/roles/{role_id}/permissions
```

Current limitation:

This is still mock/API-level RBAC. Permission changes are not yet persisted in PostgreSQL and are not yet enforced by real backend authorization logic.

## 3. Integration flow tested

Admin Users flow:

```text
React Admin Users Page
→ frontend admin service
→ FastAPI backend
→ mock users response
```

Roles & Permissions flow:

```text
React Roles & Permissions Page
→ frontend admin service
→ FastAPI backend
→ mock roles and permissions response
```

Permission update flow:

```text
Admin toggles permissions in UI
→ local permission state updates
→ Save Changes clicked
→ PUT /api/roles/{role_id}/permissions
→ FastAPI returns mock updated permissions response
→ success message appears
```

Fallback flow:

```text
Backend stopped
→ Admin pages refreshed
→ frontend keeps pages usable
→ mock fallback data appears
→ backend unavailable messages appear
```

## 4. Backend endpoints used

The following backend endpoints were used:

```text
GET  http://127.0.0.1:8000/api/users
POST http://127.0.0.1:8000/api/users/{user_id}/deactivate

GET  http://127.0.0.1:8000/api/roles
PUT  http://127.0.0.1:8000/api/roles/{role_id}/permissions
```

The following endpoints exist in the backend but are not fully connected to UI forms yet:

```text
POST http://127.0.0.1:8000/api/users
PUT  http://127.0.0.1:8000/api/users/{user_id}
```

Reason:

The current Admin Users page does not yet provide full Add User or Edit User input forms.

## 5. Frontend pages tested

Frontend routes tested:

```text
http://localhost:5173/admin/users
http://localhost:5173/admin/roles-permissions
```

## 6. Files likely involved in the integration

Frontend files likely involved:

```text
frontend/src/pages/AdminUsersPage.tsx
frontend/src/pages/RolesPermissionsPage.tsx
frontend/src/services/adminService.ts
frontend/src/services/apiClient.ts
frontend/src/services/index.ts
frontend/src/data/adminUsersData.ts
frontend/src/data/rolesPermissionsData.ts
```

Backend files likely involved:

```text
backend/app/api/admin.py
backend/app/services/admin_service.py
backend/app/schemas/admin.py
backend/app/main.py
```

Note:

This list is used for traceability. It is not a complete dependency map.

## 7. Manual Admin Users page test procedure

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

### Step 3: Open Admin Users page

Open:

```text
http://localhost:5173/admin/users
```

Confirmed behavior:

- Admin Users page opened normally.
- Sidebar appeared.
- Top header appeared.
- Admin Users page content appeared.
- Users table/list appeared.
- Backend users appeared when backend was running.
- No blank page appeared.

## 8. Network tab verification for users

Browser DevTools Network tab was used to verify the backend request.

Confirmed request:

```text
GET http://127.0.0.1:8000/api/users
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
        "id": "user_001",
        "name": "Admin User",
        "email": "admin@flowpilot.ai",
        "role": "Admin",
        "department": "IT",
        "status": "active"
      },
      {
        "id": "user_010",
        "name": "Sarah N.",
        "email": "sarah@flowpilot.ai",
        "role": "Employee",
        "department": "Operations",
        "status": "active"
      }
    ]
  },
  "error": null
}
```

This confirms that the Admin Users page loads user records from FastAPI.

## 9. Network tab verification for Deactivate User action

The Deactivate User action was tested from the Admin Users interface.

Confirmed request:

```text
POST http://127.0.0.1:8000/api/users/user_010/deactivate
```

Expected request body:

```json
{
  "reason": "User no longer active in the team"
}
```

Confirmed behavior:

- Request was sent from the frontend.
- Backend returned HTTP 200.
- UI showed success message.
- Page did not crash.

Expected response shape:

```json
{
  "success": true,
  "data": {
    "id": "user_010",
    "status": "inactive",
    "deactivated_at": "ISO datetime",
    "reason": "User no longer active in the team"
  },
  "error": null
}
```

## 10. Manual Roles & Permissions page test procedure

Open:

```text
http://localhost:5173/admin/roles-permissions
```

Confirmed behavior:

- Roles & Permissions page opened normally.
- Roles list appeared.
- Permission matrix appeared.
- Backend roles appeared when backend was running.
- A default role such as CRM Manager was selected.
- Permission checkboxes were visible.
- No blank page appeared.

## 11. Network tab verification for roles

Browser DevTools Network tab was used to verify the backend request.

Confirmed request:

```text
GET http://127.0.0.1:8000/api/roles
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
        "id": "role_admin",
        "name": "Admin",
        "description": "Full system administration access.",
        "permissions": [
          "dashboard.read",
          "leave.read",
          "leave.approve",
          "crm.read",
          "crm.manage",
          "agents.read",
          "workflow.read",
          "admin.users.manage",
          "admin.roles.manage"
        ]
      },
      {
        "id": "role_crm_manager",
        "name": "CRM Manager",
        "description": "Access to CRM leads, AI agents, and workflow monitoring.",
        "permissions": [
          "dashboard.read",
          "crm.read",
          "crm.manage",
          "agents.read",
          "workflow.read"
        ]
      }
    ]
  },
  "error": null
}
```

This confirms that the Roles & Permissions page loads role data from FastAPI.

## 12. Permission matrix edit test

The permission matrix was tested manually.

Confirmed behavior:

- A role can be selected.
- Permission checkboxes can be toggled.
- Enabled permissions show an enabled state.
- Disabled permissions show a disabled state.
- The local UI updates immediately after toggling.
- Switching role updates the visible permission state.
- Page does not crash.

Current UI note:

The current matrix is useful for testing permission editing and save behavior. It is not yet the final ideal RBAC interface. A later UI/content cleanup step should improve the matrix into a clearer action-based permission editor.

Recommended final permission model:

```text
dashboard.read

leave.read
leave.create
leave.approve
leave.reject

crm.read
crm.create
crm.update
crm.manage
crm.analyze
crm.score

agents.read
agents.run

workflow.read
workflow.retry

admin.users.read
admin.users.manage

admin.roles.read
admin.roles.manage
```

## 13. Network tab verification for Save Changes

The Save Changes action was tested from the Roles & Permissions interface.

Confirmed request:

```text
PUT http://127.0.0.1:8000/api/roles/role_crm_manager/permissions
```

Expected request body shape:

```json
{
  "permissions": [
    "dashboard.read",
    "crm.read",
    "workflow.read"
  ]
}
```

Confirmed behavior:

- Request was sent from the frontend.
- Backend returned HTTP 200.
- UI showed success message:

```text
Role permissions saved successfully.
```

- Page did not crash.

Expected response shape:

```json
{
  "success": true,
  "data": {
    "id": "role_crm_manager",
    "name": "CRM Manager",
    "permissions": [
      "dashboard.read",
      "crm.read",
      "workflow.read"
    ],
    "updated_at": "ISO datetime"
  },
  "error": null
}
```

## 14. Backend unavailable fallback test

The backend was stopped with:

```text
Ctrl + C
```

Then the Admin Users page was refreshed:

```text
http://localhost:5173/admin/users
```

Confirmed fallback behavior:

- Admin Users page still opened.
- No blank page appeared.
- Mock users remained visible.
- Backend unavailable message appeared:

```text
Backend admin users unavailable, showing mock data.
```

Deactivate behavior while backend was unavailable:

- Page did not crash.
- Error message appeared:

```text
Admin action could not be submitted. Backend unavailable.
```

Then the Roles & Permissions page was refreshed:

```text
http://localhost:5173/admin/roles-permissions
```

Confirmed fallback behavior:

- Roles & Permissions page still opened.
- No blank page appeared.
- Mock roles remained visible.
- Permission toggling still worked locally.
- Backend unavailable message appeared:

```text
Backend roles unavailable, showing mock data.
```

Save Changes behavior while backend was unavailable:

- Page did not crash.
- Error message appeared:

```text
Role permissions could not be saved. Backend unavailable.
```

## 15. Confirmed UI behavior

Confirmed UI behavior:

- Admin Users page renders correctly.
- Users list remains visible.
- Deactivate User action works when backend is running.
- Roles & Permissions page renders correctly.
- Roles list remains visible.
- Permission matrix is editable.
- Save Changes works when backend is running.
- Success feedback appears after successful backend actions.
- Error feedback appears if backend is unavailable.
- Existing visual style remained stable.
- No full UI redesign was introduced.

## 16. What remains mock-only

The following Admin/Roles parts remain mock-only:

- User list is returned from mock backend data.
- User deactivation response is simulated.
- Role list is returned from mock backend data.
- Permission update response is simulated.
- Permission changes are not persisted permanently.
- Add User action UI is not implemented.
- Edit User action UI is not implemented.
- Create Role action UI is not implemented.
- Reset action is not implemented.
- Permission matrix is editable but not yet final RBAC logic.
- Real backend authorization is not enforced.

Other remaining system limitations:

- No PostgreSQL persistence.
- No real authentication.
- No protected routes.
- No real RBAC enforcement.
- No n8n integration.
- No Odoo integration.

## 17. What is intentionally not implemented yet

The following features were intentionally not implemented in this step:

- No PostgreSQL persistence.
- No real authentication.
- No protected routes.
- No real RBAC enforcement.
- No n8n workflow calls.
- No Odoo integration.
- No Docker setup.
- No deployment setup.
- No full user management forms.
- No final permission model enforcement.

## 18. Recommended next step

Recommended next step:

```text
Step 45 — Controlled UI and Content Cleanup Before Real Data Integration.
```

Purpose:

Improve usability and presentation quality before adding PostgreSQL and n8n.

Focus areas:

```text
- Remove or replace visible “mock” wording.
- Improve headings and labels.
- Make pages more user-friendly.
- Reduce unnecessary technical details.
- Improve Roles & Permissions matrix logic.
- Fix obvious layout issues.
- Keep all existing API integrations working.
```

After Step 45, continue with:

```text
Step 46 — PostgreSQL planning and schema design.
```