"""
Bộ chuyển đổi mô hình tương thích OpenAI

Hiện thực LLMProvider cho mọi điểm cuối tương thích chuẩn OpenAI: vLLM tự vận
hành, Ollama, và các dịch vụ trung gian qua Internet. Đây là adapter DUY NHẤT
cần viết.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.core.config import settings
from app.ports.llm import LLMInvalidOutput, LLMResult, LLMTimeout, LLMUnavailable

CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_RESET_SECONDS = 60.0


class OpenAICompatibleLLM:
    """LLMProvider cho mọi endpoint tương thích /chat/completions kiểu OpenAI."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._model = model or settings.LLM_MODEL
        self._timeout = timeout or settings.LLM_TIMEOUT_SEC
        key = api_key or settings.LLM_API_KEY
        self._client = httpx.Client(
            base_url=base_url or settings.LLM_BASE_URL,
            # vLLM nội bộ thường không cần khoá: KHÔNG gửi "Bearer " rỗng (httpx từ
            # chối giá trị header không hợp lệ — lỗi thật khi chạy container).
            headers={"Authorization": f"Bearer {key}"} if key else {},
            timeout=self._timeout,
        )
        # Bộ ngắt mạch đơn giản, dùng bộ nhớ tiến trình (đủ cho worker đơn
        # luồng của bản MVP). Nhiều worker/tiến trình sẽ cần chia sẻ trạng
        # thái này qua DB hoặc Redis — không phải phạm vi bản này.
        self._consecutive_failures = 0
        self._circuit_open_until: float = 0.0

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        images: Sequence[bytes] | None = None,
        timeout: float | None = None,
    ) -> LLMResult:
        now = time.monotonic()
        if now < self._circuit_open_until:
            remaining = self._circuit_open_until - now
            raise LLMUnavailable(
                f"Bộ ngắt mạch đang mở sau {CIRCUIT_FAILURE_THRESHOLD} lỗi liên "
                f"tiếp — thử lại sau {remaining:.0f}s."
            )

        payload_messages = self._attach_images(list(messages), images)
        payload: dict[str, Any] = {"model": self._model, "messages": payload_messages}
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": schema, "strict": True},
            }

        start = time.monotonic()
        try:
            resp = self._client.post(
                "/chat/completions", json=payload, timeout=timeout or self._timeout
            )
        except httpx.TimeoutException as exc:
            self._record_failure()
            raise LLMTimeout(f"Máy chủ mô hình không phản hồi: {exc}") from exc
        except httpx.HTTPError as exc:
            self._record_failure()
            raise LLMUnavailable(f"Không gọi được máy chủ mô hình: {exc}") from exc

        latency_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code >= 500:
            self._record_failure()
            raise LLMUnavailable(
                f"Máy chủ mô hình trả lỗi {resp.status_code}: {resp.text[:300]}"
            )
        if resp.status_code >= 400:
            # Lỗi 4xx (vd. sai schema/tham số) không tính là "máy chủ mô hình
            # không sẵn sàng" — không mở bộ ngắt mạch cho loại lỗi này.
            raise LLMInvalidOutput(
                f"Yêu cầu bị từ chối ({resp.status_code}): {resp.text[:300]}"
            )

        self._consecutive_failures = 0
        data = resp.json()

        try:
            choice = data["choices"][0]["message"]
            content = choice.get("content") or ""
            usage = data.get("usage", {})
        except (KeyError, IndexError) as exc:
            raise LLMInvalidOutput(f"Phản hồi thiếu trường bắt buộc: {exc}") from exc

        parsed: dict[str, Any] | None = None
        if schema is not None:
            parsed = self._parse_json_content(content)

        return LLMResult(
            content=content,
            parsed=parsed,
            model=data.get("model", self._model),
            token_in=usage.get("prompt_tokens", 0),
            token_out=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= CIRCUIT_FAILURE_THRESHOLD:
            self._circuit_open_until = time.monotonic() + CIRCUIT_RESET_SECONDS

    @staticmethod
    def _attach_images(
        messages: list[dict[str, Any]], images: Sequence[bytes] | None
    ) -> list[dict[str, Any]]:
        """Ghép ảnh vào message cuối cùng có role='user', dạng data URI base64.

        Nếu không có message nào role='user', không sửa gì (tránh đoán sai ý
        định của bên gọi).
        """
        if not images:
            return messages
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            text = msg.get("content", "")
            parts: list[dict[str, Any]] = (
                [{"type": "text", "text": text}] if isinstance(text, str) and text else []
            )
            for img in images:
                b64 = base64.b64encode(img).decode("ascii")
                parts.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                )
            msg["content"] = parts
            break
        return messages

    @staticmethod
    def _parse_json_content(content: str) -> dict[str, Any]:
        import json

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMInvalidOutput(f"Nội dung không phải JSON hợp lệ: {exc}") from exc
        if not isinstance(result, dict):
            raise LLMInvalidOutput("Nội dung JSON hợp lệ nhưng không phải object.")
        return result

    def close(self) -> None:
        self._client.close()
