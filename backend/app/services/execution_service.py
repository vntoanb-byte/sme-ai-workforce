"""
Dịch vụ thực thi một lần chạy

Điều phối toàn bộ vòng đời của một lần chạy: đọc quy trình, chạy từng bước
(qua crew tuần tự — agents/crew.py), ghi trạng thái và nhật ký, xử lý lỗi và
quyết định có thử lại hay không.

  execute(db, storage, llm, run_id) — hàm public duy nhất, được worker gọi khi
  run đang ở CLAIMED. Kết quả:
    - SUCCEEDED: mọi bước xong, không còn chứng từ chờ xác nhận.
    - NEEDS_REVIEW: bước QC tách được chứng từ không đạt — nhánh ĐẠT vẫn chạy
      tiếp cho chứng từ đạt (không bắt chứng từ tốt chờ chứng từ lỗi), nhánh
      KHÔNG ĐẠT đưa chứng từ vào hàng chờ; lần chạy dừng ở NEEDS_REVIEW.
    - FAILED: lỗi vĩnh viễn ở bước có on_error=stop|retry.
    - Lỗi TẠM THỜI (mô hình quá tải, DB bận...) sau khi hết lượt thử lại tại
      chỗ (retry_max của bước): run → RETRYING và ném RunRetryable để worker
      trả job về hàng đợi với backoff (job hết lượt thì worker chuyển FAILED).

  Chạy tiếp sau xác nhận thủ công (review_service đưa run về hàng đợi): lần
  thực thi sau chỉ chạy các bước thuộc nhánh ĐẠT (và các bước phía sau nó) cho
  những chứng từ người duyệt đã chấp nhận.

Nhật ký: mỗi dòng run_logs được commit ngay để trang theo dõi (SSE, có thể ở
tiến trình khác) thấy tức thì. Hệ quả: tiến độ của công cụ cũng được lưu dần —
vì vậy mọi công cụ phải bất biến khi lặp (tools/base.py).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.crew import StepPlan, build_crew
from app.core.errors import is_transient
from app.core.logging import bind_context
from app.domain.state import InvalidTransitionError, RunStatus, transition
from app.models.artifact import Document
from app.models.extraction import Extraction, HumanReview
from app.models.run import Run, RunLog, RunStep
from app.models.workflow import WorkflowStep
from app.ports.llm import LLMProvider
from app.ports.storage import FileStorage
from app.services import run_service
from app.services.workflow_service import FAIL_CONDITIONS, PASS_CONDITIONS, topo_order
from app.tools.base import ToolContext

logger = structlog.get_logger(__name__)

_OK_OUTCOMES = {"SUCCEEDED", "FAILED_SKIPPED"}


class RunRetryable(Exception):
    """Lỗi tạm thời đã hết lượt thử tại chỗ — run đang RETRYING, worker xử lý tiếp."""


class _Cancelled(Exception):
    pass


@dataclass
class _Plan:
    step: WorkflowStep
    run_step: RunStep
    config: dict[str, Any]
    preds: list[tuple[str, str | None]]


def execute(
    db: Session,
    storage: FileStorage,
    llm: LLMProvider,
    run_id: int,
    *,
    retry_delay: float = 2.0,
) -> RunStatus:
    run = run_service.get(db, run_id)
    log_fn = run_service.transition_logger(db)
    bind_context(run_id=run.id)
    if RunStatus(run.status) != RunStatus.CLAIMED:
        return RunStatus(run.status)

    resume = _reached_review(db, run)
    transition(
        run,
        RunStatus.RUNNING,
        "Chạy tiếp các bước còn lại sau khi đã xác nhận" if resume else "Bắt đầu thực thi",
        log_fn,
    )
    run.started_at = run.started_at or datetime.now(UTC)
    run.error_message = None
    db.commit()

    plans = _plans(db, run)
    order = list(plans)
    crew = build_crew([StepPlan(k, plans[k].step.tool_code, plans[k].config) for k in order])
    resume_keys = _downstream_of_pass(plans) if resume else set(order)

    state: dict[str, Any] = {}
    if resume:
        state["passed_document_ids"] = _reviewed_ok_documents(db, run)
    outcome: dict[str, str] = {}
    since = _previous_success_at(db, run)

    try:
        for index, key in enumerate(order, start=1):
            plan = plans[key]
            if key not in resume_keys:
                outcome[key] = plan.run_step.status
                continue
            _ensure_not_cancelled(db, run)
            result = _run_step(
                db, storage, llm, run, crew.task(key), plan, index, state, outcome, since,
                retry_delay,
            )
            if result is not None:
                return result
        return _finish(db, run, state, resume, log_fn)
    except _Cancelled:
        _log(db, run, "WARN", "Lần chạy đã bị huỷ — dừng trước bước tiếp theo")
        return RunStatus.CANCELLED


def _run_step(
    db: Session,
    storage: FileStorage,
    llm: LLMProvider,
    run: Run,
    task: Any,
    plan: _Plan,
    index: int,
    state: dict[str, Any],
    outcome: dict[str, str],
    since: datetime | None,
    retry_delay: float,
) -> RunStatus | None:
    """Chạy một bước; trả về trạng thái kết thúc nếu lần chạy phải dừng."""
    key, rs, step = plan.step.step_key, plan.run_step, plan.step
    if plan.preds and any(outcome.get(p) not in _OK_OUTCOMES for p, _ in plan.preds):
        _mark(db, rs, "SKIPPED", "Bước trước không hoàn thành", None)
        outcome[key] = "SKIPPED"
        return None

    inputs = dict(state)
    condition = next((c.lower() for _, c in plan.preds if c), None)
    if condition in PASS_CONDITIONS:
        inputs["document_ids"] = state.get("passed_document_ids", [])
    elif condition in FAIL_CONDITIONS:
        inputs["document_ids"] = state.get("review_document_ids", [])
    required = task.tool.input_schema.get("required", [])
    if any(not inputs.get(name) for name in required):
        _mark(db, rs, "SKIPPED", "Không có dữ liệu đầu vào", None)
        outcome[key] = "SKIPPED"
        _log(db, run, "INFO", f"[bước {index}] {rs.label} — bỏ qua (không có dữ liệu đầu vào)")
        return None

    _mark(db, rs, "RUNNING", None, None)
    _log(db, run, "INFO", f"[bước {index}] {rs.label} ({task.agent.role} · {step.tool_code})")
    ctx = ToolContext(
        db=db,
        storage=storage,
        llm=llm,
        run_id=run.id,
        employee_id=run.employee_id,
        step_key=key,
        since=since,
        log=lambda level, message: _log(db, run, level, f"[bước {index}] {message}"),
    )
    bind_context(step_key=key)
    max_attempts = 1 + (step.retry_max if step.on_error == "retry" else 0)
    started = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        try:
            result = task.execute(ctx, inputs)
            db.flush()
            break
        except Exception as exc:  # noqa: BLE001 — phân loại lỗi ngay bên dưới
            db.rollback()
            transient = is_transient(exc)
            if transient and attempt < max_attempts:
                _log(
                    db, run, "WARN",
                    f"[bước {index}] lỗi tạm thời: {exc} — "
                    f"thử lại lần {attempt + 1}/{max_attempts}",
                )
                time.sleep(retry_delay * attempt)
                continue
            duration = int((time.monotonic() - started) * 1000)
            _mark(db, rs, "FAILED", str(exc)[:500], duration)
            _log(db, run, "ERROR", f"[bước {index}] {rs.label} lỗi: {exc}")
            logger.warning("execution.step_failed", step_key=key, error=str(exc))
            if transient:
                _refresh_status(db, run)
                transition(
                    run, RunStatus.RETRYING, f"Lỗi tạm thời ở bước '{rs.label}': {exc}",
                    run_service.transition_logger(db),
                )
                run.error_message = str(exc)[:1000]
                db.commit()
                raise RunRetryable(str(exc)) from exc
            if step.on_error == "skip":
                outcome[key] = "FAILED_SKIPPED"
                _log(db, run, "WARN", f"[bước {index}] bỏ qua lỗi theo cấu hình (on_error=skip)")
                return None
            _refresh_status(db, run)
            transition(
                run, RunStatus.FAILED, f"Bước '{rs.label}' lỗi: {exc}",
                run_service.transition_logger(db),
            )
            run.error_message = str(exc)[:1000]
            run.finished_at = datetime.now(UTC)
            db.commit()
            return RunStatus.FAILED

    duration = int((time.monotonic() - started) * 1000)
    state.update(result.outputs)
    outcome[key] = "SUCCEEDED"
    _mark(db, rs, "SUCCEEDED", result.detail, duration)
    _log(db, run, "INFO", f"[bước {index}] xong — {result.detail or 'hoàn tất'}")
    return None


def _finish(
    db: Session, run: Run, state: dict[str, Any], resume: bool, log_fn: Any
) -> RunStatus:
    review_ids = state.get("review_document_ids") or []
    try:
        _refresh_status(db, run)
        if review_ids and not resume:
            transition(
                run, RunStatus.NEEDS_REVIEW,
                f"{len(review_ids)} chứng từ không đạt kiểm tra — chờ người xác nhận",
                log_fn,
            )
        else:
            transition(run, RunStatus.SUCCEEDED, "Hoàn tất lần chạy", log_fn)
    except InvalidTransitionError:
        db.rollback()
        return RunStatus(run.status)
    run.finished_at = datetime.now(UTC)
    db.commit()
    return RunStatus(run.status)


# ─── Hỗ trợ ───


def _plans(db: Session, run: Run) -> dict[str, _Plan]:
    """Các bước của phiên bản workflow mà run này chạy, theo thứ tự tô-pô; tạo
    bản chụp run_steps (PENDING) ở lần thực thi đầu."""
    wf = run.workflow
    steps = sorted(wf.steps, key=lambda s: (s.order_index, s.id))
    edges = [(e.from_key, e.to_key) for e in wf.edges]
    order = topo_order([s.step_key for s in steps], edges)
    by_key = {s.step_key: s for s in steps}
    existing = {rs.step_key: rs for rs in run.steps}
    for key in order:
        if key not in existing:
            existing[key] = RunStep(
                step_key=key,
                order_index=by_key[key].order_index,
                label=by_key[key].label,
                status="PENDING",
            )
            run.steps.append(existing[key])
    db.commit()
    preds: dict[str, list[tuple[str, str | None]]] = {k: [] for k in order}
    for e in wf.edges:
        preds[e.to_key].append((e.from_key, e.condition))
    return {
        k: _Plan(by_key[k], existing[k], json.loads(by_key[k].config_json or "{}"), preds[k])
        for k in order
    }


def _downstream_of_pass(plans: dict[str, _Plan]) -> set[str]:
    """Các bước nằm trên nhánh ĐẠT (đích của cạnh 'pass') và mọi bước phía sau."""
    children: dict[str, list[str]] = {k: [] for k in plans}
    roots: list[str] = []
    for key, plan in plans.items():
        for parent, condition in plan.preds:
            children[parent].append(key)
            if condition and condition.lower() in PASS_CONDITIONS:
                roots.append(key)
    seen: set[str] = set()
    stack = roots
    while stack:
        key = stack.pop()
        if key not in seen:
            seen.add(key)
            stack.extend(children[key])
    return seen


def _reached_review(db: Session, run: Run) -> bool:
    return (
        db.scalar(
            select(RunLog.id)
            .where(RunLog.run_id == run.id, RunLog.to_status == RunStatus.NEEDS_REVIEW.value)
            .limit(1)
        )
        is not None
    )


def _reviewed_ok_documents(db: Session, run: Run) -> list[int]:
    """Chứng từ của run đã được người duyệt chấp nhận (approve/correct)."""
    rows = db.scalars(
        select(Document.id)
        .join(Extraction, Extraction.document_id == Document.id)
        .join(HumanReview, HumanReview.document_id == Document.id)
        .where(
            Extraction.run_id == run.id,
            Document.status == "ok",
            HumanReview.action.in_(("approve", "correct")),
        )
        .distinct()
        .order_by(Document.id)
    ).all()
    return list(rows)


def _previous_success_at(db: Session, run: Run) -> datetime | None:
    return db.scalar(
        select(Run.started_at)
        .where(
            Run.employee_id == run.employee_id,
            Run.id != run.id,
            Run.status.in_((RunStatus.SUCCEEDED.value, RunStatus.NEEDS_REVIEW.value)),
            Run.started_at.is_not(None),
        )
        .order_by(Run.started_at.desc())
        .limit(1)
    )


def _mark(db: Session, rs: RunStep, status: str, detail: str | None, duration: int | None) -> None:
    rs.status = status
    rs.detail = detail
    rs.duration_ms = duration
    db.commit()


def _log(db: Session, run: Run, level: str, message: str) -> None:
    run_service.log_run(db, run, level, message)
    db.commit()


def _refresh_status(db: Session, run: Run) -> None:
    db.refresh(run, attribute_names=["status"])


def _ensure_not_cancelled(db: Session, run: Run) -> None:
    _refresh_status(db, run)
    if RunStatus(run.status) == RunStatus.CANCELLED:
        raise _Cancelled()
