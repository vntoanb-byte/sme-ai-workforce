"""
Kiểm thử giao thức giành việc

BÀI KIỂM THỬ QUAN TRỌNG NHẤT. Xác nhận không bao giờ có hai worker cùng nhận
một job — chạy trên lược đồ THẬT (Base.metadata, giống migration 0001), không
phải DDL tự viết, để bắt lệch giữa adapter SQL thô và model (đã từng lệch:
bảng thật không có DEFAULT mức SQL cho status/attempts).

  1. 10 luồng cùng gọi claim() trên 5 job → tổng số job giành được đúng bằng 5,
     không job nào bị giành hai lần.
  2. Job quá hạn lease được reap() đưa về pending, lần giành sau attempts tăng.
  3. Job đạt max_attempts thì chuyển failed, không quay lại pending.
"""

from __future__ import annotations

import threading

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from app.adapters.queue_sqlite import SQLiteJobQueue
from app.models.run import JobQueueEntry, Run


def _runs(db: Session, employee, n: int) -> list[int]:  # noqa: ANN001
    ids = []
    for _ in range(n):
        run = Run(employee_id=employee.id, workflow_id=employee.current_workflow_id,
                  trigger_type="manual", status="pending")
        db.add(run)
        db.flush()
        ids.append(run.id)
    return ids


def test_ten_threads_claim_five_jobs_exactly_once(
    db: Session, engine: Engine, queue: SQLiteJobQueue, make_employee
) -> None:
    employee = make_employee()
    for run_id in _runs(db, employee, 5):
        queue.enqueue(db, run_id)
    db.commit()

    claimed: list[int] = []
    lock = threading.Lock()
    barrier = threading.Barrier(10)

    def worker(n: int) -> None:
        barrier.wait()
        while True:
            job = queue.claim(f"w{n}", lease_seconds=60)
            if job is None:
                return
            with lock:
                claimed.append(job.id)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert len(claimed) == 5
    assert len(set(claimed)) == 5
    with engine.connect() as conn:
        statuses = conn.execute(text("SELECT status, attempts FROM job_queue")).all()
    assert all(s == ("claimed", 1) for s in statuses)


def test_expired_lease_is_reaped_and_attempts_increase(
    db: Session, queue: SQLiteJobQueue, make_employee
) -> None:
    employee = make_employee()
    job_id = queue.enqueue(db, _runs(db, employee, 1)[0])
    db.commit()

    first = queue.claim("worker-chet", lease_seconds=-1)
    assert first is not None and first.attempts == 1
    assert queue.reap_expired() == 1
    second = queue.claim("worker-moi", lease_seconds=60)
    assert second is not None and second.id == job_id
    assert second.attempts == 2
    assert second.claimed_by == "worker-moi"


def test_job_reaching_max_attempts_becomes_failed(
    db: Session, queue: SQLiteJobQueue, make_employee
) -> None:
    employee = make_employee()
    job_id = queue.enqueue(db, _runs(db, employee, 1)[0], max_attempts=2)
    db.commit()

    for _ in range(2):
        assert queue.claim("w", lease_seconds=-1) is not None
        queue.reap_expired()
    db.expire_all()
    job = db.scalar(select(JobQueueEntry).where(JobQueueEntry.id == job_id))
    assert job is not None and job.status == "failed"
    assert queue.claim("w") is None
