from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["admin", "manager", "cashier", "kitchen"]


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: str = Field(..., max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)
    role: UserRole = "cashier"
    is_active: bool = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)
    role: UserRole = "cashier"
    is_active: bool = True


class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User response schema safely omitting sensitive password hashes."""
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    csrf_token: Optional[str] = None
    user: UserResponse
