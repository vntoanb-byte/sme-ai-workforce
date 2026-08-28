"""
Mô hình quy trình

Định nghĩa bảng: workflows, workflow_steps, workflow_edges, tools
(NHÓM C — TASK-005a).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.employee import AIEmployee, Schedule
    from app.models.user import User


class Workflow(Base, TimestampMixin):
    """Một phiên bản quy trình làm việc của nhân viên AI."""

    __tablename__ = "workflows"
    __table_args__ = (
        # Mỗi nhân viên có nhiều phiên bản, số version tăng dần.
        UniqueConstraint(
            "employee_id", "version", name="uq_workflows_employee_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("ai_employees.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column()
    # pending|approved|archived
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # NOTE (TASK-005a, mâu thuẫn CHƯA GIẢI QUYẾT, xem memory.md): frontend types.ts
    # dùng tiền tố 'TPL_INVOICE_TO_EXCEL', schemas/workflow_spec.py dùng
    # 'invoice_to_excel'. Cột này chỉ lưu str(50) TỰ DO, không ràng buộc
    # CHECK/Enum — khi 2 bên thống nhất thì service layer tự xử lý, models/ không
    # được chọn 1 bên (đúng nguyên tắc AGENTS.md: không tự quyết mâu thuẫn).
    template_code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    employee: Mapped[AIEmployee] = relationship(
        back_populates="workflows",
        foreign_keys=[employee_id],
    )
    # MỘT CHIỀU — User không cần danh sách workflow đã duyệt.
    approved_by_user: Mapped[User | None] = relationship(
        foreign_keys=[approved_by]
    )
    # schedules.workflow_id UNIQUE -> quan hệ 1-1. cascade xoá theo đúng
    # ondelete=CASCADE khai báo ở DB.
    schedule: Mapped[Schedule | None] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.order_index",
    )
    # QUAN TRỌNG (điểm kỹ thuật khó nhất TASK-005a): workflow_edges chỉ có FK GHÉP
    # (composite) tới workflow_steps qua (workflow_id, step_key) — KHÔNG có FK trực
    # tiếp tới workflows.id. SQLAlchemy không tự suy được join giữa 2 bảng nên phải
    # khai báo primaryjoin + foreign_keys TƯỜNG MINH cho relationship này.
    edges: Mapped[list[WorkflowEdge]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        primaryjoin="Workflow.id == WorkflowEdge.workflow_id",
        foreign_keys="[WorkflowEdge.workflow_id]",
    )


class WorkflowStep(Base, TimestampMixin):
    """Một bước xử lý trong workflow — step_key duy nhất trong một workflow."""

    __tablename__ = "workflow_steps"
    __table_args__ = (
        # Đích của cả 2 FK ghép trong workflow_edges.
        UniqueConstraint(
            "workflow_id", "step_key", name="uq_workflow_steps_wf_step"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE")
    )
    # Khớp pattern StepKey trong schemas/workflow_spec.py: ^[a-z][a-z0-9_]{1,30}$
    # (tối đa 32 ký tự).
    step_key: Mapped[str] = mapped_column(String(32))
    order_index: Mapped[int] = mapped_column()
    tool_code: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(200))
    # Cột JSON lưu dạng TEXT — đọc/ghi qua json.dumps/loads ở TẦNG SERVICE, models/
    # không nhúng logic (đúng ARCHITECTURE.md).
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    # stop|skip|retry
    on_error: Mapped[str] = mapped_column(String(10), default="stop")
    retry_max: Mapped[int] = mapped_column(default=0)

    workflow: Mapped[Workflow] = relationship(back_populates="steps")


class WorkflowEdge(Base, TimestampMixin):
    """Cạnh nối giữa 2 bước — FK ghép tới workflow_steps (xem NOTE ở Workflow)."""

    __tablename__ = "workflow_edges"
    __table_args__ = (
        # FK GHÉP (composite) tới workflow_steps qua (workflow_id, step_key) —
        # workflow_steps có UniqueConstraint(workflow_id, step_key) làm đích.
        # Cả from_key lẫn to_key đều phải trỏ tới step tồn tại trong CÙNG workflow
        # đó (cùng workflow_id) — nếu lệch, INSERT sẽ fail.
        ForeignKeyConstraint(
            ["workflow_id", "from_key"],
            ["workflow_steps.workflow_id", "workflow_steps.step_key"],
            ondelete="CASCADE",
            name="fk_workflow_edges_from",
        ),
        ForeignKeyConstraint(
            ["workflow_id", "to_key"],
            ["workflow_steps.workflow_id", "workflow_steps.step_key"],
            ondelete="CASCADE",
            name="fk_workflow_edges_to",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Các cột dưới đây thuộc FK ghép — KHÔNG khai báo ForeignKey riêng trong
    # mapped_column, ràng buộc nằm trong ForeignKeyConstraint ở __table_args__.
    workflow_id: Mapped[int] = mapped_column()
    from_key: Mapped[str] = mapped_column(String(32))
    to_key: Mapped[str] = mapped_column(String(32))
    # None = cạnh vô điều kiện; vd. 'success', 'needs_review'.
    condition: Mapped[str | None] = mapped_column(String(50))

    # workflow_id không có ForeignKey đơn (chỉ nằm trong 2 FK ghép ở
    # __table_args__) — SQLAlchemy không tự suy được join, phải khai primaryjoin/
    # foreign_keys tường minh giống hệt chiều Workflow.edges ở trên.
    workflow: Mapped[Workflow] = relationship(
        back_populates="edges",
        primaryjoin="Workflow.id == WorkflowEdge.workflow_id",
        foreign_keys=[workflow_id],
    )


class Tool(Base, TimestampMixin):
    """Danh mục công cụ — đồng bộ tự động từ TOOL_REGISTRY (app/tools/base.py).

    Bảng này do sync_tools_to_db() đồng bộ, KHÔNG phải người dùng nhập tay. models/
    chỉ định nghĩa bảng; việc đồng bộ nằm ở tools/base.py (ngoài phạm vi TASK-005a).
    """

    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # vd. 'fs.list_new_files', 'vision.extract_invoice', 'qc.validate_invoice',
    # 'xlsx.append_rows' (xem frontend mock data).
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(50))
    # JSON schema — kiểu Text, service layer đọc/ghi bằng json.dumps/loads.
    input_schema_json: Mapped[str | None] = mapped_column(Text)
    output_schema_json: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(default=True)

