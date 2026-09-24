"""
Điểm cuối lần chạy

  POST /runs             — kích hoạt thủ công một nhân viên AI, trả về {id}
  GET  /runs             — phân trang, lọc theo employee_id, status, from/to
  GET  /runs/{id}        — chi tiết kèm run_steps, thống kê, tệp kết quả
  GET  /runs/{id}/logs   — text/event-stream (SSE): event 'log' mỗi dòng nhật ký,
                           event 'done' khi lần chạy không còn hoạt động
  POST /runs/{id}/cancel — huỷ lần chạy chưa kết thúc
Kích hoạt/huỷ: MANAGER/ADMIN. Xem: mọi người dùng.

SSE đọc bảng run_logs (worker ghi và commit từng dòng) nên chạy đúng khi worker
là tiến trình khác. Hỗ trợ header Last-Event-ID để nối lại không mất dòng.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, DbSession, ManagerUser, Queue, SessionFactory
from app.models.run import Run
from app.schemas.common import IdResponse, Page, iso_utc
from app.schemas.run import RunCreate, RunDetail, RunOut
from app.services import employee_service, run_service

router = APIRouter()

SSE_POLL_SECONDS = 1.0
SSE_PING_SECONDS = 15.0


@router.post("", response_model=IdResponse, status_code=201)
def trigger_run(body: RunCreate, db: DbSession, queue: Queue, user: ManagerUser) -> dict[str, int]:
    employee = employee_service.get(db, body.employee_id)
    run = run_service.create_run(db, queue, employee, trigger_type="manual", user_id=user.id)
    db.commit()
    return {"id": run.id}


@router.get("", response_model=Page[RunOut])
def list_runs(
    db: DbSession,
    _user: CurrentUser,
    employee_id: int | None = None,
    status: str | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    items, total = run_service.list_runs(
        db,
        employee_id=employee_id,
        status=run_service.validate_status_filter(status),
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: int, db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    return run_service.run_detail(db, run_service.get(db, run_id))


@router.post("/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: int, db: DbSession, user: ManagerUser) -> dict[str, Any]:
    run = run_service.cancel_run(db, run_service.get(db, run_id), user.full_name)
    db.commit()
    return run_service.run_row(db, run)


def _poll(
    session_factory: Callable[[], Session], run_id: int, after_id: int
) -> tuple[list[dict[str, Any]], bool]:
    with session_factory() as db:
        logs = run_service.logs_after(db, run_id, after_id)
        run = db.get(Run, run_id)
        active = run is not None and run.status in run_service.ACTIVE_STATUSES
        return (
            [
                {"id": log.id, "ts": iso_utc(log.created_at), "level": log.level,
                 "message": log.message}
                for log in logs
            ],
            active,
        )


def _event(name: str, data: Any, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/{run_id}/logs")
async def stream_logs(
    run_id: int,
    request: Request,
    session_factory: SessionFactory,
    db: DbSession,
    _user: CurrentUser,
) -> StreamingResponse:
    await run_in_threadpool(run_service.get, db, run_id)  # 404 nếu không có
    try:
        after = int(request.headers.get("last-event-id", "0"))
    except ValueError:
        after = 0

    async def events() -> AsyncIterator[str]:
        last_id = after
        idle = 0.0
        yield "retry: 3000\n\n"
        while True:
            lines, active = await run_in_threadpool(_poll, session_factory, run_id, last_id)
            for line in lines:
                last_id = line["id"]
                yield _event("log", line, line["id"])
            if not lines and not active:
                yield _event("done", {"run_id": run_id})
                return
            if await request.is_disconnected():
                return
            if lines:
                continue  # còn dòng tồn — đọc tiếp ngay
            await asyncio.sleep(SSE_POLL_SECONDS)
            idle += SSE_POLL_SECONDS
            if idle >= SSE_PING_SECONDS:
                idle = 0.0
                yield ": ping\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
