"""Kiểm thử services/document_service.py (TASK-006)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.adapters.storage_local import LocalFileStorage
from app.models.artifact import Artifact, Document
from app.models.extraction import QCResult
from app.ports.llm import LLMUnavailable
from app.services import document_service
from tests.conftest import VALID_INVOICE_PAYLOAD, FakeLLM


def _fake_png_bytes() -> bytes:
    """Ảnh PNG hợp lệ nhỏ, đủ để PIL.Image.open() giải mã thật."""
    buf = io.BytesIO()
    Image.new("RGB", (20, 10), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(str(tmp_path / "artifacts"))


def test_ingest_valid_invoice_sets_status_ok(db: Session, tmp_path: Path) -> None:
    llm = FakeLLM(parsed=VALID_INVOICE_PAYLOAD)
    storage = _storage(tmp_path)

    document = document_service.ingest(
        db, storage, llm, _fake_png_bytes(), "hd-001.png", "image/png"
    )
    db.commit()

    assert document.status == "ok"
    assert document.source_kind == "image"
    assert document.artifact is not None
    assert len(llm.calls) == 1
    assert llm.calls[0]["schema"] is not None  # invoice_json_schema() đã truyền

    extractions = list(document.extractions)
    assert len(extractions) == 1
    extraction = extractions[0]
    assert extraction.invoice_no == "0000123"
    assert extraction.seller_name == "Công ty TNHH ABC"
    assert extraction.model_name == "fake-model-v1"

    qc_results = db.query(QCResult).filter(QCResult.extraction_id == extraction.id).all()
    assert len(qc_results) == 8
    assert all(q.passed for q in qc_results)


def test_ingest_rejected_content_type_does_not_call_llm(db: Session, tmp_path: Path) -> None:
    llm = FakeLLM(parsed=VALID_INVOICE_PAYLOAD)
    storage = _storage(tmp_path)

    document = document_service.ingest(
        db, storage, llm, b"PK\x03\x04fake-zip-bytes", "report.zip", "application/zip"
    )
    db.commit()

    assert document.status == "rejected"
    assert len(llm.calls) == 0
    assert list(document.extractions) == []


def test_ingest_corrupt_image_bytes_rejected(db: Session, tmp_path: Path) -> None:
    """content-type khai image/png nhưng bytes không giải mã được -> rejected,
    KHÔNG crash, KHÔNG gọi LLM."""
    llm = FakeLLM(parsed=VALID_INVOICE_PAYLOAD)
    storage = _storage(tmp_path)

    document = document_service.ingest(
        db, storage, llm, b"khong-phai-anh-that", "fake.png", "image/png"
    )
    db.commit()

    assert document.status == "rejected"
    assert len(llm.calls) == 0


def test_ingest_llm_unavailable_sets_status_failed(db: Session, tmp_path: Path) -> None:
    llm = FakeLLM(raise_exc=LLMUnavailable("bộ ngắt mạch đang mở"))
    storage = _storage(tmp_path)

    document = document_service.ingest(
        db, storage, llm, _fake_png_bytes(), "hd-002.png", "image/png"
    )
    db.commit()

    assert document.status == "failed"
    assert list(document.extractions) == []


def test_ingest_llm_output_fails_schema_validation_sets_status_failed(
    db: Session, tmp_path: Path
) -> None:
    """Mô hình trả JSON không khớp InvoiceExtraction (thiếu trường bắt buộc) ->
    failed, không crash request."""
    llm = FakeLLM(parsed={"invoice_no": "0000999"})  # thiếu issue_date/seller/totals/line_items
    storage = _storage(tmp_path)

    document = document_service.ingest(
        db, storage, llm, _fake_png_bytes(), "hd-003.png", "image/png"
    )
    db.commit()

    assert document.status == "failed"


def test_ingest_dedupes_artifact_by_sha256(db: Session, tmp_path: Path) -> None:
    """Upload 2 lần cùng bytes -> 2 Document khác nhau nhưng DÙNG CHUNG 1
    Artifact (khử trùng theo sha256, không lưu trùng bytes trên đĩa)."""
    png_bytes = _fake_png_bytes()
    storage = _storage(tmp_path)

    doc1 = document_service.ingest(
        db, storage, FakeLLM(parsed=VALID_INVOICE_PAYLOAD), png_bytes, "a.png", "image/png"
    )
    db.commit()
    doc2 = document_service.ingest(
        db, storage, FakeLLM(parsed=VALID_INVOICE_PAYLOAD), png_bytes, "b.png", "image/png"
    )
    db.commit()

    assert doc1.id != doc2.id
    assert doc1.artifact_id == doc2.artifact_id
    assert db.query(Artifact).count() == 1
    assert db.query(Document).count() == 2
