"""
DTO chứng từ, xác nhận thủ công và báo cáo

ExtractionPatch (sửa tay), ReviewResolve, ReviewItemOut, ReviewStats,
ReportRequest/ExportRequest/ReportPreview. (DocumentRow/DocumentDetail do
api/v1/documents.py dựng trực tiếp — xem ghi chú _floatify ở đó.)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money, UtcDateTime


class ExtractionPatch(BaseModel):
    """Bản đã được người dùng sửa (InvoiceData của frontend)."""

    data: dict[str, Any]
    note: str | None = Field(default=None, max_length=2000)


class ReviewResolve(BaseModel):
    action: Literal["approve", "correct", "reject"]
    data: dict[str, Any] | None = None
    note: str | None = Field(default=None, max_length=2000)


class ReviewItemOut(BaseModel):
    id: int
    document_id: int
    filename: str
    run_id: int | None
    invoice_no: str | None
    seller_name: str | None
    total: Money | None
    qc_failed: int
    critical_failed: int
    created_at: UtcDateTime


class ReviewStats(BaseModel):
    pending: int


class ReportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date_from: date = Field(alias="from")
    date_to: date = Field(alias="to")
    group_by: Literal["seller", "month", "vat_rate"] = "seller"


class ExportRequest(ReportRequest):
    format: Literal["xlsx", "pdf"] = "xlsx"


class ReportRowOut(BaseModel):
    group: str
    doc_count: int
    subtotal: Money
    vat_amount: Money
    total: Money


class ReportPreview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date_from: str = Field(serialization_alias="from")
    date_to: str = Field(serialization_alias="to")
    group_by: str
    rows: list[ReportRowOut]
    grand_total: Money


class ExportResult(BaseModel):
    artifact_id: int
    filename: str
    download_url: str
