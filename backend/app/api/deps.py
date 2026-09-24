"""
Các phụ thuộc dùng chung của tầng API

Phiên CSDL, các adapter (LLM, storage, queue) và xác thực/phân quyền.

Xác thực:
  - Header `Authorization: Bearer <access_token>` cho mọi phương thức.
  - Cookie HttpOnly `access_token` CHỈ được chấp nhận cho GET/HEAD — những
    request trình duyệt tự gửi không kèm header được (thẻ <img> xem chứng từ,
    EventSource nhật ký SSE, liên kết tải tệp). Không nhận cookie cho
    POST/PUT/PATCH/DELETE → không mở đường cho tấn công CSRF.
Phân quyền: USER (mọi người dùng), MANAGER (tạo/duyệt/chạy nhân viên AI),
ADMIN (người dùng, cấu hình hệ thống). Giao diện chỉ ẩn/hiện nút; quyết định
thật nằm ở đây.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.adapters.llm_openai_compatible import OpenAICompatibleLLM
from app.adapters.queue_sqlite import SQLiteJobQueue
from app.adapters.storage_local import LocalFileStorage
from app.core import security
from app.core.config import settings
from app.core.errors import Forbidden, Unauthorized
from app.core.logging import bind_context
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.ports.llm import LLMProvider
from app.ports.queue import JobQueue
from app.ports.storage import FileStorage
from app.services import auth_service

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

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


DbSession = Annotated[Session, Depends(get_db)]


def get_session_factory() -> Callable[[], Session]:
    """Cho điểm cuối truyền dữ liệu lâu (SSE) tự mở phiên ngắn cho từng lần đọc
    thay vì giữ một phiên suốt kết nối."""
    return SessionLocal


def get_queue(db: DbSession) -> JobQueue:
    """Hàng đợi SQLite trên CÙNG engine với phiên CSDL của request (enqueue
    dùng chung transaction của phiên — ADR-001)."""
    bind = db.get_bind()
    return SQLiteJobQueue(bind.engine if bind is not None else engine)


def _token_from(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    if request.method in ("GET", "HEAD"):
        return request.cookies.get(ACCESS_COOKIE)
    return None


def get_current_user(request: Request, db: DbSession) -> User:
    token = _token_from(request)
    if not token:
        raise Unauthorized("Vui lòng đăng nhập.")
    payload = security.decode_token(token, security.ACCESS)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized("Mã truy cập không hợp lệ.") from exc
    user = auth_service.get_active_user(db, user_id)
    bind_context(user_id=user.id)
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    def _check(user: Annotated[User, Depends(get_current_user)]) -> User:
        codes = set(auth_service.role_codes(user))
        if not codes & set(roles):
            raise Forbidden("Bạn không có quyền thực hiện thao tác này.")
        return user

    return _check


CurrentUser = Annotated[User, Depends(get_current_user)]
ManagerUser = Annotated[User, Depends(require_roles("MANAGER", "ADMIN"))]
AdminUser = Annotated[User, Depends(require_roles("ADMIN"))]
Llm = Annotated[LLMProvider, Depends(get_llm)]
Storage = Annotated[FileStorage, Depends(get_storage)]
Queue = Annotated[JobQueue, Depends(get_queue)]
SessionFactory = Annotated[Callable[[], Session], Depends(get_session_factory)]
