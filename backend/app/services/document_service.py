"""
Dịch vụ chứng từ

Nạp tệp, tạo artifact và document, khử trùng theo mã băm, gọi mô hình trích
xuất và chạy QC.

Hai đường dùng:
  - ingest(): upload trực tiếp qua API (đồng bộ, lỗi mô hình → status failed).
  - extract_document(): dùng lại bởi công cụ vision.extract_invoice trong một
    lần chạy workflow (gắn run_id, QC để bước qc.validate_invoice làm riêng,
    lỗi TẠM THỜI của mô hình được ném ra để worker thử lại cả lần chạy).
Mỗi lời gọi mô hình ghi một dòng llm_calls (thống kê token/độ trễ/lỗi).
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
from app.models.audit import LlmCall
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

EXTRACTION_PROMPT = (
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
    *,
    uploaded_by: int | None = None,
) -> Document:
    """Nạp tệp vào hệ thống và trích xuất nội dung (upload trực tiếp).

    Flow:
      1. Phát hiện loại nguồn theo content-type, không tin phần mở rộng.
          - image/*  -> "image"
          - application/pdf, application/x-pdf -> "pdf"
          - khác     -> None (từ chối, lưu document status="rejected")
      2. Lưu artifact (khử trùng theo sha256, không lưu trùng bytes).
      3-6. extract_document(): ảnh trang đầu + preprocess → mô hình →
         InvoiceExtraction → extraction + 8 quy tắc QC.

    Commit MỘT lần ngay trước lời gọi mô hình (artifact + document ở trạng thái
    "processing"): SQLite chỉ có một người ghi, giữ khoá ghi suốt 10–25 giây chờ
    mô hình làm mọi thao tác ghi khác (worker, người dùng khác) báo "database is
    locked". Phần kết quả trích xuất do caller commit. Trả về Document đã load
    sẵn các quan hệ artifact + extractions.
    """
    kind = detect_source_kind(content_type)
    artifact = ensure_artifact(db, storage, file_bytes, filename)
    document = Document(
        filename=filename,
        source_kind=kind or "image",
        status="processing",
        uploaded_by=uploaded_by,
    )
    document.artifact = artifact
    db.add(document)
    db.flush()

    if kind is None:
        document.status = "rejected"
        _refresh_loaded(document, db)
        return document

    db.commit()
    extract_document(db, llm, document, file_bytes)
    _refresh_loaded(document, db)
    return document


def extract_document(
    db: Session,
    llm: LLMProvider,
    document: Document,
    file_bytes: bytes,
    *,
    run_id: int | None = None,
    run_qc: bool = True,
    raise_transient: bool = False,
) -> Extraction | None:
    """Trích xuất 1 chứng từ đã có bản ghi Document; trả về Extraction hoặc None.

    Kết quả trạng thái document:
      - tệp không giải mã được → rejected;
      - mô hình lỗi / đầu ra sai cấu trúc → failed (trừ khi raise_transient=True
        và lỗi là tạm thời: LLMTimeout/LLMUnavailable → ném ra cho caller);
      - thành công: run_qc=True → ok|needs_review; run_qc=False → processing
        (chờ bước qc.validate_invoice của workflow).
    """
    try:
        image_bytes = prepare_image_bytes(file_bytes, document.source_kind)
    except Exception:  # noqa: BLE001 — file tuyên bố image/pdf nhưng không giải mã được
        document.status = "rejected"
        return None

    try:
        result = llm.complete(
            messages=[{"role": "user", "content": EXTRACTION_PROMPT}],
            schema=invoice_json_schema(),
            images=[image_bytes],
        )
    except (LLMTimeout, LLMUnavailable, LLMInvalidOutput) as exc:
        record_llm_call(db, None, run_id=run_id, document_id=document.id, error=exc)
        if raise_transient and isinstance(exc, LLMTimeout | LLMUnavailable):
            raise
        document.status = "failed"
        return None
    record_llm_call(db, result, run_id=run_id, document_id=document.id)

    try:
        extraction_data = InvoiceExtraction.model_validate(result.parsed)
    except ValidationError:
        document.status = "failed"
        return None

    extraction = _create_extraction(db, document.id, result, extraction_data, run_id=run_id)
    if run_qc:
        needs_review = qc_service.evaluate(db, extraction)
        document.status = "needs_review" if needs_review else "ok"
    else:
        document.status = "processing"
    return extraction


def record_llm_call(
    db: Session,
    result: LLMResult | None,
    *,
    run_id: int | None = None,
    document_id: int | None = None,
    error: Exception | None = None,
) -> None:
    """Ghi 1 dòng llm_calls cho mỗi lời gọi mô hình (thành công hoặc lỗi)."""
    db.add(
        LlmCall(
            run_id=run_id,
            document_id=document_id,
            model_name=result.model if result else settings.LLM_MODEL,
            prompt_tokens=result.token_in if result else None,
            completion_tokens=result.token_out if result else None,
            latency_ms=result.latency_ms if result else 0,
            status="error" if error is not None else "success",
            error_message=str(error)[:1000] if error is not None else None,
        )
    )


def _refresh_loaded(document: Document, db: Session) -> None:
    """Load sẵn quan hệ artifact + extractions trước khi trả về (rời khỏi
    transaction của caller thì lazy-load sẽ không còn hoạt động được)."""
    db.refresh(document, attribute_names=["artifact", "extractions"])


def detect_source_kind(content_type: str | None) -> str | None:
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


def ensure_artifact(
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


def prepare_image_bytes(file_bytes: bytes, kind: str) -> bytes:
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
    *,
    run_id: int | None = None,
) -> Extraction:
    """Tạo bản ghi Extraction (cột phẳng + json đầy đủ) từ kết quả LLM."""
    extraction = Extraction(
        document_id=document_id,
        run_id=run_id,
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



class RecordingLLM:
    """Bọc một LLMProvider, ghi llm_calls cho MỌI lời gọi (kể cả lời gọi do
    domain/compiler thực hiện — domain không được chạm DB)."""

    def __init__(self, inner: LLMProvider, db: Session, *, run_id: int | None = None) -> None:
        self._inner = inner
        self._db = db
        self._run_id = run_id

    def complete(self, messages, *, schema=None, images=None, timeout=None):  # noqa: ANN001, ANN201
        try:
            result = self._inner.complete(messages, schema=schema, images=images, timeout=timeout)
        except (LLMTimeout, LLMUnavailable, LLMInvalidOutput) as exc:
            record_llm_call(self._db, None, run_id=self._run_id, error=exc)
            raise
        record_llm_call(self._db, result, run_id=self._run_id)
        return result
