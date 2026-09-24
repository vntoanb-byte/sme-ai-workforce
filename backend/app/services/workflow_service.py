"""
Dịch vụ quy trình

Chuyển đổi hai chiều WorkflowSpec ⇄ bảng workflows/workflow_steps/workflow_edges,
tạo phiên bản mới (không sửa phiên bản cũ), duyệt phiên bản và đồng bộ lịch
chạy (bảng schedules — bộ lập lịch ở tiến trình worker tự đọc lại mỗi phút).

Quy ước giao diện (frontend/src/api/types.ts):
  - template_code trả ra dạng 'TPL_INVOICE_TO_EXCEL' (frontend), lưu trong DB
    và WorkflowSpec dạng 'invoice_to_excel' (backend) — chuyển đổi DUY NHẤT ở
    đây (to_api_template_code / from_api_template_code), giải quyết mâu thuẫn
    ghi trong memory.md mà không phải sửa hợp đồng của bên nào.
  - order_index = tầng tô-pô (bắt đầu từ 1): hai nhánh đạt/không đạt sau cùng
    một bước kiểm tra có cùng order_index, giao diện vẽ chúng cạnh nhau.
  - branch = 'pass' | 'fail' theo điều kiện cạnh đi vào bước.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, ValidationFailed
from app.domain.templates.registry import step_label
from app.domain.validators import SpecError, validate_spec
from app.models.employee import AIEmployee, Schedule
from app.models.workflow import Workflow, WorkflowEdge, WorkflowStep
from app.schemas.workflow_spec import EdgeSpec, StepSpec, TriggerSpec, WorkflowSpec
from app.tools.base import tool_catalog

PASS_CONDITIONS = {"pass", "success", "passed"}
FAIL_CONDITIONS = {"fail", "failed", "needs_review"}

_WEEKDAYS = {
    "0": "Chủ nhật", "1": "Thứ Hai", "2": "Thứ Ba", "3": "Thứ Tư", "4": "Thứ Năm",
    "5": "Thứ Sáu", "6": "Thứ Bảy", "7": "Chủ nhật",
    "mon": "Thứ Hai", "tue": "Thứ Ba", "wed": "Thứ Tư", "thu": "Thứ Năm",
    "fri": "Thứ Sáu", "sat": "Thứ Bảy", "sun": "Chủ nhật",
}


# ─── Mã mẫu: backend ⇄ frontend ───


def to_api_template_code(code: str) -> str:
    return code if code.startswith("TPL_") else f"TPL_{code.upper()}"


def from_api_template_code(code: str) -> str:
    return code[4:].lower() if code.startswith("TPL_") else code


# ─── Nhãn lịch chạy ───


def cron_label(expr: str | None) -> str:
    """'0 8 * * *' → 'Mỗi ngày lúc 08:00'; '0 9 * * 1' → 'Thứ Hai lúc 09:00'."""
    if not expr:
        return "Theo lịch"
    parts = expr.split()
    if len(parts) != 5:
        return f"Theo lịch ({expr})"
    minute, hour, dom, month, dow = parts
    if not (minute.isdigit() and hour.isdigit()):
        return f"Theo lịch ({expr})"
    at = f"{int(hour):02d}:{int(minute):02d}"
    if dom == "*" and month == "*":
        if dow == "*":
            return f"Mỗi ngày lúc {at}"
        if dow in ("1-5", "mon-fri"):
            return f"Thứ Hai–Thứ Sáu lúc {at}"
        days = [_WEEKDAYS.get(d.lower()) for d in dow.split(",")]
        if all(days):
            return f"{', '.join(d for d in days if d)} lúc {at}"
    if dom.isdigit() and month == "*" and dow == "*":
        return f"Ngày {int(dom)} hằng tháng lúc {at}"
    return f"Theo lịch ({expr})"


def trigger_label(trigger_type: str, cron_expr: str | None, watch_path: str | None) -> str:
    if trigger_type == "cron":
        return cron_label(cron_expr)
    if trigger_type == "file_watch":
        return f"Khi có tệp mới trong {watch_path}" if watch_path else "Khi có tệp mới"
    return "Chạy thủ công"


def next_fire_time(cron_expr: str | None, timezone: str | None) -> datetime | None:
    if not cron_expr:
        return None
    tz = ZoneInfo(timezone or settings.TIMEZONE)
    try:
        trigger = CronTrigger.from_crontab(cron_expr, timezone=tz)
    except (ValueError, KeyError):
        return None
    fire = trigger.get_next_fire_time(None, datetime.now(tz))
    return fire.astimezone(UTC) if fire else None


# ─── Tô-pô ───


def topo_levels(step_keys: Sequence[str], edges: Sequence[tuple[str, str]]) -> dict[str, int]:
    """Tầng tô-pô (1-based, theo đường dài nhất) — giả định đồ thị không chu trình
    (V-3 đã kiểm). Thứ tự khai báo phá hoà giữa các bước cùng tầng."""
    level = {k: 1 for k in step_keys}
    preds: dict[str, list[str]] = {k: [] for k in step_keys}
    for a, b in edges:
        if a in preds and b in preds:
            preds[b].append(a)
    for key in topo_order(step_keys, edges):
        for p in preds[key]:
            level[key] = max(level[key], level[p] + 1)
    return level


def topo_order(step_keys: Sequence[str], edges: Sequence[tuple[str, str]]) -> list[str]:
    """Kahn, ổn định theo thứ tự khai báo."""
    indeg = {k: 0 for k in step_keys}
    adj: dict[str, list[str]] = {k: [] for k in step_keys}
    for a, b in edges:
        if a in adj and b in indeg:
            adj[a].append(b)
            indeg[b] += 1
    position = {k: i for i, k in enumerate(step_keys)}
    ready = sorted((k for k in step_keys if indeg[k] == 0), key=position.__getitem__)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
                ready.sort(key=position.__getitem__)
    if len(order) != len(step_keys):
        raise ValidationFailed("Đồ thị quy trình chứa chu trình.")
    return order


# ─── WorkflowSpec ⇄ DB ───


def _trigger_of(wf: Workflow) -> dict[str, Any]:
    """Trigger của phiên bản lưu ở bảng schedules (1-1 với workflow)."""
    if wf.schedule is None:
        return {"type": "manual"}
    return {
        "type": wf.schedule.trigger_type,
        "cron_expr": wf.schedule.cron_expr,
        "watch_path": wf.schedule.watch_path,
        "timezone": wf.schedule.timezone,
    }


def spec_from_workflow(wf: Workflow) -> WorkflowSpec:
    return WorkflowSpec(
        template_code=wf.template_code,  # type: ignore[arg-type]
        name=wf.name,
        description=wf.description,
        trigger=TriggerSpec.model_validate(_trigger_of(wf)),
        steps=[
            StepSpec(
                step_key=s.step_key,
                tool_code=s.tool_code,
                config=json.loads(s.config_json or "{}"),
                on_error=s.on_error,  # type: ignore[arg-type]
                retry_max=s.retry_max,
            )
            for s in wf.steps
        ],
        edges=[
            EdgeSpec(from_key=e.from_key, to_key=e.to_key, condition=e.condition)
            for e in wf.edges
        ],
    )


def errors_out(errors: Sequence[SpecError]) -> list[dict[str, Any]]:
    return [{"rule": e.rule, "step_key": e.step_key, "message": e.message} for e in errors]


def validate(db: Session, spec: WorkflowSpec) -> list[SpecError]:
    return validate_spec(spec, tool_catalog(db))


def save_new_version(db: Session, employee: AIEmployee, spec: WorkflowSpec) -> Workflow:
    """Lưu spec thành phiên bản MỚI (status=pending) của nhân viên — không sửa
    phiên bản cũ. Trigger lưu vào bảng schedules (1-1 với workflow) ở trạng
    thái TẮT; chỉ bật khi phiên bản được duyệt và nhân viên đang active."""
    last_version = db.scalar(
        select(Workflow.version)
        .where(Workflow.employee_id == employee.id)
        .order_by(Workflow.version.desc())
        .limit(1)
    )
    catalog = tool_catalog(db)
    levels = topo_levels(
        [s.step_key for s in spec.steps], [(e.from_key, e.to_key) for e in spec.edges]
    )
    wf = Workflow(
        employee_id=employee.id,
        version=(last_version or 0) + 1,
        status="pending",
        template_code=spec.template_code,
        name=spec.name,
        description=spec.description,
    )
    wf.schedule = Schedule(
        trigger_type=spec.trigger.type,
        cron_expr=spec.trigger.cron_expr,
        watch_path=spec.trigger.watch_path,
        timezone=spec.trigger.timezone or settings.TIMEZONE,
        is_enabled=False,
    )
    db.add(wf)
    db.flush()
    for step in spec.steps:
        tool_name = str((catalog.get(step.tool_code) or {}).get("name") or step.tool_code)
        wf.steps.append(
            WorkflowStep(
                step_key=step.step_key,
                order_index=levels[step.step_key],
                tool_code=step.tool_code,
                label=step_label(spec.template_code, step.step_key, tool_name),
                config_json=json.dumps(step.config, ensure_ascii=False),
                on_error=step.on_error,
                retry_max=step.retry_max,
            )
        )
    for edge in spec.edges:
        wf.edges.append(
            WorkflowEdge(from_key=edge.from_key, to_key=edge.to_key, condition=edge.condition)
        )
    db.flush()
    return wf


def approve(db: Session, wf: Workflow, user_id: int | None) -> Workflow:
    """Duyệt phiên bản: lưu trữ phiên bản đã duyệt trước đó, trỏ nhân viên vào
    phiên bản này, bật nhân viên (draft → active) và tạo/cập nhật lịch chạy."""
    if wf.status == "archived":
        raise Conflict("Phiên bản quy trình này đã được lưu trữ, không thể duyệt.")
    errors = validate(db, spec_from_workflow(wf))
    if errors:
        raise ValidationFailed(
            "Quy trình chưa hợp lệ, không thể duyệt.",
            details=errors_out(errors),
        )
    employee = wf.employee
    if employee.status == "archived":
        raise Conflict("Nhân viên AI đã lưu trữ, không thể duyệt quy trình.")
    db.execute(
        update(Workflow)
        .where(
            Workflow.employee_id == wf.employee_id,
            Workflow.id != wf.id,
            Workflow.status.in_(("approved", "pending")),
        )
        .values(status="archived")
    )
    if wf.status != "approved":
        wf.status = "approved"
        wf.approved_at = datetime.now(UTC)
        wf.approved_by = user_id
    employee.current_workflow_id = wf.id
    if employee.status == "draft":
        employee.status = "active"

    if wf.schedule is None:
        wf.schedule = Schedule(trigger_type="manual", timezone=settings.TIMEZONE)
    wf.schedule.next_run_at = next_fire_time(wf.schedule.cron_expr, wf.schedule.timezone)
    sync_schedule_enabled(employee)
    db.flush()
    return wf


def sync_schedule_enabled(employee: AIEmployee) -> None:
    """Lịch chỉ bật khi nhân viên đang active — worker đọc cờ này mỗi phút."""
    for wf in employee.workflows:
        if wf.schedule is not None:
            wf.schedule.is_enabled = employee.status == "active" and (
                wf.id == employee.current_workflow_id
            )


def latest_workflow(employee: AIEmployee) -> Workflow | None:
    """Phiên bản hiện hành (đã duyệt) hoặc bản nháp mới nhất nếu chưa duyệt."""
    if employee.current_workflow is not None:
        return employee.current_workflow
    return employee.workflows[-1] if employee.workflows else None


def workflow_out(wf: Workflow) -> dict[str, Any]:
    trigger = _trigger_of(wf)
    incoming = {e.to_key: e.condition for e in wf.edges if e.condition}
    steps = []
    for s in sorted(wf.steps, key=lambda x: (x.order_index, x.id or 0)):
        item: dict[str, Any] = {
            "step_key": s.step_key,
            "order_index": s.order_index,
            "tool_code": s.tool_code,
            "label": s.label,
            "config": json.loads(s.config_json or "{}"),
            "on_error": s.on_error,
            "retry_max": s.retry_max,
        }
        condition = (incoming.get(s.step_key) or "").lower()
        if condition in PASS_CONDITIONS:
            item["branch"] = "pass"
        elif condition in FAIL_CONDITIONS:
            item["branch"] = "fail"
        steps.append(item)
    return {
        "id": wf.id,
        "employee_id": wf.employee_id,
        "version": wf.version,
        "status": wf.status,
        "name": wf.name,
        "description": wf.description,
        "template_code": to_api_template_code(wf.template_code),
        "trigger": {
            **trigger,
            "label": trigger_label(
                trigger.get("type", "manual"), trigger.get("cron_expr"), trigger.get("watch_path")
            ),
        },
        "steps": steps,
        "edges": [
            {"from_key": e.from_key, "to_key": e.to_key, "condition": e.condition}
            for e in wf.edges
        ],
        "approved_at": wf.approved_at,
    }
