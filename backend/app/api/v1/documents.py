"""
Điểm cuối chứng từ

Nạp tệp, liệt kê chứng từ theo trạng thái, xem chi tiết kết quả trích xuất và
tải tệp gốc. Hàng đợi chờ xác nhận chính là danh sách này với bộ lọc
status=needs_review (xem note TASK-006 trong IMPLEMENTATION_PLAN.md).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, BinaryIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_llm, get_storage
from app.core.config import settings
from app.models.artifact import Document
from app.models.extraction import Extraction, QCResult
from app.ports.llm import LLMProvider
from app.ports.storage import ArtifactRef, FileStorage
from app.schemas.invoice import InvoiceExtraction
from app.services import document_service

# TODO SECURITY (TASK-006): chưa bảo vệ các endpoint bằng auth/JWT — cần
# models/user.py + JWT (việc riêng, chưa nằm trong phạm vi task). PHẢI thêm
# xác thực + phân quyền trước khi deploy thật, đừng coi đây là bản vĩnh viễn.

router = APIRouter()


class PresignRequest(BaseModel):
    sha256: str


def _latest_extraction(db: Session, document_id: int) -> Extraction | None:
    """Extraction mới nhất theo created_at/id (đồng hồ có thể trùng)."""
    return db.scalar(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc(), Extraction.id.desc())
        .limit(1)
    )


def _floatify(obj: Any) -> Any:
    """Đệ quy chuyển mọi Decimal trong dict/list thành float.

    NOTE (TASK-007): Pydantic (cả mode="python" lẫn mode="json") VÀ
    jsonable_encoder của FastAPI đều serialize Decimal thành CHUỖI (giữ chính
    xác tuyệt đối) — nhưng `frontend/src/api/types.ts` khai báo mọi trường tiền
    tệ là `number` (vd. DocumentRow.total, InvoiceData.totals.subtotal,
    LineItem.quantity/unit_price/amount). Chuỗi vẫn hiển thị được ở hầu hết chỗ
    (Intl.NumberFormat tự ép kiểu) nhưng sai hợp đồng kiểu dữ liệu — chỉ ép
    float ở BIÊN API (trả về cho frontend hiển thị), KHÔNG đụng tới Decimal
    dùng nội bộ (lưu DB/tính toán vẫn luôn Decimal theo đúng quy tắc kiến
    trúc).
    """
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _floatify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_floatify(v) for v in obj]
    return obj


def _document_row(
    document: Document,
    extraction: Extraction | None,
    qc_failed: int = 0,
) -> dict[str, Any]:
    """Một dòng trong danh sách chứng từ."""
    return {
        "id": document.id,
        "filename": document.filename,
        "source_kind": document.source_kind,
        "status": document.status,
        "invoice_no": extraction.invoice_no if extraction else None,
        "issue_date": (
            extraction.issue_date.isoformat()
            if extraction and extraction.issue_date
            else None
        ),
        "seller_name": extraction.seller_name if extraction else None,
        "total": float(extraction.total) if extraction and extraction.total is not None else None,
        "qc_failed": qc_failed,
        "created_at": document.created_at.isoformat(),
    }


def _extraction_data(extraction: Extraction | None) -> dict[str, Any]:
    """Dựng object `data` trả về cho frontend.

    Parse lại extracted_data_json bằng InvoiceExtraction (đảm bảo đúng cấu trúc
    schema) rồi dump về mode="python" + _floatify() để mọi trường tiền tệ lồng
    nhau (totals.*, line_items[].quantity/unit_price/amount) là number thật,
    khớp `InvoiceData` trong types.ts. KHÔNG trả thẳng json.loads() vì trong
    blob tiền tệ đang là chuỗi (chính xác tuyệt đối để lưu — xem
    _serialize_extraction).
    """
    if extraction is None or not extraction.extracted_data_json:
        return {}
    try:
        parsed = InvoiceExtraction.model_validate_json(extraction.extracted_data_json)
        return _floatify(parsed.model_dump(mode="python"))
    except (ValueError, TypeError):
        return {}


def _document_detail(
    document: Document,
    extraction: Extraction | None,
) -> dict[str, Any]:
    """Chi tiết đầy đủ: hàng cơ bản + file_url + extraction + qc[].

    NOTE (TASK-007): KHÔNG dùng `storage.url_for(ref)` — adapter trả về
    "/artifacts/{path}" (đường dẫn CHUNG, chính docstring của nó ghi rõ "chưa
    nối với route API thật nào"), nhưng route đó CHƯA BAO GIỜ được mount ở
    `main.py` (không `StaticFiles`, không router nào khớp `/artifacts/*`) —
    phát hiện thật khi xem `<img>` bị vỡ trên frontend. Route THẬT để tải file
    là `GET /documents/{id}/file` (đã hiện thực ở TASK-006, ngay trong file
    này) — dùng đúng route đó.
    """
    qc_results = list(extraction.qc_results) if extraction else []
    return {
        **_document_row(
            document,
            extraction,
            qc_failed=sum(1 for q in qc_results if not q.passed),
        ),
        "file_url": f"/api/v1/documents/{document.id}/file",
        "schema_version": extraction.schema_version if extraction else None,
        "model_name": extraction.model_name if extraction else None,
        "confidence": (
            float(extraction.confidence)
            if extraction and extraction.confidence is not None
            else None
        ),
        "latency_ms": extraction.latency_ms if extraction else 0,
        "data": _extraction_data(extraction),
        "qc": [
            {
                "rule_code": q.rule_code,
                "severity": q.severity,
                "passed": q.passed,
                "field": q.field,
                "message": q.message,
            }
            for q in qc_results
        ],
    }


def _read_with_limit(file: UploadFile) -> bytes:
    """Đọc file theo khối, từ chối 413 nếu vượt MAX_UPLOAD_MB — không bắt buộc
    đọc hết file vào RAM trước khi kiểm tra."""
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Tệp vượt quá giới hạn {settings.MAX_UPLOAD_MB} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _file_chunks(fileobj: BinaryIO):
    """Tạo iterator đọc và đóng file gốc khi kết thúc stream."""
    try:
        while chunk := fileobj.read(64 * 1024):
            yield chunk
    finally:
        fileobj.close()

@router.post("/presign")
def presign(
    body: PresignRequest,
    storage: Annotated[FileStorage, Depends(get_storage)],
) -> dict[str, bool]:
    """Kiểm tra đã có tệp cùng sha256 trong kho hay chưa (chống trùng sớm).

    Chỉ chạm vào storage, KHÔNG đọc DB — entry nhỏ để frontend bỏ qua upload
    lặp.
    """
    return {"exists": storage.exists(body.sha256)}


@router.post("", status_code=200)
def upload_document(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
    storage: Annotated[FileStorage, Depends(get_storage)],
) -> dict[str, Any]:
    """Nạp file (multipart), trích xuất bằng LLM + QC, trả chi tiết chứng từ.

    Điểm cuối ĐỒNG BỘ (sync def): FastAPI chạy hàm này trong threadpool nên
    thời gian gọi mô hình (nhiều giây) không chặn event loop — đúng quyết định
    "sync, không job queue" của TASK-006. Tệp quá MAX_UPLOAD_MB bị từ chối 413
    trước khi đọc hết vào RAM (xem _read_with_limit).
    """
    file_bytes = _read_with_limit(file)
    filename = file.filename or "unknown"
    content_type = file.content_type
    document = document_service.ingest(
        db, storage, llm, file_bytes, filename, content_type
    )
    db.commit()
    # Sau commit vẫn cần đọc lại quan hệ (session dùng expire_on_commit=False,
    # nhưng extractions có thể chưa load) — đọc lại sạch sẽ hơn.
    db.refresh(document, attribute_names=["artifact", "extractions"])
    extraction = _latest_extraction(db, document.id)
    return _document_detail(document, extraction)


@router.get("")
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Phân trang danh sách chứng từ.

    JOIN extraction MỚI NHẤT theo document_id (window function row_number, không
    phải GROUP BY) để lấy invoice_no/issue_date/seller_name/total; qc_failed =
    số QCResult.passed=False của extraction đó; lọc theo status và khoảng ngày
    của extraction mới nhất.
    """
    ranked = (
        select(
            Extraction.id.label("extraction_id"),
            Extraction.document_id.label("document_id"),
            Extraction.invoice_no.label("invoice_no"),
            Extraction.issue_date.label("issue_date"),
            Extraction.seller_name.label("seller_name"),
            Extraction.total.label("total"),
            func.row_number()
            .over(
                partition_by=Extraction.document_id,
                order_by=(Extraction.created_at.desc(), Extraction.id.desc()),
            )
            .label("rn"),
        ).subquery()
    )
    latest = ranked.alias()
    qc_failed = (
        select(func.count(QCResult.id))
        .where(
            QCResult.extraction_id == latest.c.extraction_id,
            QCResult.passed.is_(False),
        )
        .correlate(latest)
        .scalar_subquery()
        .label("qc_failed")
    )
    stmt = (
        select(
            Document,
            latest.c.invoice_no,
            latest.c.issue_date,
            latest.c.seller_name,
            latest.c.total,
            qc_failed,
        ).outerjoin(latest, and_(latest.c.document_id == Document.id, latest.c.rn == 1))
    )
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)
    if from_date is not None:
        stmt = stmt.where(latest.c.issue_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(latest.c.issue_date <= to_date)

    page_size = max(limit, 1)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(Document.created_at.desc(), Document.id.desc())
        .limit(page_size)
        .offset(offset)
    ).all()

    items = []
    for row in rows:
        document = row[0]
        items.append(
            {
                "id": document.id,
                "filename": document.filename,
                "source_kind": document.source_kind,
                "status": document.status,
                "invoice_no": row.invoice_no,
                "issue_date": (
                    row.issue_date.isoformat() if row.issue_date else None
                ),
                "seller_name": row.seller_name,
                "total": float(row.total) if row.total is not None else None,
                "qc_failed": row.qc_failed or 0,
                "created_at": document.created_at.isoformat(),
            }
        )
    return {
        "items": items,
        "total": total if total is not None else 0,
        "page": offset // page_size + 1,
        "page_size": page_size,
    }


@router.get("/{document_id}")
def get_document(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Chi tiết một chứng từ: dữ liệu trích xuất mới nhất + toàn bộ qc_results."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chứng từ không tồn tại.",
        )
    extraction = _latest_extraction(db, document_id)
    return _document_detail(document, extraction)


@router.get("/{document_id}/file")
def get_document_file(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[FileStorage, Depends(get_storage)],
) -> StreamingResponse:
    """Trả về tệp gốc (dùng cho khung xem ảnh ở frontend)."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chứng từ không tồn tại.",
        )
    ref = ArtifactRef(
        sha256=document.artifact.sha256,
        path=document.artifact.path,
        size_bytes=document.artifact.size_bytes,
        content_type=document.artifact.content_type,
    )
    fileobj = storage.open(ref)
    media_type = ref.content_type or "application/octet-stream"
    return StreamingResponse(
        _file_chunks(fileobj),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{document.filename}"'},
    )