"""
Mô hình người dùng và phân quyền

Định nghĩa bảng: users, roles, user_roles (NHÓM A — TASK-005a).
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, PrimaryKeyConstraint, String, Table
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
