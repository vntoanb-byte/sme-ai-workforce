"""
DTO nhân viên AI và quy trình

EmployeeCreate, EmployeeUpdate, EmployeeOut, WorkflowOut, CompileResult.
template_code ra ngoài dạng 'TPL_...' (khớp frontend), xem
services/workflow_service.py.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import OutModel, UtcDateTime

EmployeeStatus = Literal["draft", "active", "paused", "archived"]
RunStatusUpper = Literal[
    "PENDING", "CLAIMED", "RUNNING", "RETRYING", "NEEDS_REVIEW", "SUCCEEDED", "FAILED", "CANCELLED"
]


class EmployeeCreate(BaseModel):
    name: str = Field(default="", max_length=200)
    job_description: str = Field(min_length=1, max_length=4000)


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    status: Literal["active", "paused", "archived"] | None = None


class EmployeeOut(OutModel):
    id: int
    name: str
    job_description: str
    status: EmployeeStatus
    schedule_label: str | None
    next_run_at: UtcDateTime | None
    last_run_at: UtcDateTime | None
    last_run_status: RunStatusUpper | None
    runs_30d: int
    created_at: UtcDateTime
    workflow_id: int | None


class TriggerOut(BaseModel):
    type: Literal["manual", "cron", "file_watch"]
    label: str
    cron_expr: str | None = None
    watch_path: str | None = None
    timezone: str | None = None


class WorkflowStepOut(BaseModel):
    step_key: str
    order_index: int
    tool_code: str
    label: str
    config: dict[str, Any]
    on_error: str
    retry_max: int
    branch: Literal["pass", "fail"] | None = None


class WorkflowEdgeOut(BaseModel):
    from_key: str
    to_key: str
    condition: str | None


class WorkflowOut(BaseModel):
    id: int
    employee_id: int
    version: int
    status: Literal["pending", "approved", "archived"]
    name: str
    description: str | None
    template_code: str
    trigger: TriggerOut
    steps: list[WorkflowStepOut]
    edges: list[WorkflowEdgeOut]
    approved_at: UtcDateTime | None


class SpecErrorOut(BaseModel):
    rule: str
    step_key: str | None
    message: str


class CompileResult(BaseModel):
    ok: bool
    workflow: WorkflowOut | None = None
    errors: list[SpecErrorOut] = []


class ValidateResult(BaseModel):
    ok: bool
    errors: list[SpecErrorOut] = []


class ToolOut(BaseModel):
    code: str
    name: str
    category: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_params: list[str]
