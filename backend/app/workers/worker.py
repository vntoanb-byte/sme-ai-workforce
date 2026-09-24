"""
Tiến trình xử lý nền

Vòng lặp vô hạn: giành việc từ hàng đợi, gọi execution_service, báo kết quả.
Chạy như một tiến trình riêng (`python -m app.workers.worker`):

  1. job = queue.claim(worker_id, lease); None thì ngủ JOB_POLL_INTERVAL_SEC.
  2. Luồng heartbeat gia hạn lease mỗi lease/3 giây khi job chạy lâu.
  3. Bắt MỌI ngoại lệ — worker không bao giờ chết vì một job lỗi.
  4. SIGTERM/SIGINT: hoàn tất job hiện tại rồi thoát sạch.
  5. worker_id = hostname:pid[:luồng] để truy vết.
  6. Mặc định chạy kèm bộ lập lịch (workers/scheduler.py); nhiều tiến trình
     worker thì chỉ MỘT tiến trình bật lịch (tắt bằng --no-scheduler).
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import threading
from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import bind_context, clear_context, setup_logging
from app.domain.state import InvalidTransitionError, RunStatus, is_terminal, transition
from app.models.run import Run
from app.ports.llm import LLMProvider
from app.ports.queue import Job, JobQueue
from app.ports.storage import FileStorage
from app.services import execution_service, run_service

logger = structlog.get_logger(__name__)


def default_worker_id(suffix: str | None = None) -> str:
    base = f"{socket.gethostname()}:{os.getpid()}"
    return f"{base}:{suffix}" if suffix else base


class Worker:
    def __init__(
        self,
        queue: JobQueue,
        session_factory: Callable[[], Session],
        storage: FileStorage,
        llm: LLMProvider,
        *,
        worker_id: str | None = None,
        lease_seconds: int | None = None,
        poll_interval: float | None = None,
        retry_delay: float = 2.0,
    ) -> None:
        self.queue = queue
        self.session_factory = session_factory
        self.storage = storage
        self.llm = llm
        self.worker_id = worker_id or default_worker_id()
        self.lease_seconds = lease_seconds or settings.JOB_LEASE_SECONDS
        self.poll_interval = (
            poll_interval if poll_interval is not None else settings.JOB_POLL_INTERVAL_SEC
        )
        self.retry_delay = retry_delay

    def run_forever(self, stop: threading.Event) -> None:
        logger.info("worker.started", worker_id=self.worker_id)
        while not stop.is_set():
            try:
                worked = self.process_one()
            except Exception:  # noqa: BLE001 — worker không bao giờ được chết
                logger.exception("worker.loop_error", worker_id=self.worker_id)
                worked = False
            if not worked:
                stop.wait(self.poll_interval)
        logger.info("worker.stopped", worker_id=self.worker_id)

    def process_one(self) -> bool:
        """Giành và xử lý tối đa một job. Trả về True nếu đã có job."""
        job = self.queue.claim(self.worker_id, lease_seconds=self.lease_seconds)
        if job is None:
            return False
        bind_context(worker_id=self.worker_id, job_id=job.id, run_id=job.run_id)
        try:
            self._handle(job)
        except Exception as exc:  # noqa: BLE001
            logger.exception("worker.job_crashed", error=str(exc))
            self._fail_permanently(job, f"Lỗi hệ thống: {exc}")
        finally:
            clear_context()
        return True

    def _handle(self, job: Job) -> None:
        with self.session_factory() as db:
            run = db.get(Run, job.run_id)
            if run is None or is_terminal(RunStatus(run.status)):
                self.queue.complete(job.id)
                return
            if RunStatus(run.status) != RunStatus.CLAIMED:
                try:
                    transition(
                        run, RunStatus.CLAIMED,
                        f"Tiến trình {self.worker_id} nhận việc (lần thử {job.attempts})",
                        run_service.transition_logger(db),
                    )
                except InvalidTransitionError:
                    logger.warning("worker.unexpected_run_status", status=run.status)
                    self.queue.complete(job.id)
                    return
                db.commit()

            stop_heartbeat = threading.Event()
            heartbeat = threading.Thread(
                target=self._heartbeat, args=(job.id, stop_heartbeat), daemon=True
            )
            heartbeat.start()
            try:
                execution_service.execute(
                    db, self.storage, self.llm, job.run_id, retry_delay=self.retry_delay
                )
                self.queue.complete(job.id)
            except execution_service.RunRetryable as exc:
                if job.attempts >= job.max_attempts:
                    db.rollback()
                    run = db.get(Run, job.run_id)
                    if run is not None:
                        transition(
                            run, RunStatus.FAILED,
                            f"Đã thử {job.attempts} lần vẫn lỗi tạm thời: {exc}",
                            run_service.transition_logger(db),
                        )
                        db.commit()
                self.queue.fail(job.id, str(exc))
            finally:
                stop_heartbeat.set()
                heartbeat.join(timeout=5)

    def _heartbeat(self, job_id: int, stop: threading.Event) -> None:
        interval = max(self.lease_seconds / 3, 1)
        while not stop.wait(interval):
            try:
                if not self.queue.extend_lease(
                    job_id, self.worker_id, lease_seconds=self.lease_seconds
                ):
                    logger.warning("worker.lease_lost", job_id=job_id)
                    return
            except Exception:  # noqa: BLE001
                logger.exception("worker.heartbeat_error", job_id=job_id)

    def _fail_permanently(self, job: Job, reason: str) -> None:
        """Lỗi ngoài dự kiến (lỗi lập trình/dữ liệu) — không thử lại vô ích."""
        try:
            with self.session_factory() as db:
                run = db.get(Run, job.run_id)
                if run is not None and not is_terminal(RunStatus(run.status)):
                    try:
                        transition(
                            run, RunStatus.FAILED, reason[:500], run_service.transition_logger(db)
                        )
                        run.error_message = reason[:1000]
                        db.commit()
                    except InvalidTransitionError:
                        db.rollback()
        finally:
            self.queue.fail(job.id, reason, retry=False)


def build_runtime() -> dict[str, Any]:
    from app.adapters.llm_openai_compatible import OpenAICompatibleLLM
    from app.adapters.queue_sqlite import SQLiteJobQueue
    from app.adapters.storage_local import LocalFileStorage
    from app.db.session import SessionLocal, engine

    return {
        "queue": SQLiteJobQueue(engine),
        "session_factory": SessionLocal,
        "storage": LocalFileStorage(settings.STORAGE_PATH),
        "llm": OpenAICompatibleLLM(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Tiến trình xử lý nền SME AI Workforce")
    parser.add_argument("--no-scheduler", action="store_true", help="Không chạy bộ lập lịch")
    args = parser.parse_args(argv)

    setup_logging()
    from app.db import init_db

    init_db.wait_for_schema()
    runtime = build_runtime()
    stop = threading.Event()

    def _on_signal(signum: int, _frame: Any) -> None:
        logger.info("worker.signal", signal=signum)
        stop.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    scheduler = None
    if not args.no_scheduler:
        from app.workers.scheduler import build_scheduler

        scheduler = build_scheduler(runtime["session_factory"], runtime["queue"])
        scheduler.start()

    threads = []
    for index in range(max(settings.WORKER_CONCURRENCY, 1)):
        worker = Worker(
            runtime["queue"],
            runtime["session_factory"],
            runtime["storage"],
            runtime["llm"],
            worker_id=default_worker_id(str(index) if settings.WORKER_CONCURRENCY > 1 else None),
        )
        thread = threading.Thread(target=worker.run_forever, args=(stop,), name=f"worker-{index}")
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    if scheduler is not None:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
