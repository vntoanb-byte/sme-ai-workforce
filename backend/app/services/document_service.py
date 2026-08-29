"""
Dịch vụ chứng từ

Nạp tệp, tạo artifact và document, khử trùng theo mã băm, gọi mô hình trích
xuất và chạy QC (THAO TÁC ĐỒNG BỘ — quyết định cắt phạm vi của Claude trong
IMPLEMENTATION_PLAN.md TASK-006).
"""

from __future__ import annotations

import io
import json

from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.artifact import Artifact, Document
from app.models.extraction import Extraction
from app.ports.llm import (
    LLMInvalidOutput,
    LLMProvider,
    LLMResult,
    LLMTimeout,
    LLMUnavailable,
)
from app.ports.storage import FileStorage
from app.schemas.invoice import SCHEMA_VERSION, InvoiceExtraction, invoice_json_schema
from app.services import qc_service
from app.utils import images
from app.utils.hashing import sha256_bytes

_PROMPT = (
    "Đây là ảnh hoá đơn giá trị gia tăng Việt Nam. Hãy trích xuất đầy đủ các "
    "trường dữ liệu theo đúng lược đồ JSON được chỉ định. Chỉ trả về JSON hợp "
    "lệ, không thêm chú thích hay văn bản khác."
)


def ingest(
    db: Session,
    storage: FileStorage,
    llm: LLMProvider,
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
) -> Document:
    """Nạp tệp vào hệ thống và trích xuất nội dung.

    Flow (THAO TÁC ĐỒNG BỘ theo TASK-006):
      1. Phát hiện loại nguồn theo content-type, không tin phần mở rộng.
          - image/*  -> "image"
          - application/pdf, application/x-pdf -> "pdf"
          - khác     -> None (từ chối, lưu document status="rejected")
      2. Lưu artifact (khử trùng theo sha256, không lưu trùng bytes).
      3. Cắt ảnh trang đầu (PDF render @ PDF_RENDER_DPI) và preprocess
         (utils.images.preprocess).
      4. Gọi llm.complete(messages, schema=invoice_json_schema(), images=[...]).
      5. Validate JSON đầu ra bằng InvoiceExtraction.
      6. Ghi phiên bản extraction + chạy 8 quy tắc QC.

    Trạng thái document được đặt 1 lần DUY NHẤT ở cuối flow. KHÔNG tự commit —
    caller (api) quyết định thời điểm. Trả về Document đã load sẵn các quan hệ
    artifact + extractions.
    """
    kind = _detect_source_kind(content_type)
    artifact = _ensure_artifact(db, storage, file_bytes, filename)
    document = Document(filename=filename, source_kind=kind or "image", status="processing")
    document.artifact = artifact
    db.add(document)
    db.flush()

    if kind is None:
        document.status = "rejected"
        _refresh_loaded(document, db)
        return document

    try:
        image_bytes = _prepare_image_bytes(file_bytes, kind)
    except Exception:  # noqa: BLE001 — file tuyên bố image/pdf nhưng không giải mã được
        document.status = "rejected"
        _refresh_loaded(document, db)
        return document

    try:
        result = llm.complete(
            messages=[{"role": "user", "content": _PROMPT}],
            schema=invoice_json_schema(),
            images=[image_bytes],
        )
    except (LLMTimeout, LLMUnavailable, LLMInvalidOutput):
        document.status = "failed"
        _refresh_loaded(document, db)
        return document

    try:
        extraction_data = InvoiceExtraction.model_validate(result.parsed)
    except ValidationError:
        document.status = "failed"
        _refresh_loaded(document, db)
        return document

    extraction = _create_extraction(db, document.id, result, extraction_data)
    needs_review = qc_service.evaluate(db, extraction)
    document.status = "needs_review" if needs_review else "ok"
    _refresh_loaded(document, db)
    return document


def _refresh_loaded(document: Document, db: Session) -> None:
    """Load sẵn quan hệ artifact + extractions trước khi trả về (rời khỏi
    transaction của caller thì lazy-load sẽ không còn hoạt động được)."""
    db.refresh(document, attribute_names=["artifact", "extractions"])


def _detect_source_kind(content_type: str | None) -> str | None:
    """Phát hiện loại nguồn theo content-type (chuẩn hoá về chữ thường).

    application/octet-stream không được chấp nhận — quá mơ hồ, không tin.
    """
    if not content_type:
        return None
    normalized = content_type.split(";")[0].strip().lower()
    if normalized.startswith("image/"):
        return "image"
    if normalized in ("application/pdf", "application/x-pdf"):
        return "pdf"
    return None


def _ensure_artifact(
    db: Session,
    storage: FileStorage,
    file_bytes: bytes,
    filename: str,
) -> Artifact:
    """Tạo Artifact, khử trùng theo sha256 để không lưu trùng bytes trên đĩa.

    Nếu storage.exists(sha256) nhưng DB chưa có Artifact tương ứng (vd. thư mục
    data/artifacts được copy từ máy khác) thì cũng tạo lại bản ghi — storage
    của LocalFileStorage khi gặp file trùng chỉ trả về ref cũ, không ghi lại.
    """
    sha256 = sha256_bytes(file_bytes)
    if not storage.exists(sha256):
        ref = storage.save(file_bytes, filename)
        artifact = Artifact(
            sha256=ref.sha256,
            path=ref.path,
            size_bytes=ref.size_bytes,
            content_type=ref.content_type,
        )
        db.add(artifact)
        db.flush()
        return artifact

    existing_artifact: Artifact | None = db.scalar(
        select(Artifact).where(Artifact.sha256 == sha256)
    )
    if existing_artifact is not None:
        return existing_artifact

    ref = storage.save(file_bytes, filename)
    artifact = Artifact(
        sha256=ref.sha256,
        path=ref.path,
        size_bytes=ref.size_bytes,
        content_type=ref.content_type,
    )
    db.add(artifact)
    db.flush()
    return artifact


def _prepare_image_bytes(file_bytes: bytes, kind: str) -> bytes:
    """Giải mã ảnh/PDF thành 1 ảnh JPEG duy nhất sau preprocess.

    PDF: render trang đầu ở PDF_RENDER_DPI rồi preprocess.
    Ảnh: mở bằng PIL, preprocess, nén JPEG quality 85 (đủ cho mô hình thu gọn).
    """
    if kind == "pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(file_bytes)
        try:
            page = pdf[0]  # luôn lấy trang ĐẦU TIÊN (theo IMPLEMENTATION_PLAN)
            bitmap = page.render(scale=settings.PDF_RENDER_DPI / 72.0)
            pil_image = bitmap.to_pil()
        finally:
            pdf.close()
    else:
        pil_image = Image.open(io.BytesIO(file_bytes))
        pil_image.load()

    pil_image = images.preprocess(pil_image)
    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _create_extraction(
    db: Session,
    document_id: int,
    result: LLMResult,
    extraction_data: InvoiceExtraction,
) -> Extraction:
    """Tạo bản ghi Extraction (cột phẳng + json đầy đủ) từ kết quả LLM."""
    extraction = Extraction(
        document_id=document_id,
        schema_version=SCHEMA_VERSION,
        model_name=result.model,
        confidence=None,  # mô hình không trả score; đặt None để người xem biết rõ là không có
        latency_ms=result.latency_ms,
        invoice_no=extraction_data.invoice_no,
        issue_date=extraction_data.issue_date,
        seller_name=extraction_data.seller.name,
        seller_tax_code=extraction_data.seller.tax_code,
        currency=extraction_data.currency,
        subtotal=extraction_data.totals.subtotal,
        vat_rate=extraction_data.totals.vat_rate,
        vat_amount=extraction_data.totals.vat_amount,
        total=extraction_data.totals.total,
        extracted_data_json=_serialize_extraction(extraction_data),
    )
    db.add(extraction)
    db.flush()
    return extraction


def _serialize_extraction(data: InvoiceExtraction) -> str:
    """Nối chuỗi JSON lưu vào cột extracted_data_json.

    Dùng model_dump(mode="json") — Decimal/date được Pydantic chuyển thành
    chuỗi (giữ nguyên độ chính xác, không làm mất chữ số qua float). Phía API
    sẽ parse lại bằng InvoiceExtraction.model_validate_json() rồi trả ra cho
    frontend với kiểu số (xem app/api/v1/documents.py).
    """
    return json.dumps(data.model_dump(mode="json"), ensure_ascii=False)

