"""
Xác thực và mã hoá

Băm mật khẩu (argon2), tạo/giải mã JWT, mã hoá bí mật cấu hình (Fernet).

Khoá:
  - JWT_SECRET rỗng → sinh khoá NGẪU NHIÊN tạm cho tiến trình (log cảnh báo).
    An toàn (không đoán được) nhưng mọi phiên mất hiệu lực khi khởi động lại
    và nhiều tiến trình không dùng chung được — vận hành thật PHẢI đặt khoá.
  - CREDENTIAL_ENC_KEY: chuỗi bất kỳ; được dẫn xuất (SHA-256) thành khoá Fernet
    32 byte, nên không bắt người vận hành tự sinh đúng định dạng base64.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import structlog
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.errors import AppError, Unauthorized

logger = structlog.get_logger(__name__)

JWT_ALGORITHM = "HS256"
ACCESS = "access"
REFRESH = "refresh"

_hasher = PasswordHasher()
_ephemeral_secret: str | None = None
# Giá trị mẫu trong .env.example — công khai trong repo nên KHÔNG được dùng làm khoá.
_PLACEHOLDER_SECRETS = {"SINH-NGAU-NHIEN-32-BYTE"}


def _jwt_secret() -> str:
    global _ephemeral_secret
    if settings.JWT_SECRET and settings.JWT_SECRET not in _PLACEHOLDER_SECRETS:
        return settings.JWT_SECRET
    if _ephemeral_secret is None:
        _ephemeral_secret = secrets.token_urlsafe(48)
        logger.warning(
            "security.jwt_secret_missing",
            message="JWT_SECRET chưa cấu hình — dùng khoá tạm, phiên mất khi khởi động lại.",
        )
    return _ephemeral_secret


# ─── Mật khẩu ───


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# ─── JWT ───


def _encode(claims: dict[str, Any], ttl: timedelta) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    expires_at = now + ttl
    payload = {**claims, "jti": jti, "iat": now, "exp": expires_at}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM), jti, expires_at


def create_access_token(sub: int | str, roles: list[str], ttl: timedelta | None = None) -> str:
    token, _, _ = _encode(
        {"sub": str(sub), "roles": roles, "type": ACCESS},
        ttl or timedelta(minutes=settings.JWT_ACCESS_TTL_MIN),
    )
    return token


def create_refresh_token(sub: int | str) -> tuple[str, str, datetime]:
    """Trả về (token, jti, expires_at) — jti được lưu DB để thu hồi được."""
    return _encode(
        {"sub": str(sub), "type": REFRESH},
        timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
    )


def decode_token(token: str, expected_type: str = ACCESS) -> dict[str, Any]:
    """Giải mã + kiểm chữ ký, hạn dùng và loại token; sai thì ném Unauthorized."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, _jwt_secret(), algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Phiên đăng nhập đã hết hạn.", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise Unauthorized("Mã truy cập không hợp lệ.", code="TOKEN_INVALID") from exc
    if payload.get("type") != expected_type:
        raise Unauthorized("Sai loại mã truy cập.", code="TOKEN_INVALID")
    return payload


# ─── Mã hoá bí mật cấu hình ───


def _fernet() -> Fernet:
    if not settings.CREDENTIAL_ENC_KEY:
        raise AppError(
            "CREDENTIAL_ENC_KEY chưa được cấu hình — không thể lưu thông tin bí mật.",
            code="ENCRYPTION_KEY_MISSING",
            http_status=500,
        )
    digest = hashlib.sha256(settings.CREDENTIAL_ENC_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            "Không giải mã được — khoá CREDENTIAL_ENC_KEY đã đổi hoặc dữ liệu hỏng.",
            code="DECRYPT_FAILED",
            http_status=500,
        ) from exc
