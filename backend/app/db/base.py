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


# Import mọi model đã hiện thực để Alembic autogenerate nhìn thấy bảng mới.
# Đặt SAU khi Base/TimestampMixin đã định nghĩa xong ở trên — model/*.py tự
# import ngược lại "from app.db.base import Base" (import vòng), Python xử lý
# được vì lúc models/*.py chạy tới dòng đó, module app.db.base đã có sẵn
# Base/TimestampMixin trong namespace (dù chưa chạy hết file) — đã verify
# thật bằng cách import module + gọi Base.metadata.create_all().
#
# Nhóm A/B/C (TASK-005a, 2026-08-28):
from app.models.employee import AIEmployee, Schedule  # noqa: E402,F401
from app.models.user import Role, User, user_roles  # noqa: E402,F401
from app.models.workflow import Tool, Workflow, WorkflowEdge, WorkflowStep  # noqa: E402,F401

# NOTE: app/models/run.py, extraction.py, artifact.py, audit.py VẪN LÀ STUB
# tại thời điểm sửa file này (TASK-005a, 2026-08-28) — chưa có class SQLAlchemy
# nào để import. Khi TASK-005b hiện thực xong, thêm import tương tự ở đây.
# Thiếu bước này, Alembic autogenerate sẽ không thấy bảng mới.
