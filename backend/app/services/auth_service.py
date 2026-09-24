"""
Dịch vụ xác thực và người dùng

  - authenticate(username, password) -> User | None (nguồn 'local': argon2).
  - issue_tokens / rotate_refresh / revoke_refresh: refresh token lưu jti ở bảng
    refresh_tokens → đăng xuất thu hồi được, mỗi lần làm mới xoay vòng token
    (token cũ bị thu hồi — lộ token cũ không dùng lại được).
  - Quản lý người dùng cho /admin/users.

Nguồn xác thực 'ldap' (docstring gốc) CHƯA hiện thực: cần thêm thư viện ldap3
và thông số máy chủ LDAP của doanh nghiệp — quyết định của Owner, không tự
thêm dependency. AUTH_BACKENDS để sẵn điểm mở rộng.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import Conflict, NotFound, Unauthorized, ValidationFailed
from app.models.user import RefreshToken, Role, User
from app.utils.dates import as_utc

ROLE_CODES = ("USER", "MANAGER", "ADMIN")


def _local_backend(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))
    if user is None:
        # Vẫn băm để thời gian phản hồi không lộ việc tài khoản có tồn tại hay không.
        security.verify_password(password, _DUMMY_HASH)
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    return user


_DUMMY_HASH = security.hash_password("khong-phai-mat-khau-that")
AUTH_BACKENDS: dict[str, Callable[[Session, str, str], User | None]] = {"local": _local_backend}


def authenticate(db: Session, username: str, password: str) -> User | None:
    for backend in AUTH_BACKENDS.values():
        user = backend(db, username, password)
        if user is not None:
            return user if user.is_active else None
    return None


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    user: User


def role_codes(user: User) -> list[str]:
    return sorted({r.code for r in user.roles}, key=ROLE_CODES.index)


def issue_tokens(db: Session, user: User) -> TokenPair:
    access = security.create_access_token(user.id, role_codes(user))
    refresh, jti, expires_at = security.create_refresh_token(user.id)
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    db.flush()
    return TokenPair(access, refresh, user)


def _load_refresh(db: Session, token: str) -> RefreshToken:
    payload = security.decode_token(token, security.REFRESH)
    record = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))
    if record is None or record.revoked_at is not None:
        raise Unauthorized("Phiên đăng nhập đã bị thu hồi.", code="TOKEN_REVOKED")
    if as_utc(record.expires_at) <= datetime.now(UTC):
        raise Unauthorized("Phiên đăng nhập đã hết hạn.", code="TOKEN_EXPIRED")
    return record


def rotate_refresh(db: Session, token: str) -> TokenPair:
    record = _load_refresh(db, token)
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Tài khoản không còn hoạt động.")
    record.revoked_at = datetime.now(UTC)
    return issue_tokens(db, user)


def revoke_refresh(db: Session, token: str | None) -> None:
    """Thu hồi refresh token; token hỏng/hết hạn thì bỏ qua (đăng xuất luôn thành công)."""
    if not token:
        return
    try:
        record = _load_refresh(db, token)
    except Unauthorized:
        return
    record.revoked_at = datetime.now(UTC)
    db.flush()


def get_active_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Tài khoản không còn hoạt động.")
    return user


def user_out(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "roles": role_codes(user),
        "is_active": user.is_active,
    }


# ─── Quản lý người dùng ───


def _roles(db: Session, codes: Sequence[str]) -> list[Role]:
    wanted = {c.upper() for c in codes} | {"USER"}  # ai cũng có quyền USER cơ bản
    unknown = wanted - set(ROLE_CODES)
    if unknown:
        raise ValidationFailed(f"Vai trò không hợp lệ: {sorted(unknown)}.")
    existing = {r.code: r for r in db.scalars(select(Role).where(Role.code.in_(wanted)))}
    for code in wanted - existing.keys():
        existing[code] = Role(code=code)
        db.add(existing[code])
    return [existing[c] for c in ROLE_CODES if c in wanted]


def _check_password(password: str) -> None:
    if len(password) < 8:
        raise ValidationFailed("Mật khẩu phải có ít nhất 8 ký tự.")


def create_user(
    db: Session,
    *,
    username: str,
    full_name: str,
    email: str,
    password: str,
    roles: Sequence[str],
) -> User:
    username = username.strip()
    clash = db.scalar(
        select(User).where(
            or_(func.lower(User.username) == username.lower(), User.email == email.strip())
        )
    )
    if clash is not None:
        raise Conflict("Tên đăng nhập hoặc thư điện tử đã được dùng.")
    _check_password(password)
    user = User(
        username=username,
        full_name=full_name.strip(),
        email=email.strip(),
        password_hash=security.hash_password(password),
        is_active=True,
    )
    user.roles = _roles(db, roles)
    db.add(user)
    db.flush()
    return user


def update_user(
    db: Session,
    user_id: int,
    *,
    full_name: str | None = None,
    email: str | None = None,
    password: str | None = None,
    roles: Sequence[str] | None = None,
    is_active: bool | None = None,
    acting_user_id: int | None = None,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("Người dùng không tồn tại.")
    if full_name is not None:
        user.full_name = full_name.strip()
    if email is not None:
        clash = db.scalar(select(User).where(User.email == email.strip(), User.id != user.id))
        if clash is not None:
            raise Conflict("Thư điện tử đã được dùng.")
        user.email = email.strip()
    if password is not None:
        _check_password(password)
        user.password_hash = security.hash_password(password)
        _revoke_all(db, user.id)
    if roles is not None:
        if user.id == acting_user_id and "ADMIN" not in {r.upper() for r in roles}:
            raise Conflict("Không thể tự bỏ quyền quản trị của chính mình.")
        user.roles = _roles(db, roles)
    if is_active is not None:
        if user.id == acting_user_id and not is_active:
            raise Conflict("Không thể tự khoá tài khoản của chính mình.")
        user.is_active = is_active
        if not is_active:
            _revoke_all(db, user.id)
    db.flush()
    return user


def _revoke_all(db: Session, user_id: int) -> None:
    now = datetime.now(UTC)
    for record in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ):
        record.revoked_at = now
