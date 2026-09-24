"""
Kiểm thử luồng thực thi

Chạy trọn một quy trình (mẫu invoice_to_excel) qua ĐÚNG đường thật:
run_service.create_run (run + job cùng transaction) → Worker.process_one (giành
việc BEGIN IMMEDIATE) → execution_service → crew tuần tự → công cụ → DB/kho tệp.
Chỉ mô hình là giả (SmartLLM).

  1. Kịch bản đạt: chạy hết các bước, SUCCEEDED, có tệp Excel kết quả.
  2. QC không đạt: dừng ở NEEDS_REVIEW, nhánh đạt vẫn ghi Excel cho chứng từ tốt;
     người duyệt chấp nhận → lần chạy tự quay lại hàng đợi, chạy tiếp nhánh đạt
     cho đúng chứng từ vừa duyệt → SUCCEEDED.
  3. Lỗi tạm thời: thử lại tại chỗ đúng retry_max, rồi RETRYING + backoff; hết
     lượt job thì FAILED.
  4. Lỗi vĩnh viễn, huỷ giữa chừng, không có tệp mới, worker không chết vì lỗi lạ,
     reaper thu hồi job của worker chết.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.queue_sqlite import SQLiteJobQueue
from app.adapters.storage_local import LocalFileStorage
from app.domain.state import RunStatus
from app.models.artifact import Document
from app.models.run import JobQueueEntry, Run, RunLog
from app.models.user import User
from app.ports.llm import LLMUnavailable
from app.services import execution_service, review_service, run_service
from app.workers.reaper import reap
from app.workers.worker import Worker
from tests.conftest import SmartLLM, invoice_payload, png_bytes


@pytest.fixture()
def put_files(scan_dir: Path):  # noqa: ANN201
    def _put(n: int, start: int = 0) -> None:
        for i in range(start, start + n):
            (scan_dir / f"hd_{i:03d}.png").write_bytes(png_bytes(i))

    return _put


def _worker(queue: SQLiteJobQueue, session_factory: sessionmaker[Session],
            storage: LocalFileStorage, llm: Any) -> Worker:
    return Worker(queue, session_factory, storage, llm, worker_id="w-test",
                  lease_seconds=60, poll_interval=0, retry_delay=0)


def _start(db: Session, queue: SQLiteJobQueue, employee: Any) -> int:
    run = run_service.create_run(db, queue, employee, trigger_type="manual", user_id=None)
    db.commit()
    return run.id


def _state(session_factory: sessionmaker[Session], run_id: int) -> dict[str, Any]:
    with session_factory() as s:
        run = s.get(Run, run_id)
        assert run is not None
        detail = run_service.run_detail(s, run)
        job = s.scalar(
            select(JobQueueEntry).where(JobQueueEntry.run_id == run_id)
            .order_by(JobQueueEntry.id.desc()).limit(1)
        )
        transitions = [
            (log.from_status, log.to_status)
            for log in s.scalars(select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.id))
            if log.to_status
        ]
        return {
            "status": run.status,
            "steps": {st["step_key"]: st["status"] for st in detail["steps"]},
            "stats": detail["stats"],
            "outputs": detail["outputs"],
            "job": job.status if job else None,
            "transitions": transitions,
            "error": run.error_message,
        }


def test_happy_path_succeeds(db, queue, session_factory, storage, make_employee, put_files):
    employee = make_employee()
    put_files(3)
    llm = SmartLLM(invoices=[invoice_payload(f"000000{i}") for i in range(3)])
    run_id = _start(db, queue, employee)

    assert _worker(queue, session_factory, storage, llm).process_one() is True

    st = _state(session_factory, run_id)
    assert st["status"] == "succeeded"
    assert st["job"] == "succeeded"
    assert st["steps"] == {
        "scan_folder": "SUCCEEDED", "read_invoice": "SUCCEEDED", "check_data": "SUCCEEDED",
        "write_excel": "SUCCEEDED", "to_review": "SKIPPED",
    }
    assert st["stats"]["read"] == 3 and st["stats"]["passed"] == 3
    assert st["stats"]["needs_review"] == 0
    assert len(st["outputs"]) == 1 and st["outputs"][0]["filename"].endswith(".xlsx")
    assert st["transitions"] == [
        ("pending", "claimed"), ("claimed", "running"), ("running", "succeeded")
    ]
    assert llm.calls.count("invoice") == 3
    # Không còn việc gì trong hàng đợi.
    assert _worker(queue, session_factory, storage, llm).process_one() is False


def test_qc_failure_needs_review_then_resume_after_approval(
    db, queue, session_factory, storage, make_employee, put_files, users
):
    employee = make_employee()
    put_files(3)
    llm = SmartLLM(invoices=[
        invoice_payload("0000001"), invoice_payload("0000002", bad_total=True),
        invoice_payload("0000003"),
    ])
    run_id = _start(db, queue, employee)
    worker = _worker(queue, session_factory, storage, llm)
    worker.process_one()

    st = _state(session_factory, run_id)
    assert st["status"] == "needs_review"
    assert st["steps"]["write_excel"] == "SUCCEEDED"   # chứng từ tốt không phải chờ
    assert st["steps"]["to_review"] == "SUCCEEDED"
    assert st["stats"] == {"read": 3, "passed": 2, "needs_review": 1,
                           "total_amount": st["stats"]["total_amount"]}
    assert len(st["outputs"]) == 1

    bad = db.scalar(select(Document).where(Document.status == "needs_review"))
    assert bad is not None
    review_service.resolve(db, queue, bad, "approve", db.get(User, users["ketoan"].id))
    db.commit()
    assert _state(session_factory, run_id)["status"] == "pending"

    worker.process_one()
    st = _state(session_factory, run_id)
    assert st["status"] == "succeeded"
    assert len(st["outputs"]) == 2          # thêm đúng 1 tệp Excel cho chứng từ vừa duyệt
    assert llm.calls.count("invoice") == 3  # không đọc lại hoá đơn khi chạy tiếp
    assert ("needs_review", "retrying") in st["transitions"]


def test_reject_all_reviewed_documents_finishes_run(
    db, queue, session_factory, storage, make_employee, put_files, users
):
    employee = make_employee()
    put_files(1)
    run_id = _start(db, queue, employee)
    _worker(queue, session_factory, storage,
            SmartLLM(invoices=[invoice_payload("0000009", bad_total=True)])).process_one()
    assert _state(session_factory, run_id)["status"] == "needs_review"

    bad = db.scalar(select(Document).where(Document.status == "needs_review"))
    review_service.resolve(db, queue, bad, "reject", db.get(User, users["ketoan"].id))  # type: ignore[arg-type]
    db.commit()
    assert _state(session_factory, run_id)["status"] == "succeeded"
    assert db.scalar(select(JobQueueEntry.id).where(JobQueueEntry.status == "pending")) is None


def test_transient_error_retries_then_fails(
    db, queue, session_factory, storage, make_employee, put_files
):
    employee = make_employee()
    put_files(1)
    llm = SmartLLM(invoices=[LLMUnavailable("máy chủ mô hình quá tải")] * 10)
    run_id = _start(db, queue, employee)
    db.execute(update(JobQueueEntry).values(max_attempts=2))
    db.commit()
    worker = _worker(queue, session_factory, storage, llm)

    worker.process_one()
    st = _state(session_factory, run_id)
    assert st["status"] == "retrying"
    assert st["job"] == "pending"                    # trả về hàng đợi, có backoff
    assert llm.calls.count("invoice") == 3           # 1 lần + retry_max=2 của bước
    assert worker.process_one() is False             # còn trong thời gian backoff

    db.execute(text("UPDATE job_queue SET available_at='2000-01-01T00:00:00.000000Z'"))
    db.commit()
    worker.process_one()
    st = _state(session_factory, run_id)
    assert st["status"] == "failed"
    assert st["job"] == "failed"
    assert llm.calls.count("invoice") == 6
    assert ("retrying", "claimed") in st["transitions"]


def test_permanent_error_fails_run_without_retry(
    db, queue, session_factory, storage, make_employee, put_files
):
    employee = make_employee(config={"write_excel": {"file": "/etc/SoHoaDon.xlsx"}})
    put_files(1)
    run_id = _start(db, queue, employee)
    _worker(queue, session_factory, storage,
            SmartLLM(invoices=[invoice_payload("0000010")])).process_one()
    st = _state(session_factory, run_id)
    assert st["status"] == "failed"
    assert st["steps"]["write_excel"] == "FAILED"
    assert "ngoài các thư mục được phép" in st["error"]
    assert st["job"] == "succeeded"  # lỗi đã được xử lý trọn vẹn, không thử lại


def test_no_new_files_skips_downstream(db, queue, session_factory, storage, make_employee):
    employee = make_employee()
    run_id = _start(db, queue, employee)
    _worker(queue, session_factory, storage, SmartLLM()).process_one()
    st = _state(session_factory, run_id)
    assert st["status"] == "succeeded"
    assert st["steps"]["scan_folder"] == "SUCCEEDED"
    assert {k for k, v in st["steps"].items() if v == "SKIPPED"} == {
        "read_invoice", "check_data", "write_excel", "to_review"
    }


def test_cancel_before_and_during_run(
    db, queue, session_factory, storage, make_employee, put_files, users
):
    employee = make_employee()
    run_id = _start(db, queue, employee)
    run_service.cancel_run(db, db.get(Run, run_id), "Quản lý")  # type: ignore[arg-type]
    db.commit()
    assert _worker(queue, session_factory, storage, SmartLLM()).process_one() is True
    st = _state(session_factory, run_id)
    assert st["status"] == "cancelled" and st["job"] == "succeeded"
    assert "scan_folder" not in st["steps"] or st["steps"]["scan_folder"] == "PENDING"

    # Huỷ trong lúc đang đọc hoá đơn → dừng trước bước kế tiếp.
    put_files(1)
    run_id = _start(db, queue, employee)

    class CancellingLLM(SmartLLM):
        def complete(self, messages, **kw):  # noqa: ANN001, ANN201
            with session_factory() as s:
                run_service.cancel_run(s, s.get(Run, run_id), "Quản lý")  # type: ignore[arg-type]
                s.commit()
            return super().complete(messages, **kw)

    _worker(queue, session_factory, storage,
            CancellingLLM(invoices=[invoice_payload("0000011")])).process_one()
    st = _state(session_factory, run_id)
    assert st["status"] == "cancelled"
    assert st["steps"]["read_invoice"] == "SUCCEEDED"
    assert st["steps"]["check_data"] == "PENDING"


def test_worker_survives_unexpected_crash(
    db, queue, session_factory, storage, make_employee, monkeypatch
):
    employee = make_employee()
    run_id = _start(db, queue, employee)

    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("lỗi lập trình bất ngờ")

    monkeypatch.setattr(execution_service, "execute", boom)
    assert _worker(queue, session_factory, storage, SmartLLM()).process_one() is True
    st = _state(session_factory, run_id)
    assert st["status"] == "failed"
    assert st["job"] == "failed"
    assert "lỗi lập trình bất ngờ" in st["error"]


def test_reaper_recovers_job_of_dead_worker(
    db, queue, session_factory, storage, make_employee, put_files
):
    employee = make_employee()
    put_files(1)
    run_id = _start(db, queue, employee)
    # Worker "chết" giữa chừng: đã giành job, run đang RUNNING, lease hết hạn.
    job = queue.claim("worker-chet", lease_seconds=-5)
    assert job is not None
    run = db.get(Run, run_id)
    run.status = RunStatus.RUNNING.value  # dựng tình huống — code thật đi qua domain/state
    db.commit()

    assert reap(queue, session_factory) == 1
    st = _state(session_factory, run_id)
    assert st["status"] == "retrying" and st["job"] == "pending"

    _worker(queue, session_factory, storage,
            SmartLLM(invoices=[invoice_payload("0000012")])).process_one()
    assert _state(session_factory, run_id)["status"] == "succeeded"
