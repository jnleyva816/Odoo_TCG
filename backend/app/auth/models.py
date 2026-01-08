"""Authentication models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """User roles."""

    ADMIN = "admin"
    USER = "user"


class UserBase(BaseModel):
    """Base user model."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    """User creation model."""

    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login model."""

    username: str
    password: str


class User(UserBase):
    """User model returned from API."""

    id: int
    role: UserRole = UserRole.USER
    is_active: bool = True
    warehouse_id: int | None = None  # Current active warehouse
    warehouse_ids: list[int] | None = None  # Allowed warehouses (admins can access multiple)
    created_at: datetime
    last_login: datetime | None = None

    class Config:
        from_attributes = True


class UserInDB(User):
    """User model with hashed password (internal use only)."""

    hashed_password: str


class UserCreateAdmin(UserBase):
    """User creation model for admin endpoint."""

    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.USER
    warehouse_id: int | None = None
    warehouse_ids: list[int] | None = None


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """JWT token payload data."""

    username: str | None = None
    user_id: int | None = None
    role: UserRole = UserRole.USER


class LoginAttempt(BaseModel):
    """Login attempt log."""

    id: int
    username: str
    ip_address: str
    user_agent: str
    success: bool
    timestamp: datetime

