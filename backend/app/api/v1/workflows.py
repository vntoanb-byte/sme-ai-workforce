"""
Điểm cuối quy trình

  GET  /workflows/{id}          — đồ thị {steps, edges} để giao diện vẽ sơ đồ
  PUT  /workflows/{id}          — nhận WorkflowSpec đã sửa, chạy lại validators,
                                  tạo phiên bản MỚI (không sửa phiên bản cũ)
  POST /workflows/{id}/approve  — chuyển approved, bật nhân viên, đăng ký lịch
  POST /workflows/{id}/validate — chỉ kiểm chứng, không lưu
template_code nhận cả dạng 'TPL_INVOICE_TO_EXCEL' lẫn 'invoice_to_excel'.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import ValidationError

from app.api.deps import CurrentUser, DbSession, ManagerUser
from app.core.errors import NotFound, ValidationFailed
from app.models.workflow import Workflow
from app.schemas.employee import ValidateResult, WorkflowOut
from app.schemas.workflow_spec import WorkflowSpec
from app.services import workflow_service

router = APIRouter()


def _get(db: DbSession, workflow_id: int) -> Workflow:
    wf = db.get(Workflow, workflow_id)
    if wf is None:
        raise NotFound("Không tìm thấy quy trình.")
    return wf


def _parse_spec(body: dict[str, Any]) -> WorkflowSpec:
    data = dict(body)
    if isinstance(data.get("template_code"), str):
        data["template_code"] = workflow_service.from_api_template_code(data["template_code"])
    try:
        return WorkflowSpec.model_validate(data)
    except ValidationError as exc:
        raise ValidationFailed(
            "Đặc tả quy trình không đúng cấu trúc.",
            details=[
                {"loc": list(e.get("loc", ())), "message": e.get("msg", "")} for e in exc.errors()
            ],
        ) from exc


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: int, db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    return workflow_service.workflow_out(_get(db, workflow_id))


@router.put("/{workflow_id}", response_model=WorkflowOut)
def update_workflow(
    workflow_id: int, body: dict[str, Any], db: DbSession, _user: ManagerUser
) -> dict[str, Any]:
    wf = _get(db, workflow_id)
    spec = _parse_spec(body)
    errors = workflow_service.validate(db, spec)
    if errors:
        raise ValidationFailed(
            "Quy trình chưa hợp lệ.", details=workflow_service.errors_out(errors)
        )
    new_wf = workflow_service.save_new_version(db, wf.employee, spec)
    db.commit()
    return workflow_service.workflow_out(new_wf)


@router.post("/{workflow_id}/approve", response_model=WorkflowOut)
def approve_workflow(
    workflow_id: int,
    db: DbSession,
    user: ManagerUser,
    employee_id: int | None = None,
) -> dict[str, Any]:
    """`employee_id` (tham số cũ của giao diện) chỉ để đối chiếu — nếu có mà
    không khớp chủ sở hữu quy trình thì từ chối."""
    wf = _get(db, workflow_id)
    if employee_id is not None and employee_id != wf.employee_id:
        raise ValidationFailed("Quy trình không thuộc nhân viên AI này.")
    workflow_service.approve(db, wf, user.id)
    db.commit()
    return workflow_service.workflow_out(wf)


@router.post("/{workflow_id}/validate", response_model=ValidateResult)
def validate_workflow(
    workflow_id: int, body: dict[str, Any], db: DbSession, _user: CurrentUser
) -> dict[str, Any]:
    _get(db, workflow_id)
    errors = workflow_service.validate(db, _parse_spec(body))
    return {"ok": not errors, "errors": workflow_service.errors_out(errors)}
