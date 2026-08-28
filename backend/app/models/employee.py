"""
Mô hình nhân viên AI và lịch chạy

Định nghĩa bảng: ai_employees, schedules (NHÓM B — TASK-005a).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workflow import Workflow


class AIEmployee(Base, TimestampMixin):
    """Nhân viên AI — công việc được mô tả bằng tiếng Việt tự nhiên, đầu vào compiler.

    NOTE (TASK-005a, cần Owner xác nhận): KHÔNG có cột next_run_at / last_run_at /
    last_run_status / runs_30d — các giá trị này trong frontend Employee type là TÍNH
    TOÁN ở service layer (join schedules + runs), không lưu trực tiếp. Nếu sau này cần
    denormalize vì hiệu năng thì mở task riêng bằng migration Alembic mới.
    """

    __tablename__ = "ai_employees"
    __table_args__ = (
        # Lọc nhanh theo trạng thái: GET /employees?status=...
        Index("ix_ai_employees_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    # Mô tả tiếng Việt gốc người dùng gõ, đầu vào cho workflow compiler.
    job_description: Mapped[str] = mapped_column(Text)
    # draft|active|paused|archived
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # Workflow approved mới nhất của nhân viên; NULL nếu chưa duyệt workflow nào.
    # FK tới bảng workflows dùng CHUỖI (không import module workflow) để tránh
    # vòng import employee.py <-> workflow.py.
    current_workflow_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL")
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # Mọi workflow thuộc nhân viên này (workflows.employee_id).
    # NOTE: cố ý KHÔNG cascade="all, delete-orphan" — theo PROJECT.md nhân viên chỉ
    # được archived, không xoá cứng; DB vẫn khai báo ondelete=CASCADE trên cột
    # employee_id cho trường hợp admin dọn dữ liệu qua SQL trực tiếp.
    workflows: Mapped[list[Workflow]] = relationship(
        back_populates="employee",
        foreign_keys="[Workflow.employee_id]",
        order_by="Workflow.version",
    )
    # QUAN HỆ MỘT CHIỀU — không có back_populates phía Workflow: đây không phải quan
    # hệ 1-nhiều chuẩn mà chỉ là con trỏ tới workflow hiện hành, Workflow không cần
    # biết ai đang trỏ vào mình qua current_workflow_id.
    current_workflow: Mapped[Workflow | None] = relationship(
        foreign_keys=[current_workflow_id]
    )
    # MỘT CHIỀU — User không cần danh sách nhân viên mình đã tạo.
    created_by_user: Mapped[User | None] = relationship(foreign_keys=[created_by])


class Schedule(Base, TimestampMixin):
    """Lịch chạy của workflow.

    NOTE (TASK-005a, cần Owner xác nhận): mỗi workflow chỉ có 1 lịch
    (workflow_id UNIQUE) — đơn giản hoá, bản này CHƯA hỗ trợ nhiều lịch/1 workflow.
    """

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), unique=True
    )
    # manual|cron|file_watch — copy từ WorkflowSpec.trigger.type lúc duyệt.
    trigger_type: Mapped[str] = mapped_column(String(20))
    cron_expr: Mapped[str | None] = mapped_column(String(100))
    watch_path: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str | None] = mapped_column(String(50))
    # Worker/scheduler cập nhật mỗi khi đã xử lý xong một lượt chạy (giờ VN).
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(default=True)

    workflow: Mapped[Workflow] = relationship(back_populates="schedule")
