"""
Điểm khởi động ứng dụng FastAPI

Tạo đối tượng FastAPI, gắn middleware (CORS, trace_id), đăng ký bộ xử lý lỗi
thống nhất {error:{code,message,details,trace_id}}, include router /api/v1,
phục vụ bản build giao diện React (STATIC_DIR) và — khi khởi động — nâng cấp
lược đồ bằng Alembic rồi nạp dữ liệu gốc (db/init_db.py).

Bộ lập lịch KHÔNG chạy trong tiến trình API (uvicorn có thể chạy nhiều tiến
trình → lịch bị kích hoạt trùng); nó chạy trong tiến trình worker
(`python -m app.workers.worker`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.core.config import settings
from app.core.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.logging import bind_context, clear_context, new_trace_id, setup_logging
from app.db import init_db
from app.db.session import SessionLocal


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Nâng cấp lược đồ (alembic upgrade head) + seed dữ liệu gốc.

    Thay cho Base.metadata.create_all() tạm thời trước đây: DB cũ tạo bằng
    create_all được stamp đúng phiên bản rồi nâng cấp (xem init_db.upgrade_db).
    """
    setup_logging()
    Path(settings.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.WATCH_PATH).mkdir(parents=True, exist_ok=True)
    init_db.upgrade_db()
    with SessionLocal() as db:
        init_db.seed(db)
        db.commit()
    yield


app = FastAPI(
    title="SME AI Workforce API",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _trace_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    trace_id = request.headers.get("x-request-id") or new_trace_id()
    clear_context()
    bind_context(trace_id=trace_id[:64])
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id[:64]
    return response


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

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


# ─── Giao diện React đã build (Dockerfile chép vào STATIC_DIR) ───
_static = Path(settings.STATIC_DIR).resolve()
if (_static / "index.html").is_file():

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Tệp tĩnh có thật thì trả tệp; còn lại trả index.html (định tuyến phía
        trình duyệt). Không bao giờ phục vụ tệp nằm ngoài STATIC_DIR."""
        if full_path.startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Không tìm thấy điểm cuối.")
        candidate = (_static / full_path).resolve()
        if full_path and candidate.is_file() and _static in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
