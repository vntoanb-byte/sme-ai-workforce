"""
Bộ chuyển đổi mô hình tự nạp lại cấu hình

Bọc OpenAICompatibleLLM: thông số kết nối (địa chỉ, tên model, khoá API) lấy từ
`loader` — do tầng API/worker truyền vào, đọc bảng settings rồi mới tới biến
môi trường. Quản trị viên đổi mô hình trên trang Cài đặt thì:
  - tiến trình API nạp lại NGAY (điểm cuối gọi invalidate());
  - tiến trình worker nạp lại trong tối đa `ttl` giây (không gọi chéo tiến trình).

Cấu hình không đổi thì giữ nguyên client cũ (giữ trạng thái bộ ngắt mạch và kết
nối). Đọc cấu hình lỗi thì dùng tiếp cấu hình đang chạy; chưa có thì dùng
`fallback` — một lỗi CSDL thoáng qua không làm hệ thống mất kết nối mô hình.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from typing import Any

import structlog

from app.adapters.llm_openai_compatible import OpenAICompatibleLLM
from app.ports.llm import LLMConfig, LLMProvider, LLMResult

logger = structlog.get_logger(__name__)

ConfigLoader = Callable[[], LLMConfig]
ClientFactory = Callable[[LLMConfig], LLMProvider]


def build_client(config: LLMConfig) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        base_url=config.base_url, api_key=config.api_key, model=config.model
    )


class ReloadingLLM:
    """LLMProvider luôn dùng cấu hình mới nhất (kiểm tra lại mỗi `ttl` giây)."""

    def __init__(
        self,
        loader: ConfigLoader,
        *,
        fallback: LLMConfig,
        ttl: float = 10.0,
        factory: ClientFactory = build_client,
    ) -> None:
        self._loader = loader
        self._fallback = fallback
        self._ttl = ttl
        self._factory = factory
        self._lock = threading.Lock()
        self._config: LLMConfig | None = None
        self._client: LLMProvider | None = None
        self._checked_at = float("-inf")

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        images: Sequence[bytes] | None = None,
        timeout: float | None = None,
    ) -> LLMResult:
        return self._current().complete(messages, schema=schema, images=images, timeout=timeout)

    def invalidate(self) -> None:
        """Buộc lần gọi kế tiếp đọc lại cấu hình (sau khi quản trị viên lưu)."""
        with self._lock:
            self._checked_at = float("-inf")

    @property
    def config(self) -> LLMConfig:
        self._current()
        assert self._config is not None
        return self._config

    @property
    def model_name(self) -> str:
        return self.config.model

    def _current(self) -> LLMProvider:
        with self._lock:
            now = time.monotonic()
            if self._client is None or now - self._checked_at >= self._ttl:
                self._checked_at = now
                try:
                    config = self._loader()
                except Exception as exc:  # noqa: BLE001 — giữ cấu hình đang chạy
                    logger.warning("llm.config_load_failed", error=str(exc))
                    config = self._config or self._fallback
                if self._client is None or config != self._config:
                    if self._config is not None:
                        logger.info(
                            "llm.config_reloaded",
                            base_url=config.base_url,
                            model=config.model,
                        )
                    self._client = self._factory(config)
                    self._config = config
            return self._client
