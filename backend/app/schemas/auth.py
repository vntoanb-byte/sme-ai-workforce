"""
DTO xác thực và người dùng

LoginRequest, RefreshRequest, TokenPair, UserOut, UserCreate, UserUpdate.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import OutModel

RoleCode = Literal["USER", "MANAGER", "ADMIN"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    # Trình duyệt gửi qua cookie HttpOnly; client khác (script) gửi trong body.
    refresh_token: str | None = None


class UserOut(OutModel):
    id: int
    username: str
    full_name: str
    email: str
    roles: list[RoleCode]
    is_active: bool


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


_EMAIL = r"^[^@\s]+@[^@\s]+$"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.\-]+$")
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200, pattern=_EMAIL)
    password: str = Field(min_length=8, max_length=200)
    roles: list[RoleCode] = ["USER"]


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=200, pattern=_EMAIL)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    roles: list[RoleCode] | None = None
    is_active: bool | None = None
