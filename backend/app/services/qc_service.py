"""
Dịch vụ kiểm soát chất lượng

Chạy tập quy tắc, ghi kết quả và định tuyến sang hàng đợi xác nhận
(hàng đợi thực chất là bộ lọc status=needs_review trên danh sách chứng từ).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain import qc_rules
from app.models.extraction import Extraction, QCResult


def evaluate(db: Session, extraction: Extraction) -> bool:
    """Chạy 8 quy tắc QC trên extraction và ghi kết quả, trả về needs_review.

    - Tạo 1 dòng QCResult cho mỗi quy tắc trong 8 quy tắc (cả pass lẫn fail).
    - KHÔNG tự commit — caller (document_service.ingest) quyết định thời điểm.
    - KHÔNG tạo bản ghi human_reviews — hàng đợi xác nhận chính là danh sách
      chứng từ lọc status=needs_review (ADR-003); human_reviews chỉ ghi QUYẾT
      ĐỊNH của người duyệt (services/review_service.py).
    """
    # Idempotent: chạy lại (worker thử lại lần chạy) thay thế kết quả cũ thay vì
    # nhân đôi số dòng qc_results của cùng một extraction.
    db.execute(delete(QCResult).where(QCResult.extraction_id == extraction.id))
    data = _build_qc_data(extraction)
    existing_invoice_numbers = _existing_invoice_numbers(db, extraction)
    results, needs_review = qc_rules.run_qc(
        data, existing_invoice_numbers=existing_invoice_numbers
    )
    for rule in results:
        db.add(
            QCResult(
                extraction_id=extraction.id,
                rule_code=rule.rule_code,
                severity=rule.severity,
                passed=rule.passed,
                field=rule.field,
                message=rule.message,
            )
        )
    return needs_review


def _existing_invoice_numbers(db: Session, extraction: Extraction) -> list[str]:
    """Số hoá đơn của CHỨNG TỪ KHÁC (phục vụ QC-06).

    Loại trừ mọi extraction của cùng document, không chỉ chính nó: bản sửa tay
    (extraction mới) mang đúng số hoá đơn của bản AI đọc trước đó của cùng chứng
    từ — so với nó sẽ luôn báo trùng giả (lỗi thật phát hiện qua test luồng sửa).
    """
    rows = db.execute(
        select(Extraction.invoice_no).where(
            Extraction.invoice_no.is_not(None),
            Extraction.document_id != extraction.document_id,
        )
    ).all()
    return [row[0] for row in rows if row[0]]


def _build_qc_data(extraction: Extraction) -> dict[str, Any]:
    """Dựng object/dict trung gian khớp ĐÚNG cấu trúc InvoiceExtraction mà
    domain/qc_rules.run_qc() kỳ vọng (seller{name, tax_code}, totals{...}).

    Extraction (ORM) chỉ có cột phẳng seller_name/seller_tax_code/... — KHÔNG
    có thuộc tính `seller` lồng nhau. Truyền thẳng object ORM vào run_qc() sẽ
    khiến qc_rules đọc seller.name/seller.tax_code thành None, làm QC-04/QC-07
    fail giả (xem note TASK-006 trong IMPLEMENTATION_PLAN.md).
    """
    parsed: dict[str, Any] = {}
    if extraction.extracted_data_json:
        try:
            parsed = json.loads(extraction.extracted_data_json)
        except (ValueError, TypeError):
            parsed = {}
    return {
        "invoice_no": extraction.invoice_no,
        "invoice_form": None,  # không có cột phẳng; schema không dùng cho QC
        "issue_date": extraction.issue_date,
        "currency": extraction.currency,
        "seller": {
            "name": extraction.seller_name,
            "tax_code": extraction.seller_tax_code,
        },
        "line_items": parsed.get("line_items") or [],
        "totals": {
            "subtotal": extraction.subtotal,
            "vat_rate": extraction.vat_rate,
            "vat_amount": extraction.vat_amount,
            "total": extraction.total,
        },
    }
