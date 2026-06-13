from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    agents,
    assistant,
    auth,
    crm,
    crm_deals,
    crm_tasks,
    dashboard,
    db_health,
    health,
    leave_requests,
    n8n_callbacks,
    workflow_monitoring,
)
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

# Allow the main React frontend + the local test-form.html helper served via
# `python -m http.server 8080`. Add new origins here as deployments require.
ALLOWED_ORIGINS = [
    settings.FRONTEND_ORIGIN,
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(assistant.router, prefix=settings.API_PREFIX)
app.include_router(db_health.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(leave_requests.router, prefix=settings.API_PREFIX)
app.include_router(crm.router, prefix=settings.API_PREFIX)
app.include_router(crm_tasks.router, prefix=settings.API_PREFIX)
app.include_router(crm_deals.router, prefix=settings.API_PREFIX)
app.include_router(workflow_monitoring.router, prefix=settings.API_PREFIX)
app.include_router(agents.router, prefix=settings.API_PREFIX)
app.include_router(admin.router, prefix=settings.API_PREFIX)
app.include_router(n8n_callbacks.router, prefix=f"{settings.API_PREFIX}/n8n")
