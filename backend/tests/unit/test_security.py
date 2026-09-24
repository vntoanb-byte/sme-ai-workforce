"""Kiểm thử core/security.py — băm mật khẩu, JWT, mã hoá bí mật."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core import security
from app.core.config import settings
from app.core.errors import AppError, Unauthorized


def test_hash_and_verify_password() -> None:
    hashed = security.hash_password("mat-khau-dung")
    assert hashed.startswith("$argon2")
    assert "mat-khau-dung" not in hashed
    assert security.verify_password("mat-khau-dung", hashed)
    assert not security.verify_password("mat-khau-sai", hashed)
    assert not security.verify_password("x", "khong-phai-hash")


def test_access_token_roundtrip() -> None:
    token = security.create_access_token(7, ["USER", "MANAGER"])
    payload = security.decode_token(token, security.ACCESS)
    assert payload["sub"] == "7"
    assert payload["roles"] == ["USER", "MANAGER"]
    assert payload["jti"]


def test_expired_token_rejected() -> None:
    token = security.create_access_token(1, ["USER"], ttl=timedelta(seconds=-1))
    with pytest.raises(Unauthorized) as exc:
        security.decode_token(token)
    assert exc.value.code == "TOKEN_EXPIRED"


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    token, jti, _ = security.create_refresh_token(1)
    assert security.decode_token(token, security.REFRESH)["jti"] == jti
    with pytest.raises(Unauthorized):
        security.decode_token(token, security.ACCESS)


def test_tampered_token_rejected() -> None:
    token = security.create_access_token(1, ["USER"])
    head, body, sig = token.split(".")
    with pytest.raises(Unauthorized):
        security.decode_token(f"{head}.{body}.{sig[:-2]}xx")


def test_encrypt_decrypt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CREDENTIAL_ENC_KEY", "mot-khoa-bat-ky-du-dai")
    cipher = security.encrypt_secret("sk-bi-mat")
    assert "sk-bi-mat" not in cipher
    assert security.decrypt_secret(cipher) == "sk-bi-mat"

    monkeypatch.setattr(settings, "CREDENTIAL_ENC_KEY", "khoa-khac")
    with pytest.raises(AppError) as exc:
        security.decrypt_secret(cipher)
    assert exc.value.code == "DECRYPT_FAILED"


def test_encrypt_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CREDENTIAL_ENC_KEY", "")
    with pytest.raises(AppError) as exc:
        security.encrypt_secret("x")
    assert exc.value.code == "ENCRYPTION_KEY_MISSING"
