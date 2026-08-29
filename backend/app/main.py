"""
Điểm khởi động ứng dụng FastAPI

Tạo đối tượng FastAPI, gắn middleware, đăng ký bộ xử lý lỗi, include router
v1, phục vụ file tĩnh của giao diện React đã build, và khởi động bộ lập lịch.

TRẠNG THÁI (2026-08-29, TASK-006): thêm CORS (settings.CORS_ORIGINS) và mount
router /api/v1 (hiện chỉ có documents — 8 router còn lại vẫn là stub). Vẫn
CHƯA làm (file phụ thuộc vẫn stub, làm ở task sau):
  - Exception handler cho AppError/RequestValidationError — core/errors.py stub.
  - Middleware trace_id, mount StaticFiles('frontend/dist').
  - Sự kiện startup chạy Alembic/seed/scheduler — workers/scheduler.py stub.
"""

from __future__ import annotations  # noqa: I001

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

# PHẢI import app.db.base TRƯỚC app.api.v1: nạp trọn chuỗi model qua
# db/base.py để tránh import vòng vỡ giữa chừng khi router (vd.
# app/api/v1/documents.py) import trực tiếp 1 model cụ thể trước khi
# app.db.base kịp nạp xong toàn bộ 21 bảng (phát hiện thật khi chạy
# `uvicorn app.main:app` — pytest không lộ vì tests/conftest.py tình cờ import
# app.db.base trước app.main). Thứ tự dòng dưới đây CỐ Ý không theo isort.
from app.db.base import Base  # noqa: F401
from app.api.v1 import api_router
from app.core.config import settings
from app.db.session import SessionLocal

app = FastAPI(title="SME AI Workforce API", openapi_url="/api/v1/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


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
