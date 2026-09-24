"""
Bộ lập lịch

APScheduler (BackgroundScheduler, múi giờ TIMEZONE — mặc định Asia/Ho_Chi_Minh)
chạy trong tiến trình worker:
  1. sync_schedules — mỗi phút đối chiếu bảng schedules (nguồn sự thật) với
     các job cron đang đăng ký: thêm/đổi/bỏ. Nhờ vậy bật/tắt nhân viên từ API
     (tiến trình khác) có hiệu lực trong ≤ 1 phút mà không cần gọi chéo tiến trình.
  2. Mỗi lịch cron đang bật: tới giờ thì tạo run (trigger 'cron') + enqueue.
  3. watch_folders — mỗi phút quét thư mục của các lịch 'file_watch', có tệp
     mới (so với lần chạy thành công trước) thì tạo run (trigger 'file_watch').
  4. reaper.reap() mỗi phút.

Quyết định hiện thực: dùng MemoryJobStore thay cho SQLAlchemyJobStore trong
docstring gốc — lịch đã nằm sẵn trong bảng schedules và được dựng lại mỗi phút,
nên lưu thêm bản pickle của APScheduler vào DB chỉ tạo hai nguồn sự thật có
thể lệch nhau.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict
from app.domain.state import RunStatus
from app.models.employee import AIEmployee, Schedule
from app.models.run import Run
from app.models.workflow import Workflow
from app.ports.queue import JobQueue
from app.services import run_service, workflow_service
from app.tools.fs_tools import has_new_files
from app.workers.reaper import reap

logger = structlog.get_logger(__name__)
SessionFactory = Callable[[], Session]
_CRON_PREFIX = "cron:"


def _active_schedules(db: Session, trigger_type: str) -> list[Schedule]:
    return list(
        db.scalars(
            select(Schedule)
            .join(Workflow, Workflow.id == Schedule.workflow_id)
            .join(AIEmployee, AIEmployee.current_workflow_id == Workflow.id)
            .where(
                Schedule.is_enabled.is_(True),
                Schedule.trigger_type == trigger_type,
                AIEmployee.status == "active",
            )
        )
    )


def create_scheduled_run(
    session_factory: SessionFactory, queue: JobQueue, schedule_id: int, trigger_type: str
) -> int | None:
    """Tạo run cho một lịch; trả về run_id hoặc None nếu bỏ qua."""
    with session_factory() as db:
        schedule = db.get(Schedule, schedule_id)
        if schedule is None or not schedule.is_enabled:
            return None
        employee = schedule.workflow.employee
        if employee.status != "active" or employee.current_workflow_id != schedule.workflow_id:
            return None
        try:
            run = run_service.create_run(
                db, queue, employee, trigger_type=trigger_type, user_id=None
            )
        except Conflict as exc:
            logger.info("scheduler.skip", schedule_id=schedule_id, reason=exc.message)
            return None
        schedule.next_run_at = workflow_service.next_fire_time(
            schedule.cron_expr, schedule.timezone
        )
        db.commit()
        logger.info("scheduler.run_created", schedule_id=schedule_id, run_id=run.id)
        return run.id


def sync_schedules(
    scheduler: BackgroundScheduler, session_factory: SessionFactory, queue: JobQueue
) -> None:
    with session_factory() as db:
        wanted = {
            f"{_CRON_PREFIX}{s.id}": (s.id, s.cron_expr or "", s.timezone or settings.TIMEZONE)
            for s in _active_schedules(db, "cron")
            if s.cron_expr
        }
    current = {job.id: job for job in scheduler.get_jobs() if job.id.startswith(_CRON_PREFIX)}
    for job_id, job in current.items():
        if job_id not in wanted or job.kwargs.get("cron_expr") != wanted[job_id][1]:
            scheduler.remove_job(job_id)
    existing = {job.id for job in scheduler.get_jobs()}
    for job_id, (schedule_id, cron_expr, tz) in wanted.items():
        if job_id in existing:
            continue
        try:
            trigger = CronTrigger.from_crontab(cron_expr, timezone=ZoneInfo(tz))
        except ValueError:
            logger.warning("scheduler.bad_cron", schedule_id=schedule_id, cron_expr=cron_expr)
            continue
        scheduler.add_job(
            _fire_cron,
            trigger,
            id=job_id,
            kwargs={
                "session_factory": session_factory,
                "queue": queue,
                "schedule_id": schedule_id,
                "cron_expr": cron_expr,
            },
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
        )


def _fire_cron(
    session_factory: SessionFactory, queue: JobQueue, schedule_id: int, cron_expr: str
) -> None:
    create_scheduled_run(session_factory, queue, schedule_id, "cron")


def watch_folders(session_factory: SessionFactory, queue: JobQueue) -> list[int]:
    created: list[int] = []
    with session_factory() as db:
        targets = []
        for schedule in _active_schedules(db, "file_watch"):
            employee = schedule.workflow.employee
            last = db.scalar(
                select(Run.started_at)
                .where(
                    Run.employee_id == employee.id,
                    Run.status.in_((RunStatus.SUCCEEDED.value, RunStatus.NEEDS_REVIEW.value)),
                )
                .order_by(Run.started_at.desc())
                .limit(1)
            )
            extensions = None
            for step in schedule.workflow.steps:
                if step.tool_code == "fs.list_new_files":
                    extensions = json.loads(step.config_json or "{}").get("extensions")
            since = last or schedule.created_at
            if schedule.watch_path and has_new_files(schedule.watch_path, extensions, since):
                targets.append(schedule.id)
    for schedule_id in targets:
        run_id = create_scheduled_run(session_factory, queue, schedule_id, "file_watch")
        if run_id is not None:
            created.append(run_id)
    return created


def build_scheduler(session_factory: SessionFactory, queue: JobQueue) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=ZoneInfo(settings.TIMEZONE))
    now = datetime.now(UTC)
    scheduler.add_job(
        sync_schedules, "interval", seconds=60, id="sync_schedules", next_run_time=now,
        args=(scheduler, session_factory, queue), coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        watch_folders, "interval", seconds=60, id="watch_folders",
        args=(session_factory, queue), coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        reap, "interval", seconds=60, id="reaper", next_run_time=now,
        args=(queue, session_factory), coalesce=True, max_instances=1,
    )
    return scheduler
