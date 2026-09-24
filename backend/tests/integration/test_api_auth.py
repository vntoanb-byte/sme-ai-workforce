"""Kiểm thử xác thực + phân quyền qua HTTP (JWT, cookie refresh, thu hồi)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import RefreshToken
from tests.conftest import PASSWORD


def _login(client: TestClient, username: str = "ketoan", password: str = PASSWORD):  # noqa: ANN202
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_returns_tokens_user_and_httponly_cookies(anon_client: TestClient, users) -> None:
    resp = _login(anon_client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"] == {
        "id": users["ketoan"].id,
        "username": "ketoan",
        "full_name": "Nguyễn Thị Hoa",
        "email": "hoa@example.vn",
        "roles": ["USER"],
        "is_active": True,
    }
    assert body["access_token"] and body["refresh_token"]
    cookies = resp.headers.get_list("set-cookie")
    refresh = next(c for c in cookies if c.startswith("refresh_token="))
    assert "HttpOnly" in refresh and "SameSite=strict" in refresh
    assert "Path=/api/v1/auth" in refresh


def test_login_rejects_bad_password_with_uniform_error(anon_client: TestClient, users) -> None:
    resp = _login(anon_client, password="sai-mat-khau")
    assert resp.status_code == 401
    err = resp.json()["error"]
    assert err["code"] == "INVALID_CREDENTIALS"
    assert err["message"] == "Tên đăng nhập hoặc mật khẩu không đúng."
    assert err["trace_id"] == resp.headers["x-trace-id"]
    assert _login(anon_client, username="khong-co").status_code == 401


def test_me_requires_token(anon_client: TestClient, user_client: TestClient) -> None:
    assert anon_client.get("/api/v1/auth/me").status_code == 401
    assert user_client.get("/api/v1/auth/me").json()["username"] == "ketoan"
    bad = anon_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer xyz"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "TOKEN_INVALID"


def test_refresh_via_cookie_rotates_and_revokes_old(anon_client: TestClient, users) -> None:
    first = _login(anon_client).json()
    resp = anon_client.post("/api/v1/auth/refresh")  # cookie tự gửi kèm
    assert resp.status_code == 200
    assert resp.json()["user"]["username"] == "ketoan"
    # token cũ đã bị thu hồi khi xoay vòng
    reuse = anon_client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "TOKEN_REVOKED"


def test_logout_revokes_refresh_token(anon_client: TestClient, db: Session, users) -> None:
    tokens = _login(anon_client).json()
    assert anon_client.post("/api/v1/auth/logout").status_code == 204
    db.expire_all()
    assert all(r.revoked_at is not None for r in db.scalars(select(RefreshToken)))
    again = anon_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert again.status_code == 401
    assert anon_client.post("/api/v1/auth/refresh").status_code == 401  # cookie đã xoá


def test_access_cookie_only_accepted_for_get(anon_client: TestClient, users) -> None:
    _login(anon_client)  # đặt cookie access_token
    assert anon_client.get("/api/v1/auth/me").status_code == 200  # GET: nhận cookie
    # POST không nhận cookie (chống CSRF) — phải có header Authorization.
    resp = anon_client.post("/api/v1/documents/presign", json={"sha256": "a" * 64})
    assert resp.status_code == 401


def test_inactive_user_cannot_login_or_use_token(
    client: TestClient, user_client: TestClient, users
) -> None:
    resp = client.patch(f"/api/v1/admin/users/{users['ketoan'].id}", json={"is_active": False})
    assert resp.status_code == 200
    assert user_client.get("/api/v1/auth/me").status_code == 401
    assert _login(client).status_code == 401


def test_role_enforcement(user_client: TestClient, manager_client: TestClient) -> None:
    body = {"name": "x", "job_description": "Đọc hoá đơn mới trong thư mục mỗi sáng"}
    forbidden = user_client.post("/api/v1/employees", json=body)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
    assert user_client.get("/api/v1/admin/users").status_code == 403
    assert manager_client.get("/api/v1/admin/users").status_code == 403
    # Chỉ số bảng điều khiển: mọi người dùng đăng nhập đều xem được.
    assert user_client.get("/api/v1/admin/metrics").status_code == 200
