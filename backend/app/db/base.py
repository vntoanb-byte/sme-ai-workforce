"""
Lớp cơ sở của mô hình dữ liệu

Khai báo DeclarativeBase và import mọi model để Alembic autogenerate nhìn
thấy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# NOTE: app/models/*.py (user, employee, workflow, run, extraction, artifact,
# audit) VẪN LÀ STUB tại thời điểm viết file này (2026-08-27) — chưa có class
# SQLAlchemy nào để import. Khi từng model được hiện thực, import nó ở đây,
# ví dụ:
#   from app.models.user import User  # noqa: F401
# Thiếu bước này, Alembic autogenerate sẽ không thấy bảng mới.
