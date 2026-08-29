"""
Mô hình thực thi và hàng đợi

Định nghĩa bảng: runs, run_steps, run_logs, job_queue (NHÓM D — TASK-005b).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.employee import AIEmployee
    from app.models.user import User
    from app.models.workflow import Workflow


class Run(Base, TimestampMixin):
    """Một lần chạy một bản workflow cụ thể (runs).

    NOTE (TASK-005b, cần Owner xác nhận): KHÔNG có cột doc_count/stats — đúng
    tiền lệ AIEmployee (TASK-005a): đây là giá trị JOIN/tính toán ở service
    layer, không lưu ở models/.
    """

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("ai_employees.id", ondelete="CASCADE")
    )
    # Bản workflow đã chạy — RESTRICT: run là dấu vết lịch sử, không cho xoá
    # workflow còn run tham chiếu.
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="RESTRICT")
    )
    # manual|cron|file_watch
    trigger_type: Mapped[str] = mapped_column(String(20))
    # Chữ THƯỜNG, khớp domain/state.py RunStatus
    # (pending|claimed|running|retrying|needs_review|succeeded|failed|cancelled).
    # Frontend RunStatus dùng chữ HOA — tầng API schema chuyển sang HOA khi trả
    # về, KHÔNG phải việc của models/.
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    # NULL nếu do cron/file_watch kích hoạt (không có user).
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # Các quan hệ MỘT CHIỀU — employee/workflow/user KHÔNG có back_populates
    # (không sửa models/user.py, employee.py, workflow.py của TASK-005a).
    employee: Mapped[AIEmployee] = relationship(foreign_keys=[employee_id])
    workflow: Mapped[Workflow] = relationship(foreign_keys=[workflow_id])
    created_by_user: Mapped[User | None] = relationship(foreign_keys=[created_by])

    steps: Mapped[list[RunStep]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunStep.order_index",
    )
    logs: Mapped[list[RunLog]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunLog.created_at",
    )
    job_queue_entries: Mapped[list[JobQueueEntry]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
class RunStep(Base, TimestampMixin):
    """Một bước xử lý trong run (run_steps).

    step_key là bản snapshot từ workflow_steps.step_key lúc run bắt đầu —
    KHÔNG FK tới workflow_steps vì workflow có thể đổi version sau khi run
    đã tạo.
    """

    __tablename__ = "run_steps"
    __table_args__ = (
        # Mỗi run chỉ có 1 bước với cùng step_key (snapshot).
        UniqueConstraint(
            "run_id", "step_key", name="uq_run_steps_run_step_key"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE")
    )
    step_key: Mapped[str] = mapped_column(String(32))
    order_index: Mapped[int] = mapped_column()
    label: Mapped[str] = mapped_column(String(200))
    # Chữ HOA, khớp StepStatus frontend
    # (PENDING|RUNNING|SUCCEEDED|FAILED|SKIPPED) — không có domain enum riêng.
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    detail: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column()

    run: Mapped[Run] = relationship(back_populates="steps")


class RunLog(Base, TimestampMixin):
    """Một dòng nhật ký của run (run_logs).

    NOTE (TASK-005b, cần Owner xác nhận): 1 bảng run_logs phục vụ CẢ (1) log
    transition từ domain/state.py (from_status/to_status, message=reason) lẫn
    (2) log tiến trình chung cho GET /runs/{id}/logs (SSE) stream — suy luận
    hợp nhất 2 nhu cầu vì docstring gốc chỉ liệt kê 1 bảng run_logs, không
    tách 2.
    """

    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE")
    )
    # DEBUG|INFO|WARN|ERROR — khớp frontend LogLine.level.
    level: Mapped[str] = mapped_column(String(10), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    # Chỉ có giá trị khi dòng này ghi lại 1 transition (message = reason của
    # domain/state.py transition()).
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))

    run: Mapped[Run] = relationship(back_populates="logs")


class JobQueueEntry(Base):
    """Một mục hàng đợi (job_queue) — worker claim theo ADR-001.

    CHỈ kế thừa Base, KHÔNG kế thừa TimestampMixin: SQL gốc trong
    adapters/queue_sqlite.py không có cột updated_at, và
    created_at/available_at/lease_until đều là TEXT ISO8601 chứ không phải
    DateTime như TimestampMixin tạo ra. Model này chỉ để Alembic autogenerate
    nhìn thấy đúng bảng — file adapters/queue_sqlite.py tiếp tục dùng SQL thô
    (ngoài phạm vi TASK-005b).
    """

    __tablename__ = "job_queue"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE")
    )
    # pending|claimed|failed|succeeded
    status: Mapped[str] = mapped_column(String(10), default="pending")
    priority: Mapped[int] = mapped_column(default=0)
    # TEXT ISO8601 UTC (vd 2026-08-28T10:00:00.000000Z) — KHÔNG dùng DateTime,
    # khớp CHÍNH XÁC adapters/queue_sqlite.py (định dạng _fmt()).
    available_at: Mapped[str] = mapped_column(String(32))
    claimed_by: Mapped[str | None] = mapped_column(String(100))
    lease_until: Mapped[str | None] = mapped_column(String(32))
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32))

    run: Mapped[Run] = relationship(back_populates="job_queue_entries")
