"""
Dịch vụ xác nhận thủ công

Xử lý quyết định của người duyệt và cho quy trình chạy tiếp.

Hàng chờ xác nhận = chứng từ status=needs_review (ADR-003 — không có bảng
"hàng chờ" riêng); `review id` trong API chính là document id. Bảng
human_reviews ghi QUYẾT ĐỊNH (ai, lúc nào, approve|correct|reject).

  - resolve(): ghi human_reviews + audit_logs (giá trị TRƯỚC và SAU).
      approve → ok; correct → extraction MỚI (model_name='human'), chạy lại QC
      để lưu kết quả kiểm tra của bản sửa, chứng từ → ok (người đã xác nhận);
      reject → rejected.
  - Sau khi chứng từ cuối cùng của một lần chạy đang NEEDS_REVIEW được xử lý:
      còn chứng từ được chấp nhận → run về hàng đợi (RETRYING → PENDING) để
      chạy các bước còn lại của nhánh đạt; không còn gì → SUCCEEDED.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domain.state import RunStatus, transition
from app.models.artifact import Document
from app.models.audit import AuditLog
from app.models.extraction import Extraction, HumanReview, QCResult
from app.models.run import Run
from app.models.user import User
from app.ports.queue import JobQueue
from app.schemas.invoice import SCHEMA_VERSION, InvoiceExtraction
from app.services import qc_service, run_service

ACTIONS = ("approve", "correct", "reject")


def latest_extraction(db: Session, document_id: int) -> Extraction | None:
    return db.scalar(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc(), Extraction.id.desc())
        .limit(1)
    )


def _parse(data: dict[str, Any]) -> InvoiceExtraction:
    try:
        return InvoiceExtraction.model_validate(data)
    except ValidationError as exc:
        raise ValidationFailed(
            "Dữ liệu hoá đơn sửa tay không hợp lệ.",
            details=[
                {"loc": list(e.get("loc", ())), "message": e.get("msg", "")} for e in exc.errors()
            ],
        ) from exc


def _same(current: Extraction | None, data: InvoiceExtraction) -> bool:
    if current is None:
        return False
    try:
        before = InvoiceExtraction.model_validate_json(current.extracted_data_json)
    except ValueError:
        return False
    return before == data


def resolve(
    db: Session,
    queue: JobQueue,
    document: Document,
    action: str,
    user: User,
    *,
    data: dict[str, Any] | None = None,
    note: str | None = None,
    allow_statuses: tuple[str, ...] = ("needs_review",),
) -> Document:
    if action not in ACTIONS:
        raise ValidationFailed(f"Hành động '{action}' không hợp lệ (approve|correct|reject).")
    if document.status not in allow_statuses:
        raise Conflict("Chứng từ không ở trạng thái chờ xác nhận.")
    current = latest_extraction(db, document.id)
    if action in ("approve", "correct") and current is None and data is None:
        raise Conflict("Chứng từ chưa có dữ liệu trích xuất — hãy nhập dữ liệu (correct).")

    before = json.loads(current.extracted_data_json) if current else None
    after: dict[str, Any] | None = before
    extraction = current
    if action == "correct":
        if data is None:
            raise ValidationFailed("Cần gửi kèm dữ liệu đã sửa (data) khi chọn 'correct'.")
        parsed = _parse(data)
        if _same(current, parsed):
            action = "approve"  # không đổi gì = xác nhận nguyên trạng
        else:
            extraction = _save_correction(db, document, current, parsed)
            after = parsed.model_dump(mode="json")

    old_status = document.status
    document.status = "rejected" if action == "reject" else "ok"
    db.add(
        HumanReview(
            document_id=document.id,
            extraction_id=extraction.id if extraction else None,
            reviewer_id=user.id,
            action=action,
            corrected_data_json=json.dumps(after, ensure_ascii=False)
            if action == "correct"
            else None,
            note=note,
        )
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action=f"document.review.{action}",
            entity_type="document",
            entity_id=document.id,
            detail_json=json.dumps(
                {
                    "status_before": old_status,
                    "status_after": document.status,
                    "before": before,
                    "after": after,
                    "note": note,
                },
                ensure_ascii=False,
                default=str,
            ),
        )
    )
    db.flush()
    run_id = (current.run_id if current else None) or (extraction.run_id if extraction else None)
    if run_id is not None:
        _maybe_resume_run(db, queue, run_id, user)
    return document


def _save_correction(
    db: Session, document: Document, current: Extraction | None, data: InvoiceExtraction
) -> Extraction:
    extraction = Extraction(
        document_id=document.id,
        run_id=current.run_id if current else None,
        schema_version=SCHEMA_VERSION,
        model_name="human",
        confidence=None,
        latency_ms=0,
        invoice_no=data.invoice_no,
        issue_date=data.issue_date,
        seller_name=data.seller.name,
        seller_tax_code=data.seller.tax_code,
        currency=data.currency,
        subtotal=data.totals.subtotal,
        vat_rate=data.totals.vat_rate,
        vat_amount=data.totals.vat_amount,
        total=data.totals.total,
        extracted_data_json=json.dumps(data.model_dump(mode="json"), ensure_ascii=False),
    )
    db.add(extraction)
    db.flush()
    qc_service.evaluate(db, extraction)
    return extraction


def _maybe_resume_run(db: Session, queue: JobQueue, run_id: int, user: User) -> None:
    run = db.get(Run, run_id)
    if run is None or run.status != RunStatus.NEEDS_REVIEW.value:
        return
    pending = db.scalar(
        select(func.count(func.distinct(Document.id)))
        .join(Extraction, Extraction.document_id == Document.id)
        .where(Extraction.run_id == run_id, Document.status == "needs_review")
    )
    if pending:
        return
    accepted = db.scalar(
        select(func.count(func.distinct(HumanReview.document_id)))
        .join(Extraction, Extraction.document_id == HumanReview.document_id)
        .join(Document, Document.id == HumanReview.document_id)
        .where(
            Extraction.run_id == run_id,
            Document.status == "ok",
            HumanReview.action.in_(("approve", "correct")),
        )
    )
    log_fn = run_service.transition_logger(db)
    if not accepted:
        transition(
            run, RunStatus.SUCCEEDED,
            f"{user.full_name} đã xử lý xong mọi chứng từ chờ xác nhận — không còn bước nào",
            log_fn,
        )
        return
    transition(
        run, RunStatus.RETRYING,
        f"{user.full_name} đã xác nhận xong — chạy tiếp các bước còn lại",
        log_fn,
    )
    transition(run, RunStatus.PENDING, "Đưa lần chạy trở lại hàng đợi", log_fn)
    queue.enqueue(db, run.id)


# ─── Truy vấn hàng chờ ───


def _critical_failed():  # noqa: ANN202 — biểu thức SQL dùng chung
    return func.sum(
        case((and_(QCResult.passed.is_(False), QCResult.severity == "critical"), 1), else_=0)
    )


def queue_page(db: Session, *, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    """Hàng chờ: sắp theo số lỗi nghiêm trọng giảm dần, rồi tới thời gian nạp."""
    ranked = select(
        Extraction.id.label("extraction_id"),
        Extraction.document_id.label("document_id"),
        Extraction.run_id.label("run_id"),
        Extraction.invoice_no.label("invoice_no"),
        Extraction.seller_name.label("seller_name"),
        Extraction.total.label("total"),
        func.row_number()
        .over(
            partition_by=Extraction.document_id,
            order_by=(Extraction.created_at.desc(), Extraction.id.desc()),
        )
        .label("rn"),
    ).subquery()
    failed = func.sum(case((QCResult.passed.is_(False), 1), else_=0))
    critical = _critical_failed()
    stmt = (
        select(
            Document,
            ranked.c.run_id,
            ranked.c.invoice_no,
            ranked.c.seller_name,
            ranked.c.total,
            func.coalesce(failed, 0).label("qc_failed"),
            func.coalesce(critical, 0).label("critical_failed"),
        )
        .outerjoin(ranked, and_(ranked.c.document_id == Document.id, ranked.c.rn == 1))
        .outerjoin(QCResult, QCResult.extraction_id == ranked.c.extraction_id)
        .where(Document.status == "needs_review")
        .group_by(Document.id)
    )
    total = db.scalar(
        select(func.count(Document.id)).where(Document.status == "needs_review")
    ) or 0
    rows = db.execute(
        stmt.order_by(
            func.coalesce(critical, 0).desc(), Document.created_at.asc(), Document.id.asc()
        )
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    items = [
        {
            "id": doc.id,
            "document_id": doc.id,
            "filename": doc.filename,
            "run_id": run_id,
            "invoice_no": invoice_no,
            "seller_name": seller_name,
            "total": total_amount,
            "qc_failed": int(qc_failed or 0),
            "critical_failed": int(critical_failed or 0),
            "created_at": doc.created_at,
        }
        for doc, run_id, invoice_no, seller_name, total_amount, qc_failed, critical_failed in rows
    ]
    return items, total


def stats(db: Session) -> dict[str, int]:
    pending = db.scalar(
        select(func.count(Document.id)).where(Document.status == "needs_review")
    ) or 0
    return {"pending": pending}


def get_document(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFound("Chứng từ không tồn tại.")
    return document
