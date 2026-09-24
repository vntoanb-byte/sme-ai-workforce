"""Kiểm thử bộ lập lịch: đồng bộ lịch cron từ DB, kích hoạt run, theo dõi thư mục."""

from __future__ import annotations

from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.run import JobQueueEntry, Run
from app.services import employee_service
from app.workers.scheduler import (
    build_scheduler,
    create_scheduled_run,
    sync_schedules,
    watch_folders,
)
from tests.conftest import png_bytes


def _cron_jobs(scheduler: BackgroundScheduler) -> dict[str, str]:
    return {j.id: j.kwargs["cron_expr"] for j in scheduler.get_jobs() if j.id.startswith("cron:")}


def test_sync_schedules_follows_database(
    db: Session, queue, session_factory, make_employee
) -> None:
    active = make_employee(trigger={"type": "cron", "cron_expr": "0 8 * * *"})
    make_employee(
        name="Chưa duyệt", trigger={"type": "cron", "cron_expr": "0 9 * * *"}, approve=False
    )
    make_employee(name="Thủ công")  # manual — không có job cron
    scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

    sync_schedules(scheduler, session_factory, queue)
    jobs = _cron_jobs(scheduler)
    assert list(jobs.values()) == ["0 8 * * *"]

    employee_service.update(db, db.get(type(active), active.id), status="paused")
    db.commit()
    sync_schedules(scheduler, session_factory, queue)
    assert _cron_jobs(scheduler) == {}


def test_create_scheduled_run_enqueues_once(
    db: Session, queue, session_factory, make_employee
) -> None:
    employee = make_employee(trigger={"type": "cron", "cron_expr": "0 8 * * *"})
    schedule_id = employee.current_workflow.schedule.id
    run_id = create_scheduled_run(session_factory, queue, schedule_id, "cron")
    assert run_id is not None
    # Lần trước chưa xong → bỏ qua, không chạy chồng.
    assert create_scheduled_run(session_factory, queue, schedule_id, "cron") is None
    db.expire_all()
    run = db.get(Run, run_id)
    assert run is not None and run.trigger_type == "cron" and run.created_by is None
    assert db.scalar(select(JobQueueEntry.run_id)) == run_id


def test_watch_folders_triggers_on_new_files(
    db: Session, queue, session_factory, make_employee, scan_dir: Path
) -> None:
    make_employee(trigger={"type": "file_watch", "watch_path": str(scan_dir)})
    assert watch_folders(session_factory, queue) == []
    (scan_dir / "moi.png").write_bytes(png_bytes(3))
    (scan_dir / "ghichu.txt").write_bytes(b"x")
    created = watch_folders(session_factory, queue)
    assert len(created) == 1
    db.expire_all()
    assert db.get(Run, created[0]).trigger_type == "file_watch"  # type: ignore[union-attr]


def test_build_scheduler_registers_housekeeping_jobs(queue, session_factory) -> None:
    scheduler = build_scheduler(session_factory, queue)
    assert {j.id for j in scheduler.get_jobs()} == {"sync_schedules", "watch_folders", "reaper"}
