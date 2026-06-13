from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "FlowPilot AI Backend"
    API_PREFIX: str = "/api"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    ENV: str = "development"
    N8N_WEBHOOK_BASE_URL: str = "http://localhost:5678/webhook"
    LEAVE_N8N_WEBHOOK_BASE_URL: str = "http://host.docker.internal:5678/webhook"
    LEAVE_BALANCE_PRECHECK_WEBHOOK_URL: str = (
        "http://localhost:5678/webhook/flowpilot/leave/balance-precheck"
    )
    FLOWPILOT_N8N_SHARED_SECRET: str = "flowpilot-test-secret"
    FLOWPILOT_API_BASE_URL_FOR_N8N: str = "http://host.docker.internal:8000"
    JWT_SECRET_KEY: str = "flowpilot-local-dev-jwt-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ODOO_BASE_URL: str = "http://host.docker.internal:8069"
    ODOO_DB: str = "flowpilot_odoo"
    ODOO_UID: int = 2
    ODOO_PASSWORD: str = "123456789"
    DATABASE_URL: str = (
        "postgresql+psycopg://flowpilot_user:flowpilot_password"
        "@localhost:5432/flowpilot_db"
    )
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "mistralai/mistral-small-3.2-24b-instruct"
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_MAX_TOKENS: int = 800
    OPENUI_ENABLED: bool = False
    OPENUI_MODEL: str = ""
    OPENUI_TIMEOUT_SECONDS: float = 30.0
    OPENUI_MAX_TABLE_ROWS: int = 20


settings = Settings()
