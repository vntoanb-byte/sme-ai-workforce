"""Kiểm thử cấu hình mô hình AI qua API (/admin/llm/config, /test, /models):
lưu trong bảng settings, khoá API mã hoá và không bao giờ trả ra, có hiệu lực
ngay, quay về .env khi xoá."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import admin
from app.core.config import settings
from app.models.audit import AuditLog
from app.ports.llm import LLMConfig, LLMResult, LLMUnavailable
from app.services import llm_config_service

URL = "/api/v1/admin/llm"
SECRET = "sk-bi-mat-khong-duoc-lo-123"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://vllm:8000/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "Qwen3-VL-8B")
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "CREDENTIAL_ENC_KEY", "khoa-ma-hoa-thu-nghiem")


@pytest.fixture()
def reloads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(admin, "reload_llm", lambda: calls.append(1))
    return calls


class _Client:
    """Thay cho OpenAICompatibleLLM khi thử cấu hình chưa lưu (không gọi mạng)."""

    built: list[LLMConfig] = []

    def __init__(self, config: LLMConfig, *, fail: bool = False) -> None:
        self.config = config
        self.fail = fail
        _Client.built.append(config)

    def complete(self, messages, *, schema=None, images=None, timeout=None) -> LLMResult:  # noqa: ANN001
        if self.fail:
            raise LLMUnavailable("Máy chủ mô hình trả lỗi 401: sai khoá")
        return LLMResult("OK", None, self.config.model, 3, 1, 120)

    def list_models(self) -> list[str]:
        if self.fail:
            raise LLMUnavailable("Máy chủ mô hình trả lỗi 401: sai khoá")
        return ["gpt-4o-mini", "qwen/qwen3-vl-8b-instruct"]

    def close(self) -> None:
        pass


def test_defaults_come_from_env(client: TestClient) -> None:
    assert client.get(f"{URL}/config").json() == {
        "base_url": "http://vllm:8000/v1",
        "model": "Qwen3-VL-8B",
        "api_key_set": False,
        "sources": {"base_url": "env", "model": "env", "api_key": "env"},
    }


def test_save_mask_resolve_and_reset(
    client: TestClient, db: Session, reloads: list[int]
) -> None:
    saved = client.put(
        f"{URL}/config",
        json={
            "base_url": "https://openrouter.ai/api/v1/",
            "model": " qwen/qwen3-vl-8b-instruct ",
            "api_key": SECRET,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "qwen/qwen3-vl-8b-instruct",
        "api_key_set": True,
        "sources": {"base_url": "settings", "model": "settings", "api_key": "settings"},
    }
    assert reloads == [1]  # có hiệu lực ngay ở tiến trình API
    assert SECRET not in saved.text

    # Khoá lưu mã hoá: API cấu hình chung chỉ thấy "••••••", nhật ký không chứa khoá.
    listing = {s["key"]: s["value"] for s in client.get("/api/v1/admin/settings").json()}
    assert listing["secret.llm_api_key"] == "••••••"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "settings.llm.update"))
    assert audit is not None and SECRET not in (audit.detail_json or "")
    assert json.loads(audit.detail_json or "{}")["before"]["sources"]["model"] == "env"
    db.expire_all()
    assert llm_config_service.resolve(db) == LLMConfig(
        "https://openrouter.ai/api/v1", "qwen/qwen3-vl-8b-instruct", SECRET
    )

    # Chỉ đổi model: khoá giữ nguyên. Chuỗi rỗng: quay về .env.
    client.put(f"{URL}/config", json={"model": "google/gemini-2.5-flash"})
    db.expire_all()
    assert llm_config_service.resolve(db).api_key == SECRET
    reset = client.put(f"{URL}/config", json={"base_url": "", "model": "", "api_key": ""}).json()
    assert reset["sources"] == {"base_url": "env", "model": "env", "api_key": "env"}
    assert (reset["base_url"], reset["api_key_set"]) == ("http://vllm:8000/v1", False)


def test_validation_and_permissions(
    client: TestClient, user_client: TestClient, manager_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = client.put(f"{URL}/config", json={"base_url": "ftp://may-chu"})
    assert bad.status_code == 422 and "http" in bad.json()["error"]["message"]
    assert client.put(f"{URL}/config", json={"base_url": "vllm:8000"}).status_code == 422

    monkeypatch.setattr(settings, "CREDENTIAL_ENC_KEY", "")
    no_key = client.put(f"{URL}/config", json={"api_key": SECRET})
    assert no_key.status_code == 422 and "CREDENTIAL_ENC_KEY" in no_key.json()["error"]["message"]

    for other in (user_client, manager_client):
        assert other.get(f"{URL}/config").status_code == 403
        assert other.put(f"{URL}/config", json={"model": "x"}).status_code == 403
        assert other.post(f"{URL}/models").status_code == 403


def test_try_unsaved_values_before_saving(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.put(f"{URL}/config", json={"api_key": SECRET})
    _Client.built = []
    monkeypatch.setattr(admin, "build_client", _Client)

    # Thử địa chỉ + model đang nhập; bỏ trống khoá → dùng khoá đã lưu.
    ok = client.post(
        f"{URL}/test", json={"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"}
    ).json()
    assert ok["ok"] is True and ok["model"] == "gpt-4o-mini"
    assert ok["base_url"] == "https://api.openai.com/v1"
    assert _Client.built == [LLMConfig("https://api.openai.com/v1", "gpt-4o-mini", SECRET)]

    models = client.post(f"{URL}/models", json={"base_url": "https://openrouter.ai/api/v1"})
    assert models.json() == {
        "ok": True,
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["gpt-4o-mini", "qwen/qwen3-vl-8b-instruct"],
        "error": None,
    }
    # Thử KHÔNG lưu gì: cấu hình đã lưu vẫn nguyên.
    assert client.get(f"{URL}/config").json()["base_url"] == "http://vllm:8000/v1"

    monkeypatch.setattr(admin, "build_client", lambda c: _Client(c, fail=True))
    failed = client.post(f"{URL}/test", json={"api_key": "sai"}).json()
    assert failed["ok"] is False and "401" in failed["error"]
    listed: dict[str, Any] = client.post(f"{URL}/models").json()
    assert listed["ok"] is False and listed["models"] == []
