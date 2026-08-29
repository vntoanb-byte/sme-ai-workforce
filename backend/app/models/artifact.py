"""
Mô hình tệp và tài liệu

Định nghĩa bảng: artifacts, documents (NHÓM F — TASK-005b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.extraction import Extraction, HumanReview
    from app.models.user import User


class Artifact(Base, TimestampMixin):
    """Một tệp vật lý trong kho (artifacts) — khớp ArtifactRef (ports/storage.py)."""

    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str | None] = mapped_column(String(100))

    # MỘT CHIỀU + viewonly: chỉ-đọc danh sách document của artifact; KHÔNG cascade
    # xoá document khi artifact bị xoá (FileStorage.delete() là thao tác vật lý
    # riêng) và KHÔNG back_populates với Document.artifact (cùng cột FK
    # documents.artifact_id — tránh SAWarning "copy column" khi flush).
    documents: Mapped[list[Document]] = relationship(
        foreign_keys="[Document.artifact_id]",
        viewonly=True,
    )


class Document(Base, TimestampMixin):
    """Một chứng từ đã nạp (documents).

    NOTE (TASK-005b, cần Owner xác nhận): KHÔNG lưu invoice_no/issue_date/
    seller_name/total/qc_failed trên documents dù DocumentRow (frontend) có các
    trường này — áp dụng ĐÚNG tiền lệ AIEmployee (TASK-005a): đây là giá trị JOIN
    với Extraction mới nhất theo document_id + đếm qc_results.passed=False,
    services/document_service.py tự JOIN khi trả DocumentRow. (NGƯỢC với NOTE ở
    Extraction — 2 quyết định khác nhau, đừng nhầm lẫn khi review.)
    """

    __tablename__ = "documents"
    __table_args__ = (
        # Lọc nhanh theo trạng thái: GET /documents?status=...
        Index("ix_documents_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # RESTRICT: không cho xoá artifact còn document tham chiếu.
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    filename: Mapped[str] = mapped_column(String(255))
    # image|pdf
    source_kind: Mapped[str] = mapped_column(String(10))
    # processing|ok|needs_review|rejected|failed — khớp frontend DocStatus.
    status: Mapped[str] = mapped_column(String(20), default="processing")
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    artifact: Mapped[Artifact] = relationship(foreign_keys=[artifact_id])
    # MỘT CHIỀU — User không cần danh sách document đã upload.
    uploaded_by_user: Mapped[User | None] = relationship(foreign_keys=[uploaded_by])
    extractions: Mapped[list[Extraction]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Extraction.created_at",
    )
    human_reviews: Mapped[list[HumanReview]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
