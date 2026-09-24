"""Kiểm thử khung ứng dụng: định dạng lỗi thống nhất, trace_id, OpenAPI, lỗi 500."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_uniform_error_body_and_trace_id(client: TestClient) -> None:
    resp = client.get("/api/v1/employees/999999", headers={"X-Request-ID": "abc123"})
    assert resp.status_code == 404
    assert resp.headers["x-trace-id"] == "abc123"
    assert resp.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Không tìm thấy nhân viên AI.",
            "details": [],
            "trace_id": "abc123",
        }
    }


def test_validation_error_format(client: TestClient) -> None:
    resp = client.post("/api/v1/runs", json={"employee_id": "khong-phai-so"})
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_FAILED"
    assert err["details"][0]["loc"] == ["body", "employee_id"]


def test_unknown_route_and_openapi(client: TestClient) -> None:
    assert client.get("/api/v1/khong-co").json()["error"]["code"] == "NOT_FOUND"
    spec = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/runs/{run_id}/logs" in spec["paths"]
    assert len(spec["paths"]) >= 30


def test_unhandled_exception_hides_details(client: TestClient) -> None:
    @app.get("/api/v1/_loi_thu")
    def _boom() -> None:
        raise RuntimeError("chi tiết nội bộ không được lộ")

    try:
        resp = TestClient(app, raise_server_exceptions=False).get("/api/v1/_loi_thu")
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", "") != "/api/v1/_loi_thu"
        ]
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "nội bộ" not in resp.text
    assert body["error"]["trace_id"]
