"""
Mô hình kết quả trích xuất và kiểm soát chất lượng

Định nghĩa bảng: extractions, qc_results, human_reviews (NHÓM E — TASK-005b).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.artifact import Document
    from app.models.run import Run
    from app.models.user import User


class Extraction(Base, TimestampMixin):
    """Kết quả trích xuất hoá đơn từ một chứng từ (extractions).

    NOTE (TASK-005b, cần Owner xác nhận): các cột invoice_no/issue_date/
    seller_name/seller_tax_code/subtotal/vat_rate/vat_amount/total là bản SAO CHÉP
    có chủ đích từ extracted_data_json — KHÁC quyết định "không denormalize" ở
    AIEmployee/Document: đây là giá trị GỐC cần filter/sort/unique-check trực tiếp
    bằng SQL (QC-06, lọc theo ngày/nhà cung cấp), không phải giá trị tính qua JOIN.
    """

    __tablename__ = "extractions"
    __table_args__ = (
        # QC-06 existing_invoice_numbers + lọc danh sách theo số hoá đơn.
        Index("ix_extractions_invoice_no", "invoice_no"),
        # Lọc theo khoảng ngày lập hoá đơn.
        Index("ix_extractions_issue_date", "issue_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    # NULL nếu trích xuất qua upload trực tiếp, không qua workflow/run.
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL")
    )
    schema_version: Mapped[str] = mapped_column(String(20))
    model_name: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    latency_ms: Mapped[int] = mapped_column()
    invoice_no: Mapped[str | None] = mapped_column(String(50))
    issue_date: Mapped[date | None] = mapped_column(Date)
    seller_name: Mapped[str | None] = mapped_column(String(200))
    seller_tax_code: Mapped[str | None] = mapped_column(String(20))
    currency: Mapped[str | None] = mapped_column(String(10))
    # Decimal — KHÔNG BAO GIỜ float (quy tắc kiến trúc bắt buộc).
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    # Toàn bộ InvoiceData (kể cả line_items[]) — đọc/ghi json ở tầng service.
    extracted_data_json: Mapped[str] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="extractions")
    # MỘT CHIỀU — Run không cần danh sách extractions.
    run: Mapped[Run | None] = relationship(foreign_keys=[run_id])
    qc_results: Mapped[list[QCResult]] = relationship(
        back_populates="extraction",
        cascade="all, delete-orphan",
    )
    # MỘT CHIỀU + viewonly: chỉ-đọc, độc lập với HumanReview.extraction (cùng cột
    # FK human_reviews.extraction_id) — không back_populates để tránh SAWarning
    # "copy column" khi flush.
    human_reviews: Mapped[list[HumanReview]] = relationship(
        foreign_keys="[HumanReview.extraction_id]",
        viewonly=True,
    )


class QCResult(Base, TimestampMixin):
    """Kết quả một quy tắc QC cho một extraction (qc_results)."""

    __tablename__ = "qc_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    extraction_id: Mapped[int] = mapped_column(
        ForeignKey("extractions.id", ondelete="CASCADE")
    )
    # QC-01..QC-08 — khớp domain/qc_rules.py.
    rule_code: Mapped[str] = mapped_column(String(10))
    # warning|critical
    severity: Mapped[str] = mapped_column(String(10))
    passed: Mapped[bool] = mapped_column()
    field: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)

    extraction: Mapped[Extraction] = relationship(back_populates="qc_results")


class HumanReview(Base, TimestampMixin):
    """Quyết định xác nhận thủ công một chứng từ (human_reviews)."""

    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    # SET NULL: xoá Extraction thì review vẫn giữ, extraction_id chuyển NULL.
    extraction_id: Mapped[int | None] = mapped_column(
        ForeignKey("extractions.id", ondelete="SET NULL")
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # approve|correct|reject — khớp POST /reviews/{id}/resolve.
    action: Mapped[str] = mapped_column(String(10))
    # Chỉ có giá trị khi action='correct'.
    corrected_data_json: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="human_reviews")
    # MỘT CHIỀU (xem Extraction.human_reviews).
    extraction: Mapped[Extraction | None] = relationship(foreign_keys=[extraction_id])
    # MỘT CHIỀU — User không cần danh sách review.
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])
