# PostgreSQL Docker Setup

## Purpose

This step adds a local PostgreSQL database container for FlowPilot AI using Docker Compose. The database is available for upcoming persistence work, but FastAPI is not connected to PostgreSQL yet.

## Files Created Or Changed

- `docker-compose.yml`
- `.env.example`
- `backend/.env.example`
- `docs/POSTGRES_DOCKER_SETUP.md`
- `backend/README.md`

## Start PostgreSQL

From the project root:

```powershell
docker compose up -d postgres
```

## Check Containers

```powershell
docker ps
```

## View Logs

```powershell
docker logs flowpilot_postgres
```

## Stop PostgreSQL

```powershell
docker compose stop postgres
```

## Remove Container But Keep Volume

```powershell
docker compose down
```

## Remove Data Volume Only If Needed

Warning: this deletes the PostgreSQL data volume.

```powershell
docker compose down -v
```

## Connection Details

- Host: `localhost`
- Port: `5432`
- Database: `flowpilot_db`
- User: `flowpilot_user`
- Password: `flowpilot_password`
- SQLAlchemy-style URL: `postgresql+psycopg://flowpilot_user:flowpilot_password@localhost:5432/flowpilot_db`

## Production Warning

Do not use these default credentials in production. They are intended only for local development.

## Not Implemented Yet

- FastAPI database connection
- SQLAlchemy models
- Alembic migrations
- Real persistence
- Authentication and RBAC
- n8n integration
