# FlowPilot AI Frontend MVP Summary

Date: 2026-04-27  
Status: Step 20 Completed

## 1. Project frontend overview
FlowPilot AI frontend MVP is a multi-module web interface for an AI Multi-Agent System focused on business process automation. The current implementation covers core operational domains with mock data and placeholder service layers.

Implemented operational modules:
- Dashboard supervision
- Leave request workflow
- Manager approvals
- CRM leads and lead details
- AI agent center
- Workflow monitoring
- Admin users
- Roles and permissions

This MVP is frontend-only at the integration level. No real backend calls, no real authentication enforcement, and no direct n8n calls from React are implemented.

## 2. Frontend technology stack
- React
- TypeScript
- Vite
- Tailwind CSS
- React Router

## 3. Current folder structure
High-level workspace structure:
- frontend
- workflows
- specs
- docs

Frontend structure summary:
- frontend/src/App.tsx
- frontend/src/main.tsx
- frontend/src/layouts
- frontend/src/pages
- frontend/src/components/common
- frontend/src/data
- frontend/src/services
- frontend/src/types
- frontend/src/utils

Detailed implemented frontend folders:
- frontend/src/layouts: MainLayout.tsx, Sidebar.tsx, TopHeader.tsx
- frontend/src/components/common: ActionButton.tsx, DataTable.tsx, PageHeader.tsx, StatCard.tsx, StatusBadge.tsx, index.ts
- frontend/src/pages: DashboardPage.tsx, LeaveRequestPage.tsx, ManagerApprovalPage.tsx, CRMLeadsPage.tsx, CRMLeadDetailsPage.tsx, AIAgentCenterPage.tsx, WorkflowMonitoringPage.tsx, AdminUsersPage.tsx, RolesPermissionsPage.tsx
- frontend/src/data: dashboardData.ts, leaveData.ts, managerApprovalData.ts, crmLeadsData.ts, crmLeadDetailsData.ts, aiAgentsData.ts, workflowMonitoringData.ts, adminUsersData.ts, rolesPermissionsData.ts, mockAuthData.ts
- frontend/src/services: apiClient.ts, leaveService.ts, crmService.ts, workflowService.ts, adminService.ts, agentService.ts, index.ts

## 4. Implemented pages
- DashboardPage
- LeaveRequestPage
- ManagerApprovalPage
- CRMLeadsPage
- CRMLeadDetailsPage
- AIAgentCenterPage
- WorkflowMonitoringPage
- AdminUsersPage
- RolesPermissionsPage

## 5. Implemented routes
Defined in frontend/src/App.tsx:
- / redirects to /dashboard
- /dashboard
- /leave-requests
- /manager-approvals
- /crm-leads
- /crm-lead-details
- /ai-agents
- /workflow-monitoring
- /admin/users
- /admin/roles-permissions

## 6. Layout files
- MainLayout.tsx: global shell wrapper (sidebar + top header + content area)
- Sidebar.tsx: navigation, admin section, active state UI, mock role-aware filtering
- TopHeader.tsx: global top bar for page context and actions

## 7. Reusable components
Current shared components in frontend/src/components/common:
- StatCard: KPI card display
- StatusBadge: status indicator with visual variants
- PageHeader: section hero/header block
- ActionButton: primary and secondary actions
- DataTable: simple typed process-owner-status table
- index.ts: centralized exports

## 8. Mock data files
Mock data is organized per module under frontend/src/data:
- dashboardData.ts
- leaveData.ts
- managerApprovalData.ts
- crmLeadsData.ts
- crmLeadDetailsData.ts
- aiAgentsData.ts
- workflowMonitoringData.ts
- adminUsersData.ts
- rolesPermissionsData.ts
- mockAuthData.ts

## 9. Service placeholder files
Service layer placeholders are organized under frontend/src/services:
- apiClient.ts
- leaveService.ts
- crmService.ts
- workflowService.ts
- adminService.ts
- agentService.ts
- index.ts

Current service behavior:
- apiClient defines API_BASE_URL and helper methods: get, post, put, remove
- request helpers intentionally reject with API client not connected yet
- endpoint-shaped typed placeholder functions exist in each domain service
- services are prepared for future backend integration but not wired into pages yet

## 10. Mock role-based sidebar behavior
Role and route visibility are currently driven by mockAuthData.ts:
- Roles defined: Admin, Employee, Manager, HR Officer, Sales Agent, CRM Manager
- allowedNavigationPaths map controls route visibility per role
- Sidebar filters visible primary/admin navigation from allowed paths
- Admin block is displayed only for Admin role
- Active state handling includes CRM lead detail highlighting under CRM Leads

Important note:
- This is UI-level mock role behavior only, not protected route security.

## 11. Manual test results from Step 20
Step 20 verification outcome:
- Lint passed
- Build passed
- Manual browser route testing passed
- Sidebar active states work
- Mock role-based sidebar behavior works
- Pages use mock data
- Service placeholder files exist
- No backend connection exists yet
- React does not call n8n directly
- No real authentication or protected routes yet

## 12. What is not implemented yet
- Real backend API integration
- Real data persistence and server state
- Real authentication and authorization
- Protected route enforcement
- Token/session management
- Environment-specific API configuration
- End-to-end integration with n8n through backend
- Production-grade error handling and retry strategy

## 13. Current limitations
- Data is static mock data per page
- Role behavior is visual/filtering only and can be bypassed by URL navigation
- Service layer is placeholder-only and intentionally disconnected
- No server-side validation or audit trails
- No real-time updates from workflows/agents
- No automated integration or e2e tests are documented yet

## 14. How to run the frontend
From the frontend directory:
1. npm.cmd install
2. npm.cmd run dev
3. Open the local URL shown by Vite (typically http://localhost:5173)

Quality checks:
1. npm.cmd run lint
2. npm.cmd run build

## 15. Recommended next step after this documentation
Recommended next step: begin backend-integration preparation in a controlled way without changing UI behavior.

Suggested order:
1. Define backend API contracts for each domain service (leave, CRM, workflow, admin, agents).
2. Introduce typed request/response DTOs and shared error shapes.
3. Replace placeholder service methods with real HTTP calls through apiClient.
4. Add incremental page-level integration behind safe loading/error states.
5. Implement route protection and role checks once auth APIs are available.

This approach keeps the current MVP stable while transitioning from mock data to real system integration.
