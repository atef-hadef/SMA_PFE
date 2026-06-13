# Leave PostgreSQL Persistence

## Purpose

Step 51 replaces the Leave Request and Manager Approval mock backend logic with PostgreSQL-backed service logic. The frontend routes and response shapes stay the same, so the existing Leave Request and Manager Approval pages continue to work without frontend changes.

## Endpoints Changed

- `POST /api/leave-requests`
- `GET /api/leave-requests/pending`
- `POST /api/leave-requests/{request_id}/approve`
- `POST /api/leave-requests/{request_id}/reject`

## Tables Used

- `leave_requests`
- `users`

## Default Users Before Real Auth

Real authentication is not implemented yet, so the backend uses fixed seeded users:

- `user_010` as the employee submitting leave requests
- `user_020` as the manager/reviewer for approve and reject decisions

## How To Test From Frontend

1. Start PostgreSQL:

   ```powershell
   docker compose up -d postgres
   ```

2. Make sure tables and seed data exist:

   ```powershell
   cd backend
   python scripts/create_tables.py
   python scripts/seed_database.py
   ```

3. Start FastAPI:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

4. Open the frontend Leave Request page and submit a leave request.

5. Open the Manager Approval page and confirm the submitted request appears in the pending approval list.

6. Approve or reject a pending request and confirm the UI shows the decision success message.

## How To Verify With psql

Open psql:

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Check submitted and pending requests:

```sql
SELECT id, user_id, leave_type, start_date, end_date, status, created_at
FROM leave_requests
ORDER BY created_at DESC;
```

Check approved or rejected decisions:

```sql
SELECT id, status, reviewed_by, reviewed_at, decision_comment, updated_at
FROM leave_requests
WHERE status IN ('approved', 'rejected')
ORDER BY updated_at DESC;
```

## What Remains Mock-Only

- AI recommendation
- Risk level
- Conflict detection
- Authentication and real current-user handling
- Real RBAC enforcement
- n8n integration
- Dashboard persistence
- CRM persistence
- Workflow persistence
- AI Agent persistence
- Admin Users and Roles persistence
