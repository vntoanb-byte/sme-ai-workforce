"""
Điểm cuối quản trị

  GET/POST/PATCH /admin/users — quản lý tài khoản (ADMIN)
  GET/PUT /admin/settings     — cấu hình khoá–giá trị (ADMIN; khoá "secret.*" được
                                mã hoá, không bao giờ trả giá trị thật)
  GET /admin/metrics          — số chứng từ, tỷ lệ tự động, giờ công tiết kiệm,
                                hàng chờ, tình trạng mô hình, token đã dùng.
                                MỌI người dùng đăng nhập được xem (bảng điều khiển
                                và chấm đỏ thanh điều hướng dùng chung chỉ số này).
  GET/PUT /admin/llm/config   — cấu hình mô hình AI: địa chỉ máy chủ, tên model,
                                khoá API (mã hoá, không bao giờ trả ra) — có hiệu
                                lực ngay, không cần khởi động lại (ADMIN)
  POST /admin/llm/test        — thử kết nối tới máy chủ mô hình; gửi kèm giá trị
                                đang nhập để thử TRƯỚC khi lưu (ADMIN)
  POST /admin/llm/models      — danh sách model máy chủ đang phục vụ (ADMIN)
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.adapters.llm_reloading import build_client
from app.api.deps import AdminUser, CurrentUser, DbSession, Llm, reload_llm
from app.models.user import User
from app.ports.llm import LLMInvalidOutput, LLMProvider, LLMTimeout, LLMUnavailable
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.services import auth_service, llm_config_service, metrics_service, settings_service
from app.services.document_service import record_llm_call

router = APIRouter()


class LlmTestResult(BaseModel):
    ok: bool
    model: str
    base_url: str
    latency_ms: int
    error: str | None = None


class LlmSettingsIn(BaseModel):
    """None = giữ nguyên; chuỗi rỗng (chỉ khi lưu) = xoá, quay về giá trị trong .env."""

    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, max_length=1000)


class LlmConfigOut(BaseModel):
    base_url: str
    model: str
    api_key_set: bool
    sources: dict[str, str]


class LlmModelsResult(BaseModel):
    ok: bool
    base_url: str
    models: list[str] = []
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
    reload_llm()  # có thể vừa đổi khoá llm.* / secret.llm_api_key
    return settings_service.list_all(db)


@router.get("/metrics")
def get_metrics(db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    return metrics_service.metrics(db)


@router.get("/llm/config", response_model=LlmConfigOut)
def get_llm_config(db: DbSession, _admin: AdminUser) -> dict[str, Any]:
    return llm_config_service.describe(db)


@router.put("/llm/config", response_model=LlmConfigOut)
def put_llm_config(body: LlmSettingsIn, db: DbSession, admin: AdminUser) -> dict[str, Any]:
    llm_config_service.update(
        db, base_url=body.base_url, model=body.model, api_key=body.api_key, user_id=admin.id
    )
    db.commit()
    reload_llm()
    return llm_config_service.describe(db)


def _has_values(body: LlmSettingsIn | None) -> bool:
    return body is not None and any((body.base_url, body.model, body.api_key))


@router.post("/llm/test", response_model=LlmTestResult)
def test_llm(
    db: DbSession, llm: Llm, _admin: AdminUser, body: LlmSettingsIn | None = None
) -> dict[str, Any]:
    """Không gửi gì: thử cấu hình đang chạy. Gửi kèm giá trị đang nhập: thử cấu
    hình đó (chưa lưu) — khoá API bỏ trống thì dùng khoá đã lưu."""
    started = time.monotonic()
    if _has_values(body):
        assert body is not None
        config = llm_config_service.candidate(
            db, base_url=body.base_url, model=body.model, api_key=body.api_key
        )
        client: LLMProvider = build_client(config)
    else:
        config = llm_config_service.resolve(db)
        client = llm
    result = {"model": config.model, "base_url": config.base_url}
    try:
        reply = client.complete(
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
    finally:
        if client is not llm and hasattr(client, "close"):
            client.close()
        db.close()


@router.post("/llm/models", response_model=LlmModelsResult)
def list_llm_models(
    db: DbSession, _admin: AdminUser, body: LlmSettingsIn | None = None
) -> dict[str, Any]:
    """Danh sách model của máy chủ (GET /models) — để chọn thay vì gõ tay."""
    if _has_values(body):
        assert body is not None
        config = llm_config_service.candidate(
            db, base_url=body.base_url, model=body.model, api_key=body.api_key
        )
    else:
        config = llm_config_service.resolve(db)
    client = build_client(config)
    try:
        return {"ok": True, "base_url": config.base_url, "models": client.list_models()}
    except (LLMTimeout, LLMUnavailable, LLMInvalidOutput) as exc:
        return {"ok": False, "base_url": config.base_url, "error": str(exc)[:500]}
    finally:
        client.close()
