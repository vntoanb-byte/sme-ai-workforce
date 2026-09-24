"""
DTO dùng chung

Page[T] phân trang, ErrorResponse, IdResponse và hai kiểu biên API:
  - UtcDateTime: SQLite trả datetime KHÔNG có múi giờ (toàn hệ thống lưu UTC) —
    xuất ra luôn là ISO-8601 có hậu tố "Z", trình duyệt không hiểu nhầm thành
    giờ địa phương.
  - Money: Decimal nội bộ → number trong JSON (frontend/src/api/types.ts khai
    báo number). CHỈ ép kiểu ở biên API; lưu trữ/tính toán vẫn là Decimal.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

from app.utils.dates import as_utc

T = TypeVar("T")


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(iso_utc, return_type=str)]
Money = Annotated[Decimal, PlainSerializer(float, return_type=float)]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[Any] = []
    trace_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class IdResponse(BaseModel):
    id: int


class OutModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
