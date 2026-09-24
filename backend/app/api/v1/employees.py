"""
Điểm cuối quản lý nhân viên AI

  GET    /employees       — phân trang, lọc theo trạng thái, tìm theo tên
  POST   /employees       — {name, job_description} → biên dịch → CompileResult
                            (ok=false kèm danh sách lỗi khi không dựng được quy
                            trình; KHÔNG tạo nhân viên trong trường hợp đó)
  GET    /employees/{id}  — chi tiết kèm lịch chạy, workflow_id hiện hành
  PATCH  /employees/{id}  — đổi tên, bật (active), tạm dừng (paused), lưu trữ
  DELETE /employees/{id}  — chỉ đánh dấu archived, không xoá thật
Đọc: mọi người dùng. Ghi: MANAGER/ADMIN.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, Llm, ManagerUser
from app.schemas.common import Page
from app.schemas.employee import CompileResult, EmployeeCreate, EmployeeOut, EmployeeUpdate
from app.services import employee_service, workflow_service

router = APIRouter()


@router.get("", response_model=Page[EmployeeOut])
def list_employees(
    db: DbSession,
    _user: CurrentUser,
    status: Literal["draft", "active", "paused", "archived"] | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    rows, total = employee_service.list_employees(
        db, status=status, q=q, page=page, page_size=page_size
    )
    return {
        "items": [employee_service.employee_out(db, e) for e in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=CompileResult)
def create_employee(
    body: EmployeeCreate, db: DbSession, llm: Llm, user: ManagerUser
) -> dict[str, Any]:
    outcome, workflow = employee_service.create(
        db, llm, body.name, body.job_description, user.id
    )
    db.commit()
    return {
        "ok": workflow is not None,
        "workflow": workflow_service.workflow_out(workflow) if workflow else None,
        "errors": workflow_service.errors_out(outcome.errors),
    }


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    return employee_service.employee_out(db, employee_service.get(db, employee_id))


@router.patch("/{employee_id}", response_model=EmployeeOut)
def patch_employee(
    employee_id: int, body: EmployeeUpdate, db: DbSession, _user: ManagerUser
) -> dict[str, Any]:
    employee = employee_service.update(
        db, employee_service.get(db, employee_id), name=body.name, status=body.status
    )
    db.commit()
    return employee_service.employee_out(db, employee)


@router.delete("/{employee_id}", response_model=EmployeeOut)
def archive_employee(employee_id: int, db: DbSession, _user: ManagerUser) -> dict[str, Any]:
    employee = employee_service.archive(db, employee_service.get(db, employee_id))
    db.commit()
    return employee_service.employee_out(db, employee)
