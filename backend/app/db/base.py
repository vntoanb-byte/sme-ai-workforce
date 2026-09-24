"""
Lớp cơ sở của mô hình dữ liệu

Khai báo DeclarativeBase và import mọi model để Alembic autogenerate nhìn
thấy.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# Nạp mọi model để Base.metadata đầy đủ bảng (Alembic autogenerate, create_all).
# Đặt SAU khi Base/TimestampMixin đã định nghĩa. Danh sách model nằm ở
# app/models/__init__.py — nhờ vậy import MỘT model bất kỳ trước (vd.
# `from app.models.user import User`) cũng nạp trọn gói mà không vỡ import vòng
# (lỗi thật đã gặp: import app.models.user trước app.db.base → ImportError).
import app.models  # noqa: E402,F401
