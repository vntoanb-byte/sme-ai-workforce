"""
Điểm khởi động ứng dụng FastAPI

Tạo đối tượng FastAPI, gắn middleware, đăng ký bộ xử lý lỗi, include router
v1, phục vụ file tĩnh của giao diện React đã build, và khởi động bộ lập lịch.

TRẠNG THÁI (2026-08-27): bản RÚT GỌN có chủ đích — chỉ đủ để `make dev-api`
khởi động thật và có 1 điểm cuối /health kiểm tra được DB + kho tệp + máy chủ
mô hình. CHƯA làm (vì các file phụ thuộc vẫn là stub, xem 08-apps/README.md
trong OS Brain / memory.md của project để biết lý do):
  - include_router(api_v1_router) — 8 router trong api/v1/*.py vẫn là stub.
  - Exception handler cho AppError/RequestValidationError — core/errors.py
    vẫn là stub.
  - Middleware trace_id, CORS, mount StaticFiles('frontend/dist').
  - Sự kiện startup chạy Alembic/seed/scheduler — models/*.py và
    workers/scheduler.py vẫn là stub.
Khi các phần trên được hiện thực, bổ sung dần vào đây theo đúng danh sách
"Cần hiện thực" gốc (xem lịch sử/`04 - references` trong OS Brain nếu cần
đối chiếu lại bản gốc).
"""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal

app = FastAPI(title="SME AI Workforce API", openapi_url="/api/v1/openapi.json")


@app.get("/health")
def health() -> dict:
    checks: dict[str, dict] = {}

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001 — health check phải bắt mọi lỗi để báo cáo, không để crash tiến trình
        checks["database"] = {"ok": False, "error": str(exc)}

    try:
        storage_path = Path(settings.STORAGE_PATH)
        storage_path.mkdir(parents=True, exist_ok=True)
        probe = storage_path / ".health_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks["storage"] = {"ok": True, "path": str(storage_path.resolve())}
    except Exception as exc:  # noqa: BLE001
        checks["storage"] = {"ok": False, "error": str(exc)}

    try:
        # Kiểm tra kết nối + xác thực tới máy chủ mô hình bằng GET /models —
        # KHÔNG gọi complete() ở đây để tránh tốn phí/độ trễ mỗi lần health
        # check. Test gọi model thật xem scripts/test_llm.py.
        resp = httpx.get(
            f"{settings.LLM_BASE_URL.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            timeout=5.0,
        )
        checks["llm"] = {"ok": resp.status_code < 400, "status_code": resp.status_code}
    except Exception as exc:  # noqa: BLE001
        checks["llm"] = {"ok": False, "error": str(exc)}

    overall_ok = all(c["ok"] for c in checks.values())
    return {"ok": overall_ok, "checks": checks}
