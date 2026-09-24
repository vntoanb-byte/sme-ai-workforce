"""Kiểm thử adapters/llm_openai_compatible.py bằng httpx.MockTransport (không gọi mạng)."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from app.adapters import llm_openai_compatible as mod
from app.adapters.llm_openai_compatible import OpenAICompatibleLLM
from app.ports.llm import LLMInvalidOutput, LLMTimeout, LLMUnavailable


def _llm(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAICompatibleLLM:
    llm = OpenAICompatibleLLM(base_url="http://model.test/v1", api_key="k", model="m")
    llm._client = httpx.Client(
        base_url="http://model.test/v1", transport=httpx.MockTransport(handler)
    )
    return llm


def _ok(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "qwen3-vl",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        },
    )


def test_guided_json_and_images_payload() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return _ok('{"label": "hoa_don"}')

    schema = {"type": "object", "properties": {"label": {"type": "string"}}}
    result = _llm(handler).complete(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "đọc"}],
        schema=schema,
        images=[b"\x89PNG"],
    )
    assert result.parsed == {"label": "hoa_don"}
    assert (result.model, result.token_in, result.token_out) == ("qwen3-vl", 12, 3)
    assert seen["response_format"]["json_schema"]["schema"] == schema
    user = seen["messages"][1]["content"]
    assert user[0] == {"type": "text", "text": "đọc"}
    assert user[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_invalid_json_and_4xx_raise_invalid_output() -> None:
    with pytest.raises(LLMInvalidOutput):
        _llm(lambda r: _ok("khong phai json")).complete(
            [{"role": "user", "content": "x"}], schema={"type": "object"}
        )
    with pytest.raises(LLMInvalidOutput):
        _llm(lambda r: httpx.Response(400, text="bad schema")).complete(
            [{"role": "user", "content": "x"}]
        )


def test_timeout_maps_to_llm_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("chậm", request=request)

    with pytest.raises(LLMTimeout):
        _llm(handler).complete([{"role": "user", "content": "x"}])


def test_circuit_breaker_opens_after_five_failures_and_resets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="quá tải")

    clock = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "monotonic", lambda: clock["t"])
    llm = _llm(handler)
    for _ in range(5):
        with pytest.raises(LLMUnavailable):
            llm.complete([{"role": "user", "content": "x"}])
    assert calls["n"] == 5
    with pytest.raises(LLMUnavailable, match="ngắt mạch"):
        llm.complete([{"role": "user", "content": "x"}])
    assert calls["n"] == 5  # mạch mở: không gọi máy chủ nữa

    clock["t"] += mod.CIRCUIT_RESET_SECONDS + 1
    llm._client = httpx.Client(
        base_url="http://model.test/v1", transport=httpx.MockTransport(lambda r: _ok("OK"))
    )
    assert llm.complete([{"role": "user", "content": "x"}]).content == "OK"
