"""
Kiểm thử lược đồ NHÓM D-G (TASK-005b)

Đủ từng bảng được Requirements liệt kê: runs, run_steps, run_logs, job_queue,
extractions, qc_results, human_reviews, artifacts, documents, audit_logs,
llm_calls, settings. (Ghi chú: tên task ghi "11 bảng" nhưng đếm theo danh sách
Requirements thì là 12 class/bảng — viết test đủ cho TỪNG bảng được liệt kê.)

Bằng chứng quan trọng nhất: Base.metadata.create_all(engine) chạy không lỗi —
lược đồ 20 bảng nhất quán (không FK trỏ sai). Test CASCADE/SET NULL cần
PRAGMA foreign_keys=ON — copy 2 event từ app/db/session.py (giống
test_models_group_a.py) để không đụng engine/DB thật. Dùng SQLite FILE trong
tmp_path.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import (
    DateTime,
    String,
    create_engine,
    event,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import Session

from app.adapters.queue_sqlite import _fmt
from app.db.base import Base
from app.models.artifact import Artifact, Document
from app.models.audit import AuditLog, LlmCall, Setting
from app.models.employee import AIEmployee
from app.models.extraction import Extraction, HumanReview, QCResult
from app.models.run import JobQueueEntry, Run, RunLog, RunStep
from app.models.user import User
from app.models.workflow import Workflow


def _register_events(engine) -> None:
    """Copy 2 event trong app/db/session.py — test độc lập, không đụng DB thật."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _do_begin(conn) -> None:
        if conn.get_execution_options().get("sqlite_begin_immediate"):
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            conn.exec_driver_sql("BEGIN")
        conn.exec_driver_sql("PRAGMA defer_foreign_keys=ON")


@pytest.fixture()
def engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'models_d.db').as_posix()}")
    _register_events(engine)
    # BẰNG CHỨNG QUAN TRỌNG NHẤT: lược đồ 20 bảng tạo được, không FK trỏ sai.
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


def _make_user(username: str = "toan") -> User:
    return User(
        username=username,
        full_name="Nguyễn Văn Toàn",
        email=f"{username}@example.com",
        password_hash="argon2-hash-giả",
    )


def _make_employee() -> AIEmployee:
    return AIEmployee(
        name="Kế toán hoá đơn",
        job_description="Đọc hoá đơn mua vào, kiểm tra rồi ghi vào Excel",
    )


def _make_workflow(employee_id: int) -> Workflow:
    return Workflow(
        employee_id=employee_id,
        version=1,
        template_code="invoice_to_excel",
        name="Xử lý hoá đơn mua vào",
    )


def _setup_run(session: Session) -> tuple[Run, int]:
    """Tạo user + employee + workflow + run, trả về (run, user.id)."""
    user = _make_user()
    employee = _make_employee()
    session.add_all([user, employee])
    session.flush()
    workflow = _make_workflow(employee.id)
    session.add(workflow)
    session.flush()
    run = Run(
        employee_id=employee.id,
        workflow_id=workflow.id,
        trigger_type="manual",
        status="pending",
        created_by=user.id,
    )
    session.add(run)
    session.flush()
    return run, user.id


def _setup_document_and_extraction(
    session: Session, run: Run
) -> tuple[Extraction, Document]:
    artifact = Artifact(
        sha256="a" * 64,
        path="2026/08/28/abc.png",
        size_bytes=12345,
        content_type="image/png",
    )
    session.add(artifact)
    session.flush()
    document = Document(
        artifact_id=artifact.id,
        filename="hd-001.png",
        source_kind="image",
        status="processing",
    )
    session.add(document)
    session.flush()
    extraction = Extraction(
        document_id=document.id,
        run_id=run.id,
        schema_version="1.0",
        model_name="qwen3-vl-8b",
        latency_ms=500,
        extracted_data_json="{}",
    )
    session.add(extraction)
    session.flush()
    return extraction, document


def _count_where(session: Session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for col, val in filters.items():
        stmt = stmt.where(getattr(model, col) == val)
    return session.execute(stmt).scalar_one()


def test_create_all_creates_all_new_tables(engine):
    tables = set(inspect(engine).get_table_names())
    assert {
        "runs",
        "run_steps",
        "run_logs",
        "job_queue",
        "extractions",
        "qc_results",
        "human_reviews",
        "artifacts",
        "documents",
        "audit_logs",
        "llm_calls",
        "settings",
    } <= tables


def test_run_round_trip(session):
    run, user_id = _setup_run(session)
    session.commit()

    session.expire_all()
    loaded = session.get(Run, run.id)
    assert loaded is not None
    assert loaded.trigger_type == "manual"
    assert loaded.status == "pending"
    assert loaded.created_by == user_id
    assert loaded.started_at is None
    assert loaded.finished_at is None
    assert loaded.error_message is None
    # các relationship MỘT CHIỀU load được.
    assert loaded.employee.id == loaded.employee_id
    assert loaded.workflow.id == loaded.workflow_id
    assert loaded.created_by_user.id == user_id


def test_run_step_round_trip(session):
    run, _ = _setup_run(session)
    run.steps = [
        RunStep(step_key="read_invoice", order_index=1, label="Đọc hoá đơn"),
        RunStep(
            step_key="write_excel",
            order_index=2,
            label="Ghi Excel",
            status="SUCCEEDED",
            detail="xong",
            duration_ms=1200,
        ),
    ]
    session.commit()

    session.expire_all()
    loaded = session.get(Run, run.id)
    assert loaded is not None
    # order_by RunStep.order_index.
    assert [s.step_key for s in loaded.steps] == ["read_invoice", "write_excel"]
    first, second = loaded.steps
    assert first.status == "PENDING"  # default
    assert first.duration_ms is None
    assert second.status == "SUCCEEDED"
    assert second.detail == "xong"
    assert second.duration_ms == 1200
    # back_populates: run.steps[i].run.
    assert second.run.id == run.id


def test_run_log_round_trip(session):
    run, _ = _setup_run(session)
    log = RunLog(
        run_id=run.id,
        level="INFO",
        message="worker bắt đầu chạy",
        from_status="pending",
        to_status="running",
    )
    session.add(log)
    session.commit()

    session.expire_all()
    loaded = session.get(RunLog, log.id)
    assert loaded is not None
    assert loaded.run_id == run.id
    assert loaded.level == "INFO"
    assert loaded.message == "worker bắt đầu chạy"
    assert loaded.from_status == "pending"
    assert loaded.to_status == "running"
    # back_populates: run.logs chứa dòng này (order_by RunLog.created_at).
    r = session.get(Run, run.id)
    assert r is not None
    assert [lg.message for lg in r.logs] == ["worker bắt đầu chạy"]


def test_job_queue_entry_round_trip(session):
    run, _ = _setup_run(session)
    entry = JobQueueEntry(
        run_id=run.id,
        available_at="2026-08-28T10:00:00.000000Z",
        created_at="2026-08-28T10:00:00.000000Z",
    )
    session.add(entry)
    session.commit()

    session.expire_all()
    loaded = session.get(JobQueueEntry, entry.id)
    assert loaded is not None
    assert loaded.run_id == run.id
    assert loaded.status == "pending"  # default
    assert loaded.priority == 0  # default
    assert loaded.attempts == 0  # default
    assert loaded.max_attempts == 5  # default
    assert loaded.available_at == "2026-08-28T10:00:00.000000Z"
    assert loaded.created_at == "2026-08-28T10:00:00.000000Z"
    assert loaded.claimed_by is None
    assert loaded.lease_until is None
    assert loaded.last_error is None
    # back_populates: run.job_queue_entries.
    r = session.get(Run, run.id)
    assert r is not None
    assert [e.id for e in r.job_queue_entries] == [entry.id]


def test_extraction_round_trip(session):
    run, _ = _setup_run(session)
    extraction, document = _setup_document_and_extraction(session, run)
    extraction.confidence = Decimal("0.9876")
    extraction.latency_ms = 1234
    extraction.invoice_no = "HD/001"
    extraction.issue_date = date(2026, 8, 28)
    extraction.seller_name = "Công ty TNHH ABC"
    extraction.seller_tax_code = "0101234567"
    extraction.currency = "VND"
    extraction.subtotal = Decimal("100000.00")
    extraction.vat_rate = Decimal("10.00")
    extraction.vat_amount = Decimal("10000.00")
    extraction.total = Decimal("110000.00")
    extraction.extracted_data_json = '{"invoice_no": "HD/001"}'
    session.commit()

    session.expire_all()
    loaded = session.get(Extraction, extraction.id)
    assert loaded is not None
    assert loaded.document_id == document.id
    assert loaded.run_id == run.id
    assert loaded.schema_version == "1.0"
    assert loaded.model_name == "qwen3-vl-8b"
    assert loaded.confidence == Decimal("0.9876")
    assert loaded.latency_ms == 1234
    assert loaded.invoice_no == "HD/001"
    assert loaded.issue_date == date(2026, 8, 28)
    assert loaded.seller_name == "Công ty TNHH ABC"
    assert loaded.seller_tax_code == "0101234567"
    assert loaded.currency == "VND"
    assert loaded.subtotal == Decimal("100000.00")
    assert loaded.vat_rate == Decimal("10.00")
    assert loaded.vat_amount == Decimal("10000.00")
    assert loaded.total == Decimal("110000.00")
    assert loaded.extracted_data_json == '{"invoice_no": "HD/001"}'
    # relationship hai chiều document.extractions.
    assert loaded.document.id == document.id
    d = session.get(Document, document.id)
    assert d is not None
    assert [e.id for e in d.extractions] == [extraction.id]


def test_qc_result_round_trip(session):
    run, _ = _setup_run(session)
    extraction, _ = _setup_document_and_extraction(session, run)
    qc = QCResult(
        extraction_id=extraction.id,
        rule_code="QC-01",
        severity="warning",
        passed=False,
        field="subtotal",
        message="Tổng các dòng không khớp subtotal",
    )
    session.add(qc)
    session.commit()

    session.expire_all()
    loaded = session.get(QCResult, qc.id)
    assert loaded is not None
    assert loaded.extraction_id == extraction.id
    assert loaded.rule_code == "QC-01"
    assert loaded.severity == "warning"
    assert loaded.passed is False
    assert loaded.field == "subtotal"
    assert loaded.message == "Tổng các dòng không khớp subtotal"
    # back_populates: extraction.qc_results.
    e = session.get(Extraction, extraction.id)
    assert e is not None
    assert [q.id for q in e.qc_results] == [qc.id]


def test_human_review_round_trip(session):
    run, user_id = _setup_run(session)
    extraction, document = _setup_document_and_extraction(session, run)
    review = HumanReview(
        document_id=document.id,
        extraction_id=extraction.id,
        reviewer_id=user_id,
        action="correct",
        corrected_data_json='{"invoice_no": "HD/999"}',
        note="Sửa lại số hoá đơn",
    )
    session.add(review)
    session.commit()

    session.expire_all()
    loaded = session.get(HumanReview, review.id)
    assert loaded is not None
    assert loaded.document_id == document.id
    assert loaded.extraction_id == extraction.id
    assert loaded.reviewer_id == user_id
    assert loaded.action == "correct"
    assert loaded.corrected_data_json == '{"invoice_no": "HD/999"}'
    assert loaded.note == "Sửa lại số hoá đơn"
    # relationships một chiều.
    assert loaded.document.id == document.id
    assert loaded.extraction.id == extraction.id
    assert loaded.reviewer.id == user_id


def test_artifact_round_trip(session):
    artifact = Artifact(
        sha256="b" * 64,
        path="2026/08/28/xyz.pdf",
        size_bytes=99999,
        content_type="application/pdf",
    )
    session.add(artifact)
    session.commit()

    session.expire_all()
    loaded = session.get(Artifact, artifact.id)
    assert loaded is not None
    assert loaded.sha256 == "b" * 64
    assert loaded.path == "2026/08/28/xyz.pdf"
    assert loaded.size_bytes == 99999
    assert loaded.content_type == "application/pdf"


def test_document_round_trip(session):
    _, user_id = _setup_run(session)
    artifact = Artifact(
        sha256="c" * 64,
        path="2026/08/28/doc.png",
        size_bytes=321,
        content_type="image/png",
    )
    session.add(artifact)
    session.flush()
    document = Document(
        artifact_id=artifact.id,
        filename="hoa-don.png",
        source_kind="image",
        status="needs_review",
        uploaded_by=user_id,
    )
    session.add(document)
    session.commit()

    session.expire_all()
    loaded = session.get(Document, document.id)
    assert loaded is not None
    assert loaded.artifact_id == artifact.id
    assert loaded.filename == "hoa-don.png"
    assert loaded.source_kind == "image"
    assert loaded.status == "needs_review"
    assert loaded.uploaded_by == user_id
    # relationships một chiều.
    assert loaded.artifact.id == artifact.id
    assert loaded.uploaded_by_user.id == user_id
    # Artifact.documents (MỘT CHIỀU + viewonly) load được.
    a = session.get(Artifact, artifact.id)
    assert a is not None
    assert [d.id for d in a.documents] == [document.id]


def test_audit_log_round_trip(session):
    user = _make_user()
    session.add(user)
    session.flush()
    log = AuditLog(
        user_id=user.id,
        action="document.extraction.correct",
        entity_type="extraction",
        entity_id=123,
        detail_json='{"from": "HD/001", "to": "HD/999"}',
    )
    session.add(log)
    session.commit()

    session.expire_all()
    loaded = session.get(AuditLog, log.id)
    assert loaded is not None
    assert loaded.user_id == user.id
    assert loaded.action == "document.extraction.correct"
    assert loaded.entity_type == "extraction"
    assert loaded.entity_id == 123
    assert loaded.detail_json == '{"from": "HD/001", "to": "HD/999"}'
    # relationship một chiều.
    assert loaded.user.id == user.id


def test_llm_call_round_trip(session):
    run, _ = _setup_run(session)
    extraction, document = _setup_document_and_extraction(session, run)
    call = LlmCall(
        run_id=run.id,
        document_id=document.id,
        model_name="qwen3-vl-8b",
        prompt_tokens=128,
        completion_tokens=64,
        latency_ms=1500,
        status="success",
    )
    session.add(call)
    session.commit()

    session.expire_all()
    loaded = session.get(LlmCall, call.id)
    assert loaded is not None
    assert loaded.run_id == run.id
    assert loaded.document_id == document.id
    assert loaded.model_name == "qwen3-vl-8b"
    assert loaded.prompt_tokens == 128
    assert loaded.completion_tokens == 64
    assert loaded.latency_ms == 1500
    assert loaded.status == "success"
    assert loaded.error_message is None
    # relationships một chiều.
    assert loaded.run.id == run.id
    assert loaded.document.id == document.id


def test_setting_round_trip(session):
    user = _make_user()
    session.add(user)
    session.flush()
    setting = Setting(
        key="LLM_BASE_URL_OVERRIDE",
        value_json='"http://localhost:8000/v1"',
        updated_by=user.id,
    )
    session.add(setting)
    session.commit()

    session.expire_all()
    loaded = session.get(Setting, "LLM_BASE_URL_OVERRIDE")
    assert loaded is not None
    assert loaded.value_json == '"http://localhost:8000/v1"'
    assert loaded.updated_by == user.id
    # updated_at có ý nghĩa thật ở bảng settings (TimestampMixin).
    assert loaded.updated_at is not None


def test_orm_delete_run_cascades_steps_logs_job_queue(session):
    run, _ = _setup_run(session)
    run.steps = [RunStep(step_key="a", order_index=1, label="Bước A")]
    run.logs = [RunLog(level="INFO", message="chạy xong")]
    run.job_queue_entries = [
        JobQueueEntry(
            available_at="2026-08-28T10:00:00.000000Z",
            created_at="2026-08-28T10:00:00.000000Z",
        )
    ]
    session.commit()

    session.delete(run)
    session.commit()
    session.rollback()  # kết thúc transaction WAL cũ (bài học TASK-005a)

    assert session.get(Run, run.id) is None
    assert _count_where(session, RunStep, run_id=run.id) == 0
    assert _count_where(session, RunLog, run_id=run.id) == 0
    assert _count_where(session, JobQueueEntry, run_id=run.id) == 0


def test_delete_extraction_sets_null_and_delete_document_cascades(session):
    run, user_id = _setup_run(session)
    extraction, document = _setup_document_and_extraction(session, run)
    extraction.qc_results = [
        QCResult(
            rule_code="QC-01",
            severity="warning",
            passed=False,
            field="subtotal",
            message="lệch subtotal",
        )
    ]
    review = HumanReview(
        document_id=document.id,
        extraction_id=extraction.id,
        reviewer_id=user_id,
        action="reject",
        note="Số liệu sai",
    )
    session.add(review)
    session.commit()

    # (1) Xoá Extraction riêng: qc_results bị xoá theo cascade; human_reviews
    #     vẫn còn nhưng extraction_id chuyển NULL (SET NULL ở DB).
    session.delete(extraction)
    session.commit()
    session.rollback()

    assert session.get(Extraction, extraction.id) is None
    assert _count_where(session, QCResult, extraction_id=extraction.id) == 0
    assert _count_where(session, HumanReview, document_id=document.id) == 1
    rv = session.execute(
        select(HumanReview).where(HumanReview.document_id == document.id)
    ).scalar_one()
    assert rv.extraction_id is None

    # (2) Xoá Document: extractions (đã rỗng) + human_reviews xoá theo cascade.
    session.delete(session.get(Document, document.id))
    session.commit()
    session.rollback()

    assert _count_where(session, Extraction, document_id=document.id) == 0
    assert _count_where(session, HumanReview, document_id=document.id) == 0


def test_job_queue_timestamps_stored_as_text_not_datetime(session, engine):
    run, _ = _setup_run(session)
    now = datetime(2026, 8, 28, 10, 0, 0, 123456, tzinfo=UTC)
    entry = JobQueueEntry(
        run_id=run.id,
        available_at=_fmt(now),
        created_at=_fmt(now),
    )
    session.add(entry)
    session.commit()
    session.rollback()

    # Kiểu cột khai báo là String(32) — KHÔNG phải DateTime.
    cols = {c["name"]: c["type"] for c in inspect(engine).get_columns("job_queue")}
    assert isinstance(cols["available_at"], String)
    assert isinstance(cols["created_at"], String)
    assert not isinstance(cols["available_at"], DateTime)
    assert not isinstance(cols["created_at"], DateTime)

    # Dữ liệu lưu đúng định dạng _fmt() của adapters/queue_sqlite.py.
    available_at, created_at = session.execute(
        select(JobQueueEntry.available_at, JobQueueEntry.created_at).where(
            JobQueueEntry.id == entry.id
        )
    ).one()
    assert available_at == _fmt(now)
    assert created_at == _fmt(now)

    # typeof() của SQLite xác nhận lưu ở dạng TEXT.
    type_of = session.execute(
        text(
            "SELECT typeof(available_at), typeof(created_at) "
            "FROM job_queue WHERE id = :id"
        ),
        {"id": entry.id},
    ).one()
    assert tuple(type_of) == ("text", "text")