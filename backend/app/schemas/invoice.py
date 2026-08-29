"""
Lược đồ dữ liệu hoá đơn

Cấu trúc dữ liệu hoá đơn giá trị gia tăng Việt Nam, có đánh số phiên bản.
Đây vừa là hợp đồng dữ liệu giữa mô hình và hệ thống (kiểu Pydantic), vừa là
nguồn sinh JSON Schema truyền cho cơ chế sinh có ràng buộc (guided_json) khi
gọi LLM.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "invoice_v1"


class Party(BaseModel):
    """Bên tham gia trên hoá đơn (bên bán / bên mua)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    # NOTE bắt buộc (TASK-006): cố ý viết LỎNG hơn mô tả gốc (bỏ pattern 10/13
    # số) — vì domain/qc_rules.py QC-04 (đã hiện thực, đã test) coi mã số thuế
    # sai là dữ liệu AI đọc SAI cần QC-04 bắt lỗi và báo needs_review, không
    # phải lỗi hệ thống cần chặn cứng ở tầng Pydantic (chặn cứng sẽ làm cả
    # request lỗi 422 thay vì lưu lại kèm cảnh báo QC — sai mục tiêu
    # "human-in-the-loop" của AGENTS.md). Cần Owner xác nhận lại.
    tax_code: str | None = None
    address: str | None = None


class LineItem(BaseModel):
    """Một dòng hàng hoá trên hoá đơn."""

    model_config = ConfigDict(extra="forbid")

    line_no: int
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


class Totals(BaseModel):
    """Tổng tiền hoá đơn."""

    model_config = ConfigDict(extra="forbid")

    subtotal: Decimal
    # NOTE bắt buộc (TASK-006): cố ý KHÔNG dùng Literal[0,5,8,10] cứng — để
    # QC-03 (domain/qc_rules.py) báo lỗi khi AI đọc sai thuế suất, Pydantic chỉ
    # ép kiểu Decimal (lý do tương tự NOTE ở Party.tax_code).
    vat_rate: Decimal
    vat_amount: Decimal
    total: Decimal


class InvoiceExtraction(BaseModel):
    """Toàn bộ dữ liệu trích xuất từ một hoá đơn."""

    model_config = ConfigDict(extra="forbid")

    invoice_no: str
    invoice_form: str | None = None
    issue_date: date
    currency: str = "VND"
    seller: Party
    buyer: Party | None = None
    line_items: list[LineItem]
    totals: Totals


def invoice_json_schema() -> dict[str, Any]:
    """Trả về JSON Schema của InvoiceExtraction, dùng làm tham số `schema=`
    khi gọi llm.complete().

    CẢNH BÁO (ghi theo TASK-006): JSON Schema sinh từ Decimal có thể không
    tương thích 100% với guided_json của vLLM (một số backend guided-decoding
    không hỗ trợ `anyOf`/`format` mà Pydantic sinh cho Decimal) — nếu khi Owner
    test thật gặp lỗi LLMInvalidOutput, đây là nghi phạm đầu tiên cần kiểm tra,
    KHÔNG tự đổi sang float.
    """
    return InvoiceExtraction.model_json_schema()
