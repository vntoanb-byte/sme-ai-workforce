"""
Các phụ thuộc dùng chung của tầng API

Cung cấp phiên CSDL và các adapter (LLM, storage) cho mọi điểm cuối.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.adapters.llm_openai_compatible import OpenAICompatibleLLM
from app.adapters.storage_local import LocalFileStorage
from app.core.config import settings
from app.db.session import SessionLocal
from app.ports.llm import LLMProvider
from app.ports.storage import FileStorage

_llm_instance: LLMProvider | None = None


def get_db() -> Generator[Session, None, None]:
    """Mở phiên CSDL, đóng ở finally (mọi endpoint đều dùng phụ thuộc này)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_llm() -> LLMProvider:
    """Trả về adapter LLM (OpenAICompatibleLLM) dựng từ settings.

    Dùng 1 instance dùng chung cho toàn tiến trình để giữ nguyên trạng thái bộ
    ngắt mạch (circuit breaker) của adapter giữa các request.
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = OpenAICompatibleLLM()
    return _llm_instance


def get_storage() -> FileStorage:
    """Trả về LocalFileStorage dựng từ settings.STORAGE_PATH."""
    return LocalFileStorage(settings.STORAGE_PATH)
