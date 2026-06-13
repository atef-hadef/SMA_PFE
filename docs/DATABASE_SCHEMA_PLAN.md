# FlowPilot AI Database Schema Plan

Date: 2026-04-28  
Status: Planning only, no database code implemented

## 1. Purpose of the database schema
The database schema will provide the durable system of record for FlowPilot AI. It will store the core business entities needed to run the MVP, support secure access control, and keep workflow and automation data consistent across the backend, frontend, and future integrations.

The schema should be designed to support:
- operational business data
- role-based access control
- leave request processing
- CRM lead tracking
- workflow execution tracking
- AI agent run history
- future audit and notification capabilities

## 2. Why PostgreSQL is recommended
PostgreSQL is the recommended database for FlowPilot AI because it fits the project’s expected growth and data shape.

Key reasons:
- Strong support for relational data and foreign keys
- Reliable transaction handling for business workflows
- Good fit for structured operational records such as users, roles, requests, and executions
- Mature indexing and query performance for dashboard and reporting use cases
- Flexible enough for later extensions such as JSON metadata, audit logging, and workflow payloads
- Widely supported by FastAPI, SQLAlchemy, and common Python tooling
- Production-grade stability and ecosystem maturity

## 3. Database scope for MVP
The first database version should only cover the minimum entities required to replace the current mock-driven core flows.

In scope for MVP:
- users and access control
- leave request storage
- CRM lead storage
- workflow execution tracking
- AI agent run tracking
- basic status history needed by the UI and backend services

Out of scope for the first version:
- full authentication implementation
- n8n secret storage
- advanced analytics warehouse design
- document storage or file attachments
- multi-tenant architecture
- complex auditing beyond basic timestamps

## 4. Tables for first version
The first schema version should include these core tables:
- users
- roles
- role_permissions
- leave_requests
- crm_leads
- workflow_executions
- agent_runs

## 5. Optional tables for later
These tables are recommended for later phases, after the MVP schema is stable:
- audit_logs
- notifications
- crm_interactions
- workflow_steps

## 6. Core table definitions

### 6.1 users
Purpose: Store application users who can log in, submit leave requests, manage CRM activity, or operate as admins and approvers.

Main columns:
- id
- full_name
- email
- password_hash or authentication reference
- role_id
- status
- job_title
- department
- last_login_at
- created_at
- updated_at

Primary key:
- id

Foreign keys:
- role_id -> roles.id

Important status fields:
- status: active, inactive

Timestamp fields:
- created_at
- updated_at

### 6.2 roles
Purpose: Define application roles such as employee, manager, admin, or custom future roles.

Main columns:
- id
- name
- description
- is_system_role
- created_at
- updated_at

Primary key:
- id

Foreign keys:
- none required for the first version

Important status fields:
- is_system_role can be used to protect built-in roles from accidental deletion

Timestamp fields:
- created_at
- updated_at

### 6.3 role_permissions
Purpose: Store the permissions assigned to each role for access control and admin management.

Main columns:
- id
- role_id
- permission_code
- created_at
- updated_at

Primary key:
- id

Foreign keys:
- role_id -> roles.id

Important status fields:
- no dedicated status field is required in the first version
- permission_code should store values such as dashboard.read, leave.create, leave.approve, crm.read, crm.manage, agents.run, workflow.retry, admin.users.manage, and admin.roles.manage

Timestamp fields:
- created_at
- updated_at

### 6.4 leave_requests
Purpose: Store employee leave requests and their approval lifecycle.

Main columns:
- id
- user_id
- leave_type
- start_date
- end_date
- reason
- status
- reviewed_by
- reviewed_at
- decision_comment
- created_at
- updated_at

Primary key:
- id

Foreign keys:
- user_id -> users.id
- reviewed_by -> users.id

Important status fields:
- status: pending, approved, rejected

Timestamp fields:
- created_at
- updated_at

### 6.5 crm_leads
Purpose: Store CRM leads managed by the platform and displayed in the CRM modules.

Main columns:
- id
- full_name
- company_name
- email
- phone
- source
- lead_score
- status
- sentiment
- urgency
- intention
- message
- ai_summary
- recommended_action
- owner_user_id
- assigned_to
- notes
- created_at
- updated_at

Primary key:
- id

Foreign keys:
- owner_user_id -> users.id
- assigned_to -> users.id

Important status fields:
- status: new, hot, warm, cold, qualified, archived

Timestamp fields:
- created_at
- updated_at

### 6.6 workflow_executions
Purpose: Track workflow runs triggered from CRM, leave processing, monitoring, agent activity, or manual actions.

Main columns:
- id
- related_object_type
- related_object_id
- workflow_name
- trigger_source
- status
- started_at
- finished_at
- error_message
- result_summary
- created_at
- updated_at

Primary key:
- id

Foreign keys:
- related_object_id can point to different business objects depending on related_object_type; crm_lead_id should remain optional only if introduced later for a specific use case

Important status fields:
- status: success, failed, running, queued

Timestamp fields:
- created_at
- updated_at

### 6.7 agent_runs
Purpose: Store execution records for AI agents invoked during automation or analysis workflows.

Main columns:
- id
- agent_id
- workflow_execution_id
- process
- requested_by
- requested_at
- agent_name
- input_summary
- output_summary
- status
- started_at
- finished_at
- error_message
- created_at
- updated_at

Primary key:
- id

Foreign keys:
- workflow_execution_id -> workflow_executions.id, optional
- requested_by -> users.id
- agent_id is a logical reference to the configured agent identity and does not require a foreign key in the first MVP document

Important status fields:
- status: queued, running, success, failed

Timestamp fields:
- created_at
- updated_at

## 7. Relationships
The first version should keep relationships simple and explicit.

- users -> roles
  - Each user belongs to one role in the MVP schema.
  - This supports role-based UI behavior and admin permissions.

- roles -> role_permissions
  - Each role can have multiple permissions.
  - This supports a flexible permission model without hardcoding access rules in the frontend.

- users -> leave_requests
  - Each leave request is created by one user.
  - A reviewer can also be stored as a user reference.

- crm_leads -> workflow_executions
  - Each CRM lead can produce one or more workflow executions.
  - This keeps automation traceability attached to the lead.

- workflow_executions -> agent_runs
  - Each workflow execution can contain one or more agent runs.
  - This provides traceability for AI-assisted actions.

## 8. Recommended status values
The schema should standardize status values early so the frontend and backend stay aligned.

- Leave request status: pending, approved, rejected
- CRM lead status: new, hot, warm, cold, qualified, archived
- Workflow execution status: success, failed, running, queued
- Agent run status: queued, running, success, failed
- User status: active, inactive

## 9. Mock data to be replaced by PostgreSQL
The following mock-driven areas should eventually read from PostgreSQL instead of static frontend or backend mock data:
- dashboard summary
- leave requests
- pending approvals
- CRM leads
- workflow executions
- agent runs
- users
- roles and permissions

This replacement should happen progressively so the application can move from mocked state to persisted state without a full rewrite.

## 10. What should not be stored yet
The first database version should avoid storing data that is not required for the MVP.

Do not store yet:
- raw n8n secrets
- frontend-only UI state
- sensitive tokens in plain text

If credentials or secrets are needed later, they should be managed through secure environment variables or a secrets manager, not plain database columns.

## 11. Implementation order
The recommended implementation order is:

- Step 47: Add PostgreSQL with Docker
- Step 48: Connect FastAPI to PostgreSQL
- Step 49: Create SQLAlchemy models
- Step 50: Persist users, roles, leave requests, CRM leads
- Step 51: Replace mock services progressively

This order keeps the work small, testable, and aligned with the current mock-based backend.

## 12. Final recommendation
Start with a small database slice first:
- users
- roles
- role_permissions
- leave_requests

This slice gives the project an immediate foundation for access control and leave management while keeping implementation risk low. Once that slice is stable, the schema can expand to CRM, workflow execution, and agent run persistence.
