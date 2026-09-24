"""
DTO lần chạy

RunCreate, RunOut, RunDetail, RunStepOut, RunOutput, LogLine.
Trạng thái trả ra CHỮ HOA (frontend RunStatus); DB và domain/state dùng chữ
thường.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.common import Money, UtcDateTime
from app.schemas.employee import RunStatusUpper


class RunCreate(BaseModel):
    employee_id: int


class RunOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    trigger_type: Literal["manual", "cron", "file_watch"]
    status: RunStatusUpper
    doc_count: int
    started_at: UtcDateTime | None
    finished_at: UtcDateTime | None
    error_message: str | None


class RunStepOut(BaseModel):
    step_key: str
    label: str
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED"]
    detail: str | None
    duration_ms: int | None


class RunStats(BaseModel):
    read: int
    passed: int
    needs_review: int
    total_amount: Money


class RunOutput(BaseModel):
    artifact_id: int
    filename: str | None
    step_key: str | None
    download_url: str


class RunDetail(RunOut):
    workflow_id: int
    steps: list[RunStepOut]
    stats: RunStats
    outputs: list[RunOutput]


class LogLine(BaseModel):
    id: int
    ts: str
    level: Literal["DEBUG", "INFO", "WARN", "ERROR"]
    message: str
