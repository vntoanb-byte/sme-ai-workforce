"""
Thu hồi công việc treo

Đưa các job đã quá hạn giữ (worker chết/treo) về trạng thái chờ để worker
khác nhận lại, rồi sửa trạng thái lần chạy tương ứng cho nhất quán:
  - job về pending  → run RUNNING chuyển RETRYING (sẽ được giành lại);
  - job hết lượt (attempts >= max_attempts, adapter chuyển 'failed') → run
    FAILED kèm lý do "hết hạn giữ việc".
Bất biến dùng để phát hiện: run ở CLAIMED/RUNNING thì job mới nhất của nó
phải đang 'claimed'.
"""

from __future__ import annotations

from collections.abc import Callable

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.state import InvalidTransitionError, RunStatus, transition
from app.models.run import JobQueueEntry, Run
from app.ports.queue import JobQueue
from app.services import run_service

logger = structlog.get_logger(__name__)


def reap(queue: JobQueue, session_factory: Callable[[], Session]) -> int:
    reclaimed = queue.reap_expired()
    repaired = 0
    with session_factory() as db:
        runs = db.scalars(
            select(Run).where(Run.status.in_((RunStatus.CLAIMED.value, RunStatus.RUNNING.value)))
        ).all()
        for run in runs:
            job = db.scalar(
                select(JobQueueEntry)
                .where(JobQueueEntry.run_id == run.id)
                .order_by(JobQueueEntry.id.desc())
                .limit(1)
            )
            if job is None or job.status == "claimed":
                continue
            log_fn = run_service.transition_logger(db)
            try:
                if job.status == "failed":
                    transition(run, RunStatus.FAILED, "Hết hạn giữ việc và đã hết lượt thử", log_fn)
                    run.error_message = job.last_error or "Hết hạn giữ việc"
                elif RunStatus(run.status) == RunStatus.RUNNING:
                    transition(
                        run, RunStatus.RETRYING,
                        "Tiến trình xử lý bị gián đoạn (hết hạn giữ việc) — sẽ thử lại", log_fn,
                    )
                else:
                    continue  # CLAIMED + job pending: worker kế tiếp tự chạy tiếp
                repaired += 1
            except InvalidTransitionError:
                continue
        db.commit()
    if reclaimed or repaired:
        logger.info("reaper.reaped", jobs=reclaimed, runs_repaired=repaired)
    return reclaimed
