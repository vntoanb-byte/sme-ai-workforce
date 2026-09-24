"""
Điểm cuối xác thực

  POST /login   — username+password → access_token + refresh_token (+ cookie)
  POST /refresh — đổi refresh_token (cookie HttpOnly hoặc body) lấy cặp mới;
                  token cũ bị thu hồi (xoay vòng)
  POST /logout  — thu hồi refresh_token, xoá cookie
  GET  /me      — người dùng hiện tại kèm vai trò

Cookie:
  - refresh_token: HttpOnly, SameSite=Strict, Path=/api/v1/auth — JavaScript
    không đọc được, chỉ gửi tới các điểm cuối xác thực. Nhờ nó giao diện khôi
    phục được phiên khi tải lại trang mà KHÔNG lưu token vào localStorage.
  - access_token: HttpOnly, SameSite=Strict, Path=/api/v1 — chỉ dùng cho GET
    không gửi được header (ảnh chứng từ, SSE, tải tệp), xem api/deps.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.api.deps import ACCESS_COOKIE, REFRESH_COOKIE, CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import Unauthorized
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserOut
from app.services import auth_service
from app.services.auth_service import TokenPair as ServiceTokens

router = APIRouter()

_REFRESH_PATH = "/api/v1/auth"


def _set_cookies(response: Response, tokens: ServiceTokens) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.JWT_REFRESH_TTL_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path=_REFRESH_PATH,
    )
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=settings.JWT_ACCESS_TTL_MIN * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path="/api/v1",
    )


def _payload(tokens: ServiceTokens) -> dict[str, Any]:
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "user": auth_service.user_out(tokens.user),
    }


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, response: Response, db: DbSession) -> dict[str, Any]:
    user = auth_service.authenticate(db, body.username, body.password)
    if user is None:
        raise Unauthorized(
            "Tên đăng nhập hoặc mật khẩu không đúng.", code="INVALID_CREDENTIALS"
        )
    tokens = auth_service.issue_tokens(db, user)
    db.commit()
    _set_cookies(response, tokens)
    return _payload(tokens)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    request: Request, response: Response, db: DbSession, body: RefreshRequest | None = None
) -> dict[str, Any]:
    token = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise Unauthorized("Chưa đăng nhập.", code="NO_SESSION")
    tokens = auth_service.rotate_refresh(db, token)
    db.commit()
    _set_cookies(response, tokens)
    return _payload(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: DbSession, body: RefreshRequest | None = None) -> Response:
    token = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    auth_service.revoke_refresh(db, token)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_PATH)
    response.delete_cookie(ACCESS_COOKIE, path="/api/v1")
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> dict[str, Any]:
    return auth_service.user_out(user)
