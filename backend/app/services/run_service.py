"""
Dịch vụ lần chạy (phía API)

  - create_run(): tạo bản ghi runs + đưa job vào job_queue trong CÙNG một
    transaction (ADR-001) — không bao giờ có run thiếu job hoặc ngược lại.
  - cancel_run(): huỷ lần chạy chưa kết thúc (qua domain/state).
  - run_row / run_detail / list_runs: dữ liệu hiển thị (RunRow/RunDetail của
    frontend: trạng thái chữ HOA, thống kê chứng từ, tệp kết quả).
  - log_run(): ghi 1 dòng run_logs (log_fn cho domain/state.transition).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domain.state import RunStatus, is_terminal, transition
from app.models.artifact import Document
from app.models.audit import AuditLog
from app.models.employee import AIEmployee
from app.models.extraction import Extraction
from app.models.run import Run, RunLog
from app.ports.queue import JobQueue

ACTIVE_STATUSES = ("pending", "claimed", "running", "retrying")


def log_run(db: Session, run: Run, level: str, message: str) -> None:
    db.add(RunLog(run_id=run.id, level=level, message=message))


def transition_logger(db: Session):  # noqa: ANN201 — LogFn của domain/state
    def _log(run: Any, frm: RunStatus, to: RunStatus, reason: str, _at: datetime) -> None:
        db.add(
            RunLog(
                run_id=run.id,
                level="ERROR" if to == RunStatus.FAILED else "INFO",
                message=reason,
                from_status=frm.value,
                to_status=to.value,
            )
        )

    return _log


def get(db: Session, run_id: int) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise NotFound("Không tìm thấy lần chạy.")
    return run


def create_run(
    db: Session,
    queue: JobQueue,
    employee: AIEmployee,
    *,
    trigger_type: str,
    user_id: int | None,
) -> Run:
    """Tạo run PENDING + enqueue (caller commit). Chặn chạy chồng cùng nhân viên."""
    if employee.status == "archived":
        raise Conflict("Nhân viên AI đã lưu trữ.")
    if employee.current_workflow_id is None:
        raise Conflict("Nhân viên AI chưa có quy trình được duyệt.")
    busy = db.scalar(
        select(Run.id).where(Run.employee_id == employee.id, Run.status.in_(ACTIVE_STATUSES))
    )
    if busy is not None:
        raise Conflict(f"Nhân viên AI đang có lần chạy #{busy} chưa kết thúc.")
    run = Run(
        employee_id=employee.id,
        workflow_id=employee.current_workflow_id,
        trigger_type=trigger_type,
        status=RunStatus.PENDING.value,
        created_by=user_id,
    )
    db.add(run)
    db.flush()
    log_run(db, run, "INFO", f"Tạo lần chạy #{run.id} ({trigger_type}) — chờ tiến trình xử lý")
    queue.enqueue(db, run.id)
    return run


def cancel_run(db: Session, run: Run, user_name: str | None) -> Run:
    if is_terminal(RunStatus(run.status)):
        raise Conflict("Lần chạy đã kết thúc, không thể huỷ.")
    transition(
        run,
        RunStatus.CANCELLED,
        f"Huỷ bởi {user_name}" if user_name else "Huỷ lần chạy",
        transition_logger(db),
    )
    run.finished_at = datetime.now(UTC)
    db.flush()
    return run


# ─── Dữ liệu hiển thị ───


def _run_documents(db: Session, run_ids: list[int]) -> dict[int, list[tuple[str, Decimal | None]]]:
    """run_id → [(trạng thái chứng từ, tổng tiền extraction mới nhất)]."""
    if not run_ids:
        return {}
    ranked = select(
        Extraction.run_id.label("run_id"),
        Extraction.document_id.label("document_id"),
        Extraction.total.label("total"),
        func.row_number()
        .over(
            partition_by=(Extraction.run_id, Extraction.document_id),
            order_by=(Extraction.created_at.desc(), Extraction.id.desc()),
        )
        .label("rn"),
    ).subquery()
    rows = db.execute(
        select(ranked.c.run_id, Document.status, ranked.c.total)
        .join(Document, and_(Document.id == ranked.c.document_id, ranked.c.rn == 1))
        .where(ranked.c.run_id.in_(run_ids))
    ).all()
    out: dict[int, list[tuple[str, Decimal | None]]] = {}
    for run_id, status, total in rows:
        out.setdefault(run_id, []).append((status, total))
    return out


def _row(run: Run, docs: list[tuple[str, Decimal | None]]) -> dict[str, Any]:
    return {
        "id": run.id,
        "employee_id": run.employee_id,
        "employee_name": run.employee.name,
        "trigger_type": run.trigger_type,
        "status": run.status.upper(),
        "doc_count": len(docs),
        "started_at": run.started_at or run.created_at,
        "finished_at": run.finished_at,
        "error_message": run.error_message,
    }


def run_row(db: Session, run: Run) -> dict[str, Any]:
    return _row(run, _run_documents(db, [run.id]).get(run.id, []))


def list_runs(
    db: Session,
    *,
    employee_id: int | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(Run)
    if employee_id is not None:
        stmt = stmt.where(Run.employee_id == employee_id)
    if status:
        stmt = stmt.where(Run.status == status.lower())
    if date_from is not None:
        stmt = stmt.where(Run.created_at >= datetime.combine(date_from, time.min, UTC))
    if date_to is not None:
        stmt = stmt.where(Run.created_at <= datetime.combine(date_to, time.max, UTC))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    runs = db.scalars(
        stmt.order_by(Run.id.desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    docs = _run_documents(db, [r.id for r in runs])
    return [_row(r, docs.get(r.id, [])) for r in runs], total


def run_outputs(db: Session, run_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.action == "run.output",
            func.json_extract(AuditLog.detail_json, "$.run_id") == run_id,
        )
        .order_by(AuditLog.id)
    ).all()
    outputs = []
    for row in rows:
        detail = json.loads(row.detail_json or "{}")
        outputs.append(
            {
                "artifact_id": row.entity_id,
                "filename": detail.get("filename"),
                "step_key": detail.get("step_key"),
                "download_url": f"/api/v1/reports/{row.entity_id}/download",
            }
        )
    return outputs


def run_detail(db: Session, run: Run) -> dict[str, Any]:
    docs = _run_documents(db, [run.id]).get(run.id, [])
    return {
        **_row(run, docs),
        "workflow_id": run.workflow_id,
        "steps": [
            {
                "step_key": s.step_key,
                "label": s.label,
                "status": s.status,
                "detail": s.detail,
                "duration_ms": s.duration_ms,
            }
            for s in sorted(run.steps, key=lambda x: (x.order_index, x.id))
        ],
        "stats": {
            "read": len(docs),
            "passed": sum(1 for status, _ in docs if status == "ok"),
            "needs_review": sum(1 for status, _ in docs if status == "needs_review"),
            "total_amount": sum((t for _, t in docs if t is not None), Decimal("0")),
        },
        "outputs": run_outputs(db, run.id),
    }


def logs_after(db: Session, run_id: int, after_id: int, limit: int = 200) -> list[RunLog]:
    return list(
        db.scalars(
            select(RunLog)
            .where(RunLog.run_id == run_id, RunLog.id > after_id)
            .order_by(RunLog.id)
            .limit(limit)
        )
    )


def validate_status_filter(status: str | None) -> str | None:
    if not status:
        return None
    try:
        return RunStatus(status.lower()).value
    except ValueError as exc:
        raise ValidationFailed(f"Trạng thái '{status}' không hợp lệ.") from exc
