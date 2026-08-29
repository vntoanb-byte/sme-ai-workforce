"""Kiểm thử services/qc_service.py (TASK-006).

Trọng tâm: qc_service phải TỰ DỰNG object trung gian có seller{name, tax_code}
lồng nhau từ 2 cột phẳng seller_name/seller_tax_code của Extraction (ORM)
trước khi gọi domain/qc_rules.run_qc() — Extraction KHÔNG có thuộc tính
`seller`, truyền thẳng object ORM sẽ làm QC-04/QC-07 fail giả.
"""

from __future__ import annotations

import itertools
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.artifact import Artifact, Document
from app.models.extraction import Extraction, QCResult
from app.services import qc_service

_sha_counter = itertools.count()


def _make_document_and_extraction(db: Session, **overrides) -> Extraction:
    # sha256 khác nhau mỗi lần gọi trong CÙNG 1 test — artifacts.sha256 là
    # UNIQUE, nhiều test gọi hàm này >1 lần (vd. test QC-06 trùng số hoá đơn).
    sha256 = f"{next(_sha_counter):064d}"
    artifact = Artifact(sha256=sha256, path="x/y.png", size_bytes=1, content_type="image/png")
    db.add(artifact)
    db.flush()
    document = Document(artifact_id=artifact.id, filename="hd.png", source_kind="image")
    db.add(document)
    db.flush()

    defaults = dict(
        document_id=document.id,
        schema_version="invoice_v1",
        model_name="fake-model-v1",
        latency_ms=1,
        invoice_no="0000123",
        issue_date=date(2026, 8, 20),
        seller_name="Công ty TNHH ABC",
        seller_tax_code="0101234565",  # checksum hợp lệ, xem tests/conftest.py
        currency="VND",
        subtotal=Decimal("100000"),
        vat_rate=Decimal("10"),
        vat_amount=Decimal("10000"),
        total=Decimal("110000"),
        extracted_data_json=(
            '{"line_items": [{"line_no": 1, "description": "x", "unit": "goi", '
            '"quantity": "1", "unit_price": "100000", "amount": "100000"}]}'
        ),
    )
    defaults.update(overrides)
    extraction = Extraction(**defaults)
    db.add(extraction)
    db.flush()
    return extraction


def test_evaluate_valid_invoice_all_rules_pass(db: Session) -> None:
    extraction = _make_document_and_extraction(db)

    needs_review = qc_service.evaluate(db, extraction)
    db.commit()

    assert needs_review is False
    results = db.query(QCResult).filter(QCResult.extraction_id == extraction.id).all()
    assert len(results) == 8
    assert {r.rule_code for r in results} == {f"QC-0{i}" for i in range(1, 9)}
    assert all(r.passed for r in results)


def test_evaluate_reads_seller_fields_correctly_not_none(db: Session) -> None:
    """Bug cần chặn: nếu qc_service truyền thẳng ORM object vào run_qc(), QC-04
    (mã số thuế) và QC-07 (trường bắt buộc seller.tax_code) sẽ fail giả vì đọc
    được seller.name/seller.tax_code = None. Test này KHÔNG được fail dù mã số
    thuế/tên bên bán hợp lệ."""
    extraction = _make_document_and_extraction(db)

    qc_service.evaluate(db, extraction)
    db.commit()

    qc04 = (
        db.query(QCResult)
        .filter(QCResult.extraction_id == extraction.id, QCResult.rule_code == "QC-04")
        .one()
    )
    qc07 = (
        db.query(QCResult)
        .filter(QCResult.extraction_id == extraction.id, QCResult.rule_code == "QC-07")
        .one()
    )
    assert qc04.passed is True
    assert qc07.passed is True


def test_evaluate_invalid_tax_code_needs_review_true(db: Session) -> None:
    # "0101234561" sai chữ số kiểm tra (đúng phải là "...65", xem
    # tests/conftest.py) — đã tự xác nhận qua domain/qc_rules.qc_04 thật.
    extraction = _make_document_and_extraction(db, seller_tax_code="0101234561")

    needs_review = qc_service.evaluate(db, extraction)
    db.commit()

    assert needs_review is True
    qc04 = (
        db.query(QCResult)
        .filter(QCResult.extraction_id == extraction.id, QCResult.rule_code == "QC-04")
        .one()
    )
    assert qc04.passed is False


def test_evaluate_duplicate_invoice_no_fails_qc06(db: Session) -> None:
    first = _make_document_and_extraction(db, invoice_no="0000777")
    qc_service.evaluate(db, first)
    db.commit()

    second = _make_document_and_extraction(db, invoice_no="0000777")
    needs_review = qc_service.evaluate(db, second)
    db.commit()

    assert needs_review is True
    qc06 = (
        db.query(QCResult)
        .filter(QCResult.extraction_id == second.id, QCResult.rule_code == "QC-06")
        .one()
    )
    assert qc06.passed is False
    # extraction đầu tiên không bị ảnh hưởng bởi việc thêm bản ghi thứ 2 sau nó.
    qc06_first = (
        db.query(QCResult)
        .filter(QCResult.extraction_id == first.id, QCResult.rule_code == "QC-06")
        .one()
    )
    assert qc06_first.passed is True
