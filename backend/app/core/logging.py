"""
Nhật ký có cấu trúc

Cấu hình structlog xuất JSON, mọi dòng log luôn kèm trace_id, run_id,
step_key (nếu có) lấy từ contextvars.

Dùng:
    setup_logging()                    # gọi một lần lúc khởi động tiến trình
    logger = get_logger(__name__)
    bind_context(trace_id=..., run_id=...)   # gắn vào mọi dòng log tiếp theo
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, get_contextvars

_configured = False


def setup_logging(level: str = "INFO", *, json: bool = True) -> None:
    """Cấu hình structlog + logging chuẩn. Gọi lại nhiều lần vẫn an toàn."""
    global _configured
    if _configured:
        return
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    renderer: Any = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if json
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def bind_context(**values: Any) -> None:
    bind_contextvars(**values)


def clear_context() -> None:
    clear_contextvars()


def get_trace_id() -> str | None:
    value = get_contextvars().get("trace_id")
    return str(value) if value is not None else None
