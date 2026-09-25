"""Kiểm thử adapters/llm_reloading.py — đổi cấu hình mô hình không cần khởi động lại."""

from __future__ import annotations

import httpx
import pytest

from app.adapters.llm_openai_compatible import OpenAICompatibleLLM
from app.adapters.llm_reloading import ReloadingLLM
from app.ports.llm import LLMConfig, LLMResult, LLMUnavailable

ENV = LLMConfig(base_url="http://env/v1", model="env-model")


class _Client:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def complete(self, messages, *, schema=None, images=None, timeout=None) -> LLMResult:  # noqa: ANN001
        return LLMResult("OK", None, self.config.model, 1, 1, 5)


def _reloading(configs: list[LLMConfig | Exception], ttl: float = 0.0):  # noqa: ANN202
    built: list[LLMConfig] = []
    calls = {"n": 0}

    def loader() -> LLMConfig:
        item = configs[min(calls["n"], len(configs) - 1)]
        calls["n"] += 1
        if isinstance(item, Exception):
            raise item
        return item

    def factory(config: LLMConfig) -> _Client:
        built.append(config)
        return _Client(config)

    return ReloadingLLM(loader, fallback=ENV, ttl=ttl, factory=factory), built


def _ask(llm: ReloadingLLM) -> str:
    return llm.complete([{"role": "user", "content": "x"}]).model


def test_reuses_client_until_config_changes() -> None:
    a = LLMConfig("http://vllm:8000/v1", "Qwen3-VL-8B")
    b = LLMConfig("https://openrouter.ai/api/v1", "qwen/qwen3-vl-8b-instruct", "k")
    llm, built = _reloading([a, a, b, b])
    assert [_ask(llm) for _ in range(4)] == [a.model, a.model, b.model, b.model]
    assert built == [a, b]  # cấu hình không đổi → giữ client (và bộ ngắt mạch)
    assert llm.model_name == b.model


def test_ttl_and_invalidate() -> None:
    a, b = LLMConfig("http://a/v1", "a"), LLMConfig("http://b/v1", "b")
    llm, _ = _reloading([a, b], ttl=3600)
    assert _ask(llm) == "a"
    assert _ask(llm) == "a"  # chưa hết ttl → chưa đọc lại
    llm.invalidate()  # quản trị viên vừa lưu
    assert _ask(llm) == "b"


def test_loader_failure_keeps_running_config_or_falls_back() -> None:
    a = LLMConfig("http://a/v1", "a")
    llm, built = _reloading([a, RuntimeError("CSDL bận")])
    assert _ask(llm) == "a"
    assert _ask(llm) == "a"
    assert built == [a]

    cold, _ = _reloading([RuntimeError("chưa có bảng settings")])
    assert _ask(cold) == ENV.model


def test_adapter_lists_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "b-model"}, {"id": "a-model"}]})

    llm = OpenAICompatibleLLM(base_url="http://model.test/v1", api_key="k", model="m")
    llm._client = httpx.Client(
        base_url="http://model.test/v1", transport=httpx.MockTransport(handler)
    )
    assert llm.list_models() == ["a-model", "b-model"]

    llm._client = httpx.Client(
        base_url="http://model.test/v1",
        transport=httpx.MockTransport(lambda r: httpx.Response(401, text="sai khoá")),
    )
    with pytest.raises(LLMUnavailable, match="401"):
        llm.list_models()
