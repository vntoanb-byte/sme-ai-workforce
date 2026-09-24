"""
Mô hình người dùng và phân quyền

Định nghĩa bảng: users, roles, user_roles (NHÓM A — TASK-005a), refresh_tokens
(migration 0002 — thu hồi phiên khi đăng xuất / xoay vòng refresh token).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, PrimaryKeyConstraint, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

# Bảng nối many-to-many users <-> roles, KHÔNG có id riêng — khoá chính ghép
# (user_id, role_id). TASK-005a chọn Core Table thay vì Association Object vì
# bảng không chứa cột dữ liệu bổ sung — đủ cho relationship(secondary=...)
# trên User.roles / Role.users.
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "role_id",
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    ),
    PrimaryKeyConstraint("user_id", "role_id"),
)


class User(Base, TimestampMixin):
    """Người dùng hệ thống — mật khẩu luôn lưu dạng argon2 hash, KHÔNG plaintext."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
    )


class Role(Base, TimestampMixin):
    """Vai trò — lưu dạng bảng thay vì Enum cột để thêm role mới không cần migration."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 'USER' | 'MANAGER' | 'ADMIN' (khớp frontend RoleCode).
    code: Mapped[str] = mapped_column(String(20), unique=True)

    users: Mapped[list[User]] = relationship(
        secondary=user_roles,
        back_populates="roles",
    )


class RefreshToken(Base, TimestampMixin):
    """Refresh token đã cấp — chỉ lưu jti (không lưu token), để thu hồi được.

    Token hợp lệ khi: có bản ghi, revoked_at IS NULL và chưa quá expires_at.
    Mỗi lần /auth/refresh thu hồi token cũ và cấp token mới (xoay vòng).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
