"""
Kiểm thử hàng đợi công việc trên SQLite

Tái hiện đúng môi trường thật: SQLite FILE trong thư mục tạm (KHÔNG dùng
':memory:' vì mỗi connection ':memory:' là một DB riêng — sẽ không mô phỏng
được nhiều connection/thread cùng truy cập một file như thực tế). Engine của
test đăng ký lại y hệt 2 event "connect"/"begin" của app/db/session.py để có
giao thức BEGIN IMMEDIATE (ADR-001) — copy logic thay vì import app.db.session
để không đụng engine/DB thật của dự án theo settings.DATABASE_URL.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.adapters.queue_sqlite import SQLiteJobQueue
from app.ports.queue import Job

# Lược đồ bảng job_queue — đúng cột adapter giả định (chưa có model ORM thật và
# migration Alembic nên test tự tạo bảng bằng DDL thô).
_DDL = """
CREATE TABLE job_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    claimed_by TEXT,
    lease_until TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    last_error TEXT,
    created_at TEXT NOT NULL
)
"""


def _fmt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


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


@pytest.fixture()
def engine(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'queue_test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    _register_events(engine)
    with engine.begin() as conn:
        conn.execute(text(_DDL))
    yield engine
    engine.dispose()


@pytest.fixture()
def queue(engine) -> SQLiteJobQueue:
    return SQLiteJobQueue(engine)


def _enqueue(
    queue: SQLiteJobQueue,
    engine,
    run_id: int = 1,
    *,
    priority: int = 0,
    available_at: datetime | None = None,
    max_attempts: int = 5,
) -> int:
    """enqueue đúng cách dùng thật: chung Session, caller tự commit (ADR-001)."""
    session = Session(engine)
    try:
        job_id = queue.enqueue(
            session,
            run_id,
            priority=priority,
            available_at=available_at,
            max_attempts=max_attempts,
        )
        session.commit()
        return job_id
    finally:
        session.close()


def _row(engine, job_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, run_id, status, priority, available_at, claimed_by, "
                "lease_until, attempts, max_attempts, last_error, created_at "
                "FROM job_queue WHERE id=:job_id"
            ),
            {"job_id": job_id},
        ).fetchone()
    assert row is not None
    return dict(row._mapping)

# --- a. enqueue rồi claim lấy đúng job, status chuyển 'claimed' ---------------


def test_enqueue_and_claim(engine, queue):
    job_id = _enqueue(queue, engine, run_id=7)
    job = queue.claim("worker-a")
    assert job is not None
    assert job.id == job_id
    assert job.run_id == 7
    assert job.priority == 0
    assert job.attempts == 1
    assert job.max_attempts == 5
    assert job.claimed_by == "worker-a"
    assert job.lease_until is not None
    assert job.lease_until > datetime.now(UTC)
    assert job.created_at.tzinfo is not None

    row = _row(engine, job_id)
    assert row["status"] == "claimed"
    assert row["claimed_by"] == "worker-a"
    assert row["lease_until"] is not None
    assert row["attempts"] == 1


def test_enqueue_does_not_commit_by_itself(engine, queue):
    # ADR-001: enqueue dùng CHUNG transaction với runs — caller chưa commit thì
    # rollback là job biến mất, không để lại nửa chừng.
    session = Session(engine)
    try:
        queue.enqueue(session, run_id=1)
        session.rollback()
    finally:
        session.close()
    assert queue.claim("worker-a") is None


# --- b. hàng đợi rỗng -> claim trả None --------------------------------------


def test_claim_empty_queue_returns_none(queue):
    assert queue.claim("worker-a") is None


# --- c. bỏ qua job có available_at trong tương lai ---------------------------


def test_claim_skips_job_not_yet_available(engine, queue):
    future = datetime.now(UTC) + timedelta(hours=1)
    job_id = _enqueue(queue, engine, available_at=future)
    assert queue.claim("worker-a") is None
    assert _row(engine, job_id)["status"] == "pending"


# --- d. claim ưu tiên job có priority cao hơn trước --------------------------


def test_claim_prefers_higher_priority(engine, queue):
    now = datetime.now(UTC)
    low_id = _enqueue(queue, engine, run_id=1, priority=1, available_at=now)
    high_id = _enqueue(queue, engine, run_id=2, priority=10, available_at=now)
    first = queue.claim("worker-a")
    second = queue.claim("worker-a")
    assert first is not None and first.id == high_id
    assert second is not None and second.id == low_id


# --- e. ĐỒNG THỜI: 2 worker giành 1 job, CHỈ đúng 1 thắng --------------------


def test_claim_concurrent_only_one_worker_wins(engine, queue):
    """Test quan trọng nhất TASK-003 — chứng minh BEGIN IMMEDIATE chống đụng độ.

    2 thread gọi claim() gần như đồng thời (threading.Barrier) trên cùng file DB
    thật: đúng 1 worker giành được job, worker còn lại phải nhận None.
    """
    _enqueue(queue, engine, run_id=1)

    results: dict[str, Job | None] = {}
    barrier = threading.Barrier(2)

    def _claim(worker_id: str) -> None:
        barrier.wait()
        results[worker_id] = queue.claim(worker_id)

    threads = [
        threading.Thread(target=_claim, args=(worker_id,))
        for worker_id in ("worker-a", "worker-b")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    winners = [w for w, job in results.items() if job is not None]
    assert len(winners) == 1
    loser = "worker-b" if winners[0] == "worker-a" else "worker-a"
    assert results[loser] is None


# --- f. complete() đổi status thành công -------------------------------------


def test_complete_marks_succeeded(engine, queue):
    _enqueue(queue, engine)
    claimed = queue.claim("worker-a")
    assert claimed is not None
    queue.complete(claimed.id)
    assert _row(engine, claimed.id)["status"] == "succeeded"


# --- g. fail() khi attempts < max_attempts: quay lại pending + backoff --------


def test_fail_below_max_attempts_requeues_with_backoff(engine, queue):
    job_id = _enqueue(queue, engine, run_id=1)
    claimed = queue.claim("worker-a")
    assert claimed is not None
    before = _row(engine, job_id)
    queue.fail(claimed.id, "lỗi tạm thời")
    row = _row(engine, job_id)
    assert row["status"] == "pending"
    assert row["last_error"] == "lỗi tạm thời"
    # available_at mới bị đẩy ra tương lai so với cũ (cùng định dạng chuỗi
    # ISO8601 UTC nên so sánh chuỗi = so sánh thời gian).
    assert row["available_at"] > before["available_at"]
    assert row["attempts"] == 1


# --- h. fail() khi attempts >= max_attempts: 'failed', không claim lại được ----


def test_fail_at_max_attempts_marks_failed_and_not_claimable(engine, queue):
    job_id = _enqueue(queue, engine, max_attempts=1)
    claimed = queue.claim("worker-a")
    assert claimed is not None
    queue.fail(claimed.id, "lỗi vĩnh viễn")
    row = _row(engine, job_id)
    assert row["status"] == "failed"
    assert row["last_error"] == "lỗi vĩnh viễn"
    # Không còn available_at trong tương lai để claim lại được job này.
    assert queue.claim("worker-b") is None


# --- i. reap_expired() thu hồi đúng job quá hạn, không đụng job còn hạn --------


def test_reap_expired_only_reclaims_overdue_leases(engine, queue):
    job_a = _enqueue(queue, engine, run_id=1)
    job_b = _enqueue(queue, engine, run_id=2)
    overdue = queue.claim("worker-a", lease_seconds=-10)
    valid = queue.claim("worker-b", lease_seconds=300)
    assert overdue is not None
    assert valid is not None

    assert queue.reap_expired() == 1
    assert _row(engine, job_a)["status"] == "pending"
    assert _row(engine, job_b)["status"] == "claimed"


def test_extend_lease_only_for_owner(engine, queue):
    job_id = _enqueue(queue, engine)
    job = queue.claim("worker-a", lease_seconds=1)
    assert job is not None
    before = _row(engine, job_id)["lease_until"]
    assert queue.extend_lease(job_id, "worker-a", lease_seconds=600) is True
    assert _row(engine, job_id)["lease_until"] > before
    assert queue.extend_lease(job_id, "worker-b", lease_seconds=600) is False


def test_fail_without_retry_goes_straight_to_failed(engine, queue):
    job_id = _enqueue(queue, engine, max_attempts=5)
    queue.claim("worker-a")
    queue.fail(job_id, "lỗi vĩnh viễn", retry=False)
    row = _row(engine, job_id)
    assert row["status"] == "failed"
    assert row["last_error"] == "lỗi vĩnh viễn"


def test_reap_marks_exhausted_job_failed(engine, queue):
    job_id = _enqueue(queue, engine, max_attempts=1)
    assert queue.claim("worker-a", lease_seconds=-10) is not None  # attempts = 1 = max
    assert queue.reap_expired() == 1
    row = _row(engine, job_id)
    assert row["status"] == "failed"
    assert "hết số lần thử" in row["last_error"]
