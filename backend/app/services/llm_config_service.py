"""
Dịch vụ cấu hình mô hình AI

Quản trị viên chọn máy chủ mô hình trên trang Cài đặt thay vì sửa tệp .env:
  - llm.base_url        — địa chỉ máy chủ tương thích OpenAI (vLLM, Ollama,
                          OpenRouter, OpenAI, Gemini…)
  - llm.model           — tên model
  - secret.llm_api_key  — khoá API, mã hoá Fernet (CREDENTIAL_ENC_KEY), không
                          bao giờ trả ra API
Giá trị trong bảng settings ƯU TIÊN hơn biến môi trường LLM_*; để trống một
trường = quay về giá trị trong .env. Mỗi lần đổi ghi audit_logs (không ghi khoá).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationFailed
from app.models.audit import AuditLog, Setting
from app.ports.llm import LLMConfig
from app.services import settings_service

KEY_BASE_URL = "llm.base_url"
KEY_MODEL = "llm.model"
KEY_API_KEY = settings_service.SECRET_PREFIX + "llm_api_key"


def env_config() -> LLMConfig:
    return LLMConfig(
        base_url=settings.LLM_BASE_URL, model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY
    )


def _stored(db: Session, key: str) -> str:
    value = settings_service.get(db, key)
    return value.strip() if isinstance(value, str) else ""


def resolve(db: Session) -> LLMConfig:
    """Cấu hình đang có hiệu lực: bảng settings, thiếu thì lấy biến môi trường."""
    env = env_config()
    return LLMConfig(
        base_url=_stored(db, KEY_BASE_URL) or env.base_url,
        model=_stored(db, KEY_MODEL) or env.model,
        api_key=_stored(db, KEY_API_KEY) or env.api_key,
    )


def load() -> LLMConfig:
    """Loader cho adapters/llm_reloading.py — mở phiên CSDL ngắn của riêng nó."""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        return resolve(db)


def describe(db: Session) -> dict[str, Any]:
    """Dữ liệu cho trang Cài đặt — KHÔNG chứa khoá API."""
    config = resolve(db)
    stored_key = db.get(Setting, KEY_API_KEY) is not None

    def source(key: str) -> str:
        return "settings" if db.get(Setting, key) is not None else "env"

    return {
        "base_url": config.base_url,
        "model": config.model,
        "api_key_set": bool(config.api_key),
        "sources": {
            "base_url": source(KEY_BASE_URL),
            "model": source(KEY_MODEL),
            "api_key": "settings" if stored_key else "env",
        },
    }


def validate_base_url(url: str) -> str:
    url = url.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationFailed(
            "Địa chỉ máy chủ mô hình phải bắt đầu bằng http:// hoặc https://, "
            "ví dụ http://vllm:8000/v1."
        )
    return url


def _validate_model(model: str) -> str:
    model = model.strip()
    if len(model) > 200:
        raise ValidationFailed("Tên model quá dài (tối đa 200 ký tự).")
    return model


def candidate(
    db: Session,
    *,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMConfig:
    """Cấu hình đang có hiệu lực, ghi đè bằng các giá trị đang nhập trên giao
    diện (chưa lưu) — dùng để thử kết nối trước khi lưu. None = giữ nguyên."""
    current = resolve(db)
    return LLMConfig(
        base_url=validate_base_url(base_url) if base_url else current.base_url,
        model=(_validate_model(model) or current.model) if model else current.model,
        api_key=api_key.strip() if api_key else current.api_key,
    )


def update(
    db: Session,
    *,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    user_id: int | None,
) -> None:
    """Lưu cấu hình. Mỗi trường: None = giữ nguyên; chuỗi rỗng = xoá giá trị
    đã lưu (quay về .env); còn lại = lưu giá trị mới. Không tự commit."""
    before = describe(db)
    changes: dict[str, Any] = {}
    if base_url is not None:
        changes[KEY_BASE_URL] = validate_base_url(base_url) if base_url.strip() else ""
    if model is not None:
        changes[KEY_MODEL] = _validate_model(model)
    if api_key is not None:
        api_key = api_key.strip()
        if api_key and not settings.CREDENTIAL_ENC_KEY:
            raise ValidationFailed(
                "Máy chủ chưa cấu hình CREDENTIAL_ENC_KEY nên không thể lưu khoá API an toàn. "
                "Đặt biến này trong backend/.env rồi khởi động lại."
            )
        changes[KEY_API_KEY] = api_key

    to_store = {key: value for key, value in changes.items() if value}
    for key in (key for key, value in changes.items() if not value):
        row = db.get(Setting, key)
        if row is not None:
            db.delete(row)
    settings_service.put_many(db, to_store, user_id)
    db.flush()

    after = describe(db)
    db.add(
        AuditLog(
            user_id=user_id,
            action="settings.llm.update",
            entity_type="settings",
            detail_json=json.dumps(
                {
                    "before": before,
                    "after": after,
                    "api_key_changed": api_key is not None,
                },
                ensure_ascii=False,
            ),
        )
    )
    db.flush()
