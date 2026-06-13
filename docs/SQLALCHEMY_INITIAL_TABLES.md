# SQLAlchemy Initial Tables

## Purpose

Step 49 adds the first SQLAlchemy ORM models and a simple manual table creation script for MVP development. Existing mock API services are not replaced yet.

## Tables Created

- `users`
- `roles`
- `role_permissions`
- `leave_requests`

## Make Sure PostgreSQL Is Running

From the project root:

```powershell
docker compose up -d postgres
```

## Create Tables

From the `backend` folder:

```powershell
python scripts/create_tables.py
```

Expected output:

```text
Database tables created successfully.
```

## Verify Tables With psql

```powershell
docker exec -it flowpilot_postgres psql -U flowpilot_user -d flowpilot_db
```

Then run:

```sql
\dt
```

You should see:

- `users`
- `roles`
- `role_permissions`
- `leave_requests`

## Not Implemented Yet

- Mock service replacement
- Seed data
- Authentication
- RBAC enforcement
- Alembic migrations
- n8n integration
