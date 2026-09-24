"""
Dịch vụ nhân viên AI

Tạo (qua bộ biên dịch), cập nhật, bật/tắt, lưu trữ nhân viên AI.

  - create(): biên dịch mô tả; CHỈ lưu nhân viên + quy trình nháp khi biên dịch
    thành công (người dùng sửa mô tả rồi thử lại không sinh ra nhân viên rác).
  - activate chỉ cho phép khi đã có quy trình được duyệt.
  - Bật/tắt đồng bộ cờ schedules.is_enabled; bộ lập lịch (tiến trình worker)
    đọc lại bảng schedules mỗi phút nên không cần gọi chéo tiến trình.
  - Không xoá thật — DELETE chỉ đánh dấu archived.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models.employee import AIEmployee
from app.models.run import Run
from app.models.workflow import Workflow
from app.ports.llm import LLMProvider
from app.services import compiler_service, workflow_service
from app.services.compiler_service import CompileOutcome


def get(db: Session, employee_id: int) -> AIEmployee:
    employee = db.get(AIEmployee, employee_id)
    if employee is None:
        raise NotFound("Không tìm thấy nhân viên AI.")
    return employee


def create(
    db: Session, llm: LLMProvider, name: str, job_description: str, user_id: int | None
) -> tuple[CompileOutcome, Workflow | None]:
    if len(job_description.strip()) < 15:
        raise ValidationFailed("Mô tả công việc quá ngắn — hãy mô tả cụ thể hơn.")
    outcome = compiler_service.compile_text(db, llm, job_description, user_id)
    if not outcome.ok or outcome.spec is None:
        return outcome, None
    employee = AIEmployee(
        name=name.strip() or outcome.spec.name,
        job_description=job_description.strip(),
        status="draft",
        created_by=user_id,
    )
    db.add(employee)
    db.flush()
    workflow = workflow_service.save_new_version(db, employee, outcome.spec)
    return outcome, workflow


def update(
    db: Session, employee: AIEmployee, *, name: str | None = None, status: str | None = None
) -> AIEmployee:
    if name is not None:
        if not name.strip():
            raise ValidationFailed("Tên nhân viên AI không được để trống.")
        employee.name = name.strip()
    if status is not None and status != employee.status:
        if employee.status == "archived":
            raise Conflict("Nhân viên AI đã lưu trữ, không thể thay đổi trạng thái.")
        if status == "active":
            if employee.current_workflow_id is None:
                raise Conflict("Cần duyệt quy trình trước khi bật nhân viên AI.")
        elif status not in ("paused", "archived"):
            raise ValidationFailed(f"Trạng thái '{status}' không hợp lệ.")
        employee.status = status
        workflow_service.sync_schedule_enabled(employee)
    db.flush()
    return employee


def archive(db: Session, employee: AIEmployee) -> AIEmployee:
    employee.status = "archived"
    workflow_service.sync_schedule_enabled(employee)
    db.flush()
    return employee


def _schedule_info(employee: AIEmployee) -> tuple[str | None, datetime | None]:
    wf = employee.current_workflow
    if wf is None or wf.schedule is None or wf.schedule.trigger_type == "manual":
        return None, None
    schedule = wf.schedule
    label = workflow_service.trigger_label(
        schedule.trigger_type, schedule.cron_expr, schedule.watch_path
    )
    next_run = None
    if employee.status == "active" and schedule.trigger_type == "cron":
        next_run = workflow_service.next_fire_time(schedule.cron_expr, schedule.timezone)
    return label, next_run


def employee_out(db: Session, employee: AIEmployee) -> dict[str, Any]:
    last_run = db.scalar(
        select(Run).where(Run.employee_id == employee.id).order_by(Run.id.desc()).limit(1)
    )
    since = datetime.now(UTC) - timedelta(days=30)
    runs_30d = db.scalar(
        select(func.count(Run.id)).where(Run.employee_id == employee.id, Run.created_at >= since)
    )
    label, next_run = _schedule_info(employee)
    workflow = workflow_service.latest_workflow(employee)
    return {
        "id": employee.id,
        "name": employee.name,
        "job_description": employee.job_description,
        "status": employee.status,
        "schedule_label": label,
        "next_run_at": next_run,
        "last_run_at": (last_run.started_at or last_run.created_at) if last_run else None,
        "last_run_status": last_run.status.upper() if last_run else None,
        "runs_30d": runs_30d or 0,
        "created_at": employee.created_at,
        "workflow_id": workflow.id if workflow else None,
    }


def list_employees(
    db: Session, *, status: str | None, q: str | None, page: int, page_size: int
) -> tuple[list[AIEmployee], int]:
    stmt = select(AIEmployee)
    if status:
        stmt = stmt.where(AIEmployee.status == status)
    else:
        stmt = stmt.where(AIEmployee.status != "archived")
    if q:
        stmt = stmt.where(AIEmployee.name.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AIEmployee.id.desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return list(rows), total
