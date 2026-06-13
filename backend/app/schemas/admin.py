from datetime import datetime
from typing import Literal

from pydantic import BaseModel


UserStatus = Literal["active", "inactive"]


class UserListItem(BaseModel):
    id: str
    name: str
    email: str
    role: str
    department: str
    status: UserStatus
    last_login: datetime | None


class UserCreate(BaseModel):
    name: str
    email: str
    role: str
    department: str
    password: str | None = None
    job_title: str | None = None


class UserCreatedResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    department: str
    status: Literal["active"]
    created_at: datetime


class UserUpdate(BaseModel):
    name: str
    role: str
    department: str
    job_title: str | None = None


class UserUpdatedResponse(BaseModel):
    id: str
    name: str
    role: str
    department: str
    updated_at: datetime


class DeactivateUserRequest(BaseModel):
    reason: str


class DeactivateUserResponse(BaseModel):
    id: str
    status: Literal["inactive"]
    deactivated_at: datetime
    reason: str


class RoleListItem(BaseModel):
    id: str
    name: str
    description: str
    user_count: int
    permissions: list[str]


class UpdateRolePermissionsRequest(BaseModel):
    permissions: list[str]


class RolePermissionsUpdatedResponse(BaseModel):
    id: str
    name: str
    permissions: list[str]
    updated_at: datetime
