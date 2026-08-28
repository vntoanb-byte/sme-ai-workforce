"""
Bộ chuyển đổi hàng đợi trên SQLite

TỆP QUAN TRỌNG NHẤT CỦA BACKEND. Hiện thực giao thức giành việc trên SQLite.
Lưu ý: SQLite KHÔNG có SELECT ... FOR UPDATE SKIP LOCKED như PostgreSQL, nên
phải dùng cách khác — xem phần claim() bên dưới.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, Row, text
from sqlalchemy.orm import Session

from app.ports.queue import Job

# NOTE (cần Owner đối chiếu): bảng job_queue CHƯA có model SQLAlchemy ORM thật
# (models/run.py vẫn là docstring stub, app/models chưa có class nào để import)
# nên file này dùng SQL thô. Lược đồ dưới đây SUY LUẬN từ các câu SQL trong
# docstring gốc — khi models/run.py + migration Alembic thật được làm, phải đối
# chiếu lại:
#
#   id INTEGER PRIMARY KEY AUTOINCREMENT
#   run_id INTEGER NOT NULL
#   status TEXT NOT NULL DEFAULT 'pending'   -- pending|claimed|failed
#   priority INTEGER NOT NULL DEFAULT 0
#   available_at TEXT NOT NULL               -- ISO8601 UTC, vd 2026-08-28T10:00:00.000000Z
#   claimed_by TEXT
#   lease_until TEXT                         -- ISO8601 UTC hoặc NULL
#   attempts INTEGER NOT NULL DEFAULT 0
#   max_attempts INTEGER NOT NULL DEFAULT 5
#   last_error TEXT
#   created_at TEXT NOT NULL                 -- ISO8601 UTC

# Định dạng CỐ ĐỊNH cho mọi cột timestamp: chuỗi sắp xếp = thời gian sắp xếp
# (SQLite không có kiểu datetime thật, so sánh chuỗi là so sánh thời gian).
_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _fmt(dt: datetime) -> str:
    """Chuyển datetime về chuỗi ISO8601 UTC (vd. 2026-08-28T10:00:00.000000Z)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime(_TIMESTAMP_FMT)


def _now_utc() -> str:
    return _fmt(datetime.now(UTC))


def _parse_datetime(value: str | None) -> datetime | None:
    """Chuyển chuỗi ISO8601 UTC (định dạng của _fmt) về datetime; NULL -> None."""
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _job_from_row(row: Row[Any]) -> Job:
    """Dựng Job từ một dòng SELECT đúng thứ tự cột của claim()."""
    return Job(
        id=int(row[0]),
        run_id=int(row[1]),
        priority=int(row[2]),
        attempts=int(row[3]),
        max_attempts=int(row[4]),
        claimed_by=row[5],
        lease_until=_parse_datetime(row[6]),
        # created_at NOT NULL — phép or chỉ để thoả type checker.
        created_at=_parse_datetime(row[7]) or datetime.now(UTC),
    )


class SQLiteJobQueue:
    """Hiện thực JobQueue trên SQLite theo giao thức ADR-001.

    Giao thức giành việc (SQLite không có SELECT ... FOR UPDATE SKIP LOCKED):
      1. Mở connection với execution_options(sqlite_begin_immediate=True) — câu
         lệnh ĐẦU TIÊN trên connection này tự kích hoạt event "begin" của
         app/db/session.py và phát ra BEGIN IMMEDIATE, khoá ghi NGAY LẬP TỨC.
         KHÔNG gọi conn.exec_driver_sql("BEGIN IMMEDIATE") sau khi connection
         đã chạy câu lệnh khác — sẽ lỗi "cannot start a transaction within a
         transaction".
      2. SELECT id ... ORDER BY priority DESC, id ASC LIMIT 1.
      3. UPDATE ... SET status='claimed' WHERE id=:id AND status='pending' rồi
         KIỂM TRA result.rowcount.
      4. rowcount == 0 -> worker khác đã giành mất giữa SELECT và UPDATE -> None.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enqueue(
        self,
        session: Session,
        run_id: int,
        *,
        priority: int = 0,
        available_at: datetime | None = None,
        max_attempts: int = 5,
    ) -> int:
        """Đưa job vào hàng đợi, trả về job_id.

        Dùng CHUNG Session/transaction với việc tạo bản ghi runs (ADR-001) —
        KHÔNG tự commit, caller chịu trách nhiệm commit cùng với runs để không
        bao giờ có run mà thiếu job hoặc ngược lại.
        """
        now = _now_utc()
        available_at_str = now if available_at is None else _fmt(available_at)
        result = session.connection().execute(
            text(
                "INSERT INTO job_queue (run_id, priority, available_at, max_attempts, created_at) "
                "VALUES (:run_id, :priority, :available_at, :max_attempts, :created_at)"
            ),
            {
                "run_id": run_id,
                "priority": priority,
                "available_at": available_at_str,
                "max_attempts": max_attempts,
                "created_at": now,
            },
        )
        return int(result.lastrowid)

    def claim(self, worker_id: str, *, lease_seconds: int = 300) -> Job | None:
        """Giành một job đang chờ cho worker (tự quản lý transaction riêng)."""
        now = datetime.now(UTC)
        now_str = _fmt(now)
        lease_until_str = _fmt(now + timedelta(seconds=lease_seconds))

        conn = self._engine.connect().execution_options(sqlite_begin_immediate=True)
        try:
            row = conn.execute(
                text(
                    "SELECT id FROM job_queue WHERE status='pending' AND available_at <= :now "
                    "ORDER BY priority DESC, id ASC LIMIT 1"
                ),
                {"now": now_str},
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            job_id = int(row[0])
            result = conn.execute(
                text(
                    "UPDATE job_queue SET status='claimed', claimed_by=:worker_id, "
                    "lease_until=:lease_until, attempts=attempts+1 "
                    "WHERE id=:job_id AND status='pending'"
                ),
                {
                    "worker_id": worker_id,
                    "lease_until": lease_until_str,
                    "job_id": job_id,
                },
            )
            if result.rowcount == 0:
                # Worker khác đã giành mất giữa bước SELECT và UPDATE (chỉ xảy
                # ra nếu giao thức BEGIN IMMEDIATE bị bỏ qua) — trả None.
                conn.commit()
                return None
            full = conn.execute(
                text(
                    "SELECT id, run_id, priority, attempts, max_attempts, claimed_by, "
                    "lease_until, created_at FROM job_queue WHERE id=:job_id"
                ),
                {"job_id": job_id},
            ).fetchone()
            if full is None:
                raise RuntimeError(f"Không đọc lại được job {job_id} sau khi claim")
            conn.commit()
            return _job_from_row(full)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def complete(self, job_id: int) -> None:
        """Đánh dấu job đã xử lý xong (tự quản lý transaction riêng)."""
        conn = self._engine.connect().execution_options(sqlite_begin_immediate=True)
        try:
            # NOTE (cần Owner xác nhận): 'succeeded' KHÔNG nằm trong 3 trạng thái
            # liệt kê ở docstring gốc (pending/claimed/failed) — suy luận cần
            # thiết vì phải có cách đánh dấu "xong, không cần xử lý lại" khác
            # với 'failed' (job lỗi) và 'pending' (chờ).
            conn.execute(
                text("UPDATE job_queue SET status='succeeded' WHERE id=:job_id"),
                {"job_id": job_id},
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fail(self, job_id: int, error: str) -> None:
        """Đánh dấu job lỗi (tự quản lý transaction riêng).

        Nếu attempts >= max_attempts: chuyển 'failed', KHÔNG thử lại nữa.
        Ngược lại: trả về 'pending' với available_at lùi ra tương lai theo
        backoff = min(30 * 2**attempts, 900) + nhiễu ngẫu nhiên nhỏ (tránh
        nhiều worker cùng dậy một lúc — module random chuẩn, không cần
        crypto-secure).
        """
        conn = self._engine.connect().execution_options(sqlite_begin_immediate=True)
        try:
            row = conn.execute(
                text("SELECT attempts, max_attempts FROM job_queue WHERE id=:job_id"),
                {"job_id": job_id},
            ).fetchone()
            if row is None:
                conn.commit()
                return
            attempts = int(row[0])
            max_attempts = int(row[1])
            now = datetime.now(UTC)
            if attempts >= max_attempts:
                conn.execute(
                    text(
                        "UPDATE job_queue SET status='failed', last_error=:error "
                        "WHERE id=:job_id"
                    ),
                    {"error": error, "job_id": job_id},
                )
            else:
                backoff = min(30 * (2**attempts), 900) + random.uniform(0, 5)
                available_at = _fmt(now + timedelta(seconds=backoff))
                conn.execute(
                    text(
                        "UPDATE job_queue SET status='pending', available_at=:available_at, "
                        "last_error=:error WHERE id=:job_id"
                    ),
                    {"available_at": available_at, "error": error, "job_id": job_id},
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reap_expired(self) -> int:
        """Thu hồi job có lease_until đã quá hạn, trả về số lượng đã thu hồi."""
        conn = self._engine.connect().execution_options(sqlite_begin_immediate=True)
        try:
            result = conn.execute(
                text(
                    "UPDATE job_queue SET status='pending' "
                    "WHERE status='claimed' AND lease_until < :now"
                ),
                {"now": _now_utc()},
            )
            conn.commit()
            return int(result.rowcount)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

