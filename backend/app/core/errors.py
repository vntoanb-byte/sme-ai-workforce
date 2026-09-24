"""
Lỗi ứng dụng

Định nghĩa cây ngoại lệ và bộ chuyển đổi sang phản hồi HTTP theo cấu trúc
thống nhất {error: {code, message, details, trace_id}} — đúng kiểu
`ApiErrorBody` mà frontend (src/api/client.ts) đọc.

Phân loại lỗi tạm thời / vĩnh viễn (`is_transient`) dùng cho worker và
execution_service quyết định có thử lại hay không.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_trace_id
from app.ports.llm import LLMTimeout, LLMUnavailable

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """Lỗi nghiệp vụ có mã, thông điệp tiếng Việt và mã HTTP tương ứng."""

    code = "APP_ERROR"
    http_status = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: list[Any] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or []


class NotFound(AppError):
    code = "NOT_FOUND"
    http_status = 404


class Unauthorized(AppError):
    code = "UNAUTHORIZED"
    http_status = 401


class Forbidden(AppError):
    code = "FORBIDDEN"
    http_status = 403


class Conflict(AppError):
    code = "CONFLICT"
    http_status = 409


class ValidationFailed(AppError):
    code = "VALIDATION_FAILED"
    http_status = 422


class LLMUnavailableError(AppError):
    """Máy chủ mô hình không dùng được — khác `ports.llm.LLMUnavailable` (lỗi tầng adapter)."""

    code = "LLM_UNAVAILABLE"
    http_status = 503


class StorageError(AppError):
    code = "STORAGE_ERROR"
    http_status = 500


# Mã lỗi mặc định theo mã HTTP cho HTTPException của FastAPI/Starlette.
_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_FAILED",
    429: "TOO_MANY_REQUESTS",
}


def is_transient(exc: BaseException) -> bool:
    """True nếu lỗi có khả năng tự hết khi thử lại (mạng, mô hình quá tải, DB bận).

    Lỗi vĩnh viễn (dữ liệu sai, cấu hình sai, lỗi lập trình) KHÔNG thử lại —
    thử lại chỉ tốn tài nguyên và làm chậm việc báo lỗi cho người dùng.
    """
    if isinstance(exc, LLMTimeout | LLMUnavailable | TimeoutError | ConnectionError):
        return True
    if isinstance(exc, LLMUnavailableError):
        return True
    if isinstance(exc, OperationalError | sqlite3.OperationalError):
        return "locked" in str(exc).lower() or "busy" in str(exc).lower()
    return False


def _body(code: str, message: str, details: list[Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "trace_id": get_trace_id(),
        }
    }


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.http_status, content=_body(exc.code, exc.message, exc.details)
    )


async def http_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    message = exc.detail if isinstance(exc.detail, str) else "Yêu cầu không hợp lệ."
    return JSONResponse(
        status_code=exc.status_code,
        content=_body(_HTTP_CODES.get(exc.status_code, "HTTP_ERROR"), message),
        headers=getattr(exc, "headers", None),
    )


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        {"loc": list(err.get("loc", ())), "message": err.get("msg", "")}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_body("VALIDATION_FAILED", "Dữ liệu gửi lên không hợp lệ.", details),
    )


async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Không lộ traceback cho người dùng — chỉ trace_id để tra nhật ký.
    logger.exception("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content=_body(
            "INTERNAL_ERROR", "Hệ thống gặp sự cố không xác định. Vui lòng thử lại sau."
        ),
    )
