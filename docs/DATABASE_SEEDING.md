# Database Seeding

## Purpose

Step 50 adds a simple idempotent seed script for initial FlowPilot AI database data. The API still uses mock services; seeded data is prepared for later persistence integration.

## Seeded Tables

- `roles`
- `role_permissions`
- `users`
- `leave_requests`
- `crm_leads`
- `workflow_executions`
- `agent_runs`

## Seeded Roles

- `role_admin`
- `role_manager`
- `role_employee`
- `role_crm_manager`

## Seeded Role Permissions

- `role_admin` - dashboard, leave, CRM, agents, workflow, users, and roles permissions
- `role_manager` - dashboard, leave approval, leave rejection, and workflow read permissions
- `role_employee` - dashboard, leave read, and leave create permissions
- `role_crm_manager` - dashboard, CRM, agents, and workflow permissions

## Seeded Users

- `user_001` - Admin User
- `user_010` - Sarah N.
- `user_020` - Manager User
- `user_030` - CRM Manager

## Seeded Sample Leave Requests

- `leave_001` - Annual Leave, pending
- `leave_002` - Sick Leave, approved

## Seeded CRM Leads

- `lead_001` - Northwind Logistics, hot
- `lead_002` - Atlas Retail, warm
- `lead_003` - Medina Services, cold

## Seeded Workflow Executions

- `exec_001` - Leave Request Approval Flow, success
- `exec_002` - CRM Lead Scoring Flow, failed
- `exec_003` - Agent Manual Run Flow, queued

## Seeded Agent Runs

- `run_001` - Lead Scoring Agent, failed
- `run_002` - Leave Validation Agent, success
- `run_003` - Lead Scoring Agent, queued

## Required Order

1. Start PostgreSQL from the project root:

   ```powershell
   docker compose up -d postgres
   ```

2. Move into the backend folder:

   ```powershell
   cd backend
   ```

3. Create the tables:

   ```powershell
   python scripts/create_tables.py
   ```

4. Seed the initial data:

   ```powershell
   python scripts/seed_database.py
   ```

Expected output:

```text
Database seeded successfully.
```

## Verify With psql

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Then run:

```sql
SELECT * FROM roles;
SELECT * FROM users;
SELECT * FROM role_permissions;
SELECT * FROM leave_requests;
SELECT * FROM crm_leads;
SELECT * FROM workflow_executions;
SELECT * FROM agent_runs;
```

## Not Implemented Yet

- Mock service replacement
- Frontend changes
- Authentication
- Real RBAC enforcement
- n8n integration
