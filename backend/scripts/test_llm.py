"""
Script test gọi model thật một lần, độc lập với FastAPI/DB.

Dùng khi muốn xác nhận adapters/llm_openai_compatible.py gọi được model thật
(OpenRouter khi dev, hoặc vLLM local khi đổi LLM_BASE_URL trong .env) — không
cần chạy `make dev-api`.

Chạy:
    cd backend && .venv/Scripts/python scripts/test_llm.py
    (hoặc .venv/bin/python trên Linux/macOS)

Cần điền LLM_API_KEY thật vào backend/.env trước khi chạy.
"""

from __future__ import annotations

import sys

# Console Windows mặc định dùng codepage cp1252, không encode được tiếng Việt
# có dấu — ép stdout/stderr sang UTF-8 trước khi in gì cả.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from app.adapters.llm_openai_compatible import OpenAICompatibleLLM
from app.core.config import settings
from app.ports.llm import LLMInvalidOutput, LLMTimeout, LLMUnavailable


def main() -> int:
    print(f"LLM_BASE_URL = {settings.LLM_BASE_URL}")
    print(f"LLM_MODEL    = {settings.LLM_MODEL}")
    if not settings.LLM_API_KEY:
        print("LỖI: LLM_API_KEY đang trống trong backend/.env — điền key thật rồi chạy lại.")
        return 1

    llm = OpenAICompatibleLLM()
    try:
        result = llm.complete(
            [{"role": "user", "content": "Trả lời đúng 1 từ: 'ok' nếu bạn nhận được tin nhắn này."}]
        )
    except LLMTimeout as exc:
        print(f"LỖI (timeout): {exc}")
        return 1
    except LLMUnavailable as exc:
        print(f"LỖI (không gọi được máy chủ mô hình): {exc}")
        return 1
    except LLMInvalidOutput as exc:
        print(f"LỖI (phản hồi không hợp lệ): {exc}")
        return 1
    finally:
        llm.close()

    print("\n--- Gọi model THÀNH CÔNG ---")
    print(f"model:      {result.model}")
    print(f"latency_ms: {result.latency_ms}")
    print(f"token_in:   {result.token_in}")
    print(f"token_out:  {result.token_out}")
    print(f"content:    {result.content!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
