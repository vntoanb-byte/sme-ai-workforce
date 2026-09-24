"""
Điểm cuối quản trị

  GET/POST/PATCH /admin/users — quản lý tài khoản (ADMIN)
  GET/PUT /admin/settings     — cấu hình khoá–giá trị (ADMIN; khoá "secret.*" được
                                mã hoá, không bao giờ trả giá trị thật)
  GET /admin/metrics          — số chứng từ, tỷ lệ tự động, giờ công tiết kiệm,
                                hàng chờ, tình trạng mô hình, token đã dùng.
                                MỌI người dùng đăng nhập được xem (bảng điều khiển
                                và chấm đỏ thanh điều hướng dùng chung chỉ số này).
  POST /admin/llm/test        — thử kết nối tới máy chủ mô hình (ADMIN)
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession, Llm
from app.core.config import settings
from app.models.user import User
from app.ports.llm import LLMInvalidOutput, LLMTimeout, LLMUnavailable
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.services import auth_service, metrics_service, settings_service
from app.services.document_service import record_llm_call

router = APIRouter()


class LlmTestResult(BaseModel):
    ok: bool
    model: str
    base_url: str
    latency_ms: int
    error: str | None = None


@router.get("/users", response_model=list[UserOut])
def list_users(db: DbSession, _admin: AdminUser) -> list[dict[str, Any]]:
    return [auth_service.user_out(u) for u in db.scalars(select(User).order_by(User.id))]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: DbSession, _admin: AdminUser) -> dict[str, Any]:
    user = auth_service.create_user(db, **body.model_dump())
    db.commit()
    return auth_service.user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, body: UserUpdate, db: DbSession, admin: AdminUser
) -> dict[str, Any]:
    user = auth_service.update_user(
        db, user_id, **body.model_dump(exclude_unset=True), acting_user_id=admin.id
    )
    db.commit()
    return auth_service.user_out(user)


@router.get("/settings")
def get_settings(db: DbSession, _admin: AdminUser) -> list[dict[str, Any]]:
    return settings_service.list_all(db)


@router.put("/settings")
def put_settings(body: dict[str, Any], db: DbSession, admin: AdminUser) -> list[dict[str, Any]]:
    settings_service.put_many(db, body, admin.id)
    db.commit()
    return settings_service.list_all(db)


@router.get("/metrics")
def get_metrics(db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    return metrics_service.metrics(db)


@router.post("/llm/test", response_model=LlmTestResult)
def test_llm(db: DbSession, llm: Llm, _admin: AdminUser) -> dict[str, Any]:
    started = time.monotonic()
    result = {"model": settings.LLM_MODEL, "base_url": settings.LLM_BASE_URL}
    try:
        reply = llm.complete(
            [{"role": "user", "content": "Trả lời đúng một từ: OK"}], timeout=30
        )
        record_llm_call(db, reply)
        db.commit()
        return {**result, "ok": True, "model": reply.model, "latency_ms": reply.latency_ms}
    except (LLMTimeout, LLMUnavailable, LLMInvalidOutput) as exc:
        record_llm_call(db, None, error=exc)
        db.commit()
        return {
            **result,
            "ok": False,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error": str(exc)[:500],
        }
