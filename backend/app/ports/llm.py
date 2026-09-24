"""
Cổng mô hình ngôn ngữ

Giao diện trừu tượng cho mọi nhà cung cấp mô hình. Tầng nghiệp vụ CHỈ được
biết tới giao diện này, không bao giờ import trực tiếp thư viện của nhà cung
cấp.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMResult:
    content: str
    parsed: dict[str, Any] | None
    model: str
    token_in: int
    token_out: int
    latency_ms: int


class LLMTimeout(Exception):
    """Máy chủ mô hình không phản hồi trong thời gian cho phép."""


class LLMInvalidOutput(Exception):
    """Mô hình trả về nội dung không khớp schema đã yêu cầu."""


class LLMUnavailable(Exception):
    """Máy chủ mô hình không thể tiếp cận (bộ ngắt mạch đang mở, lỗi mạng...)."""


class LLMProvider(Protocol):
    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        images: Sequence[bytes] | None = None,
        timeout: float | None = None,
    ) -> LLMResult:
        """Gọi mô hình một lần, trả về LLMResult.

        Args:
            messages: Danh sách message kiểu OpenAI chat (role/content).
            schema: JSON Schema ràng buộc đầu ra (guided_json), nếu có.
            images: Ảnh đính kèm (bytes), được adapter chuyển thành data URI.
            timeout: Ghi đè timeout mặc định của adapter, tính bằng giây.

        Raises:
            LLMTimeout, LLMInvalidOutput, LLMUnavailable.
        """
        ...
