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


# Import mọi model đã hiện thực để Alembic autogenerate nhìn thấy bảng mới.
# Đặt SAU khi Base/TimestampMixin đã định nghĩa xong ở trên — model/*.py tự
# import ngược lại "from app.db.base import Base" (import vòng), Python xử lý
# được vì lúc models/*.py chạy tới dòng đó, module app.db.base đã có sẵn
# Base/TimestampMixin trong namespace (dù chưa chạy hết file) — đã verify
# thật bằng cách import module + gọi Base.metadata.create_all().
#
# Nhóm A/B/C (TASK-005a, 2026-08-28) + Nhóm D-G (TASK-005b, 2026-08-29):
from app.models.artifact import Artifact, Document  # noqa: E402,F401
from app.models.audit import AuditLog, LlmCall, Setting  # noqa: E402,F401
from app.models.employee import AIEmployee, Schedule  # noqa: E402,F401
from app.models.extraction import Extraction, HumanReview, QCResult  # noqa: E402,F401
from app.models.run import JobQueueEntry, Run, RunLog, RunStep  # noqa: E402,F401
from app.models.user import Role, User, user_roles  # noqa: E402,F401
from app.models.workflow import Tool, Workflow, WorkflowEdge, WorkflowStep  # noqa: E402,F401
