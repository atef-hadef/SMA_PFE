from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class AuthUser(BaseModel):
    id: str
    full_name: str
    email: str
    role_id: str
    role_name: str
    permissions: list[str]
    status: str
    job_title: str | None = None
    department: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class LogoutResponse(BaseModel):
    message: str
