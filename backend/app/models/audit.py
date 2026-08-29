"""
Mô hình nhật ký và cấu hình

Định nghĩa bảng: audit_logs, llm_calls, settings (NHÓM G — TASK-005b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.artifact import Document
    from app.models.run import Run
    from app.models.user import User


class AuditLog(Base, TimestampMixin):
    """Nhật ký kiểm toán (audit_logs) — audit trail, không cho sửa/xoá."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # NULL nếu hệ thống tự ghi (không có user tác động).
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # vd 'document.extraction.correct'.
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str | None] = mapped_column(String(50))
    # KHÔNG FK — đa hình, trỏ nhiều bảng khác nhau tuỳ entity_type.
    entity_id: Mapped[int | None] = mapped_column()
    detail_json: Mapped[str | None] = mapped_column(Text)

    # MỘT CHIỀU, KHÔNG back_populates — User không cần danh sách audit log.
    user: Mapped[User | None] = relationship(foreign_keys=[user_id])


class LlmCall(Base, TimestampMixin):
    """Một lời gọi LLM (llm_calls).

    NOTE (TASK-005b): đây chính là bảng llm_calls mà
    adapters/llm_openai_compatible.py còn thiếu ghi 1 dòng cho mỗi lời gọi —
    task này CHỈ tạo bảng, việc nối adapter ghi vào bảng là task RIÊNG sau (xem
    ARCHITECTURE.md).
    """

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL")
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_tokens: Mapped[int | None] = mapped_column()
    completion_tokens: Mapped[int | None] = mapped_column()
    latency_ms: Mapped[int] = mapped_column()
    # success|error
    status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)

    # MỘT CHIỀU — Run/Document không cần danh sách llm_calls.
    run: Mapped[Run | None] = relationship(foreign_keys=[run_id])
    document: Mapped[Document | None] = relationship(
        foreign_keys=[document_id]
    )


class Setting(Base, TimestampMixin):
    """Cấu hình hệ thống lưu trong DB (settings).

    updated_at có ý nghĩa thật ở bảng này — lần sửa cấu hình gần nhất.
    """

    __tablename__ = "settings"

    # vd 'LLM_BASE_URL_OVERRIDE'.
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
