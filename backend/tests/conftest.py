"""
Cấu hình chung cho pytest

Các fixture dùng lại ở mọi bài kiểm thử (TASK-006).

Đã hiện thực:
  - fixture db — CSDL SQLite tạm trong FILE (không phải :memory:, nhất quán với
    TASK-005a/b — mỗi connection :memory: là 1 DB riêng, không mô phỏng đúng
    hành vi WAL/FK thật), đăng ký đủ PRAGMA + event begin giống app/db/session.py.
  - fixture fake_llm — LLMProvider giả (class FakeLLM), mặc định trả về 1 hoá
    đơn hợp lệ (VALID_INVOICE_PAYLOAD) đã tự xác nhận qua domain/qc_rules.run_qc()
    thật cho kết quả 8/8 pass (needs_review=False) — xem ghi chú dưới.
  - fixture client — TestClient FastAPI, ghi đè get_db/get_llm/get_storage
    (KHÔNG chạm DB/kho tệp thật của tiến trình dev).

CHƯA hiện thực (ngoài phạm vi TASK-006, xem IMPLEMENTATION_PLAN.md):
  - fixture auth_headers — TASK-006 quyết định KHÔNG auth cho endpoint documents,
    làm khi có models/user.py + JWT thật nối vào api/deps.py.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.storage_local import LocalFileStorage
from app.api.deps import get_db, get_llm, get_storage
from app.db.base import Base
from app.main import app
from app.ports.llm import LLMResult

# Hoá đơn hợp lệ dùng cho test — đã tự chạy domain/qc_rules.run_qc() thật với
# đúng dữ liệu này (không đoán): 8/8 quy tắc pass, needs_review=False. Mã số
# thuế "0101234565" tính đúng theo thuật toán modulus-11 (TAX_CODE_WEIGHTS)
# của qc_rules.py, không phải số bịa.
VALID_INVOICE_PAYLOAD: dict[str, Any] = {
    "invoice_no": "0000123",
    "invoice_form": "1C26TAA",
    "issue_date": "2026-08-20",
    "currency": "VND",
    "seller": {"name": "Công ty TNHH ABC", "tax_code": "0101234565", "address": None},
    "buyer": None,
    "line_items": [
        {
            "line_no": 1,
            "description": "Dịch vụ tư vấn",
            "unit": "gói",
            "quantity": "1",
            "unit_price": "100000",
            "amount": "100000",
        }
    ],
    "totals": {
        "subtotal": "100000",
        "vat_rate": "10",
        "vat_amount": "10000",
        "total": "110000",
    },
}


def _register_sqlite_events(engine) -> None:  # noqa: ANN001
    """Copy đúng 2 event trong app/db/session.py — test độc lập, không đụng
    engine/DB thật của tiến trình dev (giống test_models_group_d.py)."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _do_begin(conn) -> None:  # noqa: ANN001
        if conn.get_execution_options().get("sqlite_begin_immediate"):
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            conn.exec_driver_sql("BEGIN")
        conn.exec_driver_sql("PRAGMA defer_foreign_keys=ON")


@pytest.fixture()
def db(tmp_path: Path) -> Generator[Session, None, None]:
    """CSDL SQLite tạm cho 1 test — schema đầy đủ 21 bảng qua Base.metadata."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'conftest.db').as_posix()}")
    _register_sqlite_events(engine)
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class FakeLLM:
    """LLMProvider giả (Protocol app.ports.llm.LLMProvider) — trả phản hồi ghi
    sẵn, KHÔNG gọi mạng thật. Ghi lại mọi lời gọi vào self.calls để test kiểm
    tra tham số (schema=, images=) nếu cần."""

    def __init__(
        self,
        parsed: dict[str, Any] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._parsed = parsed
        self._raise_exc = raise_exc
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages,  # noqa: ANN001
        *,
        schema: dict[str, Any] | None = None,
        images=None,  # noqa: ANN001
        timeout: float | None = None,
    ) -> LLMResult:
        self.calls.append({"messages": messages, "schema": schema, "images": images})
        if self._raise_exc is not None:
            raise self._raise_exc
        return LLMResult(
            content="{}",
            parsed=self._parsed,
            model="fake-model-v1",
            token_in=10,
            token_out=10,
            latency_ms=1,
        )


@pytest.fixture()
def fake_llm() -> FakeLLM:
    """Mặc định: LLM giả trả về 1 hoá đơn hợp lệ (VALID_INVOICE_PAYLOAD)."""
    return FakeLLM(parsed=VALID_INVOICE_PAYLOAD)


@pytest.fixture()
def client(
    db: Session, fake_llm: FakeLLM, tmp_path: Path
) -> Generator[TestClient, None, None]:
    """TestClient FastAPI với get_db/get_llm/get_storage bị ghi đè.

    auth_headers CHƯA hiện thực — endpoint documents hiện không yêu cầu auth
    (quyết định TASK-006, xem IMPLEMENTATION_PLAN.md).
    """
    storage = LocalFileStorage(str(tmp_path / "artifacts"))

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm] = lambda: fake_llm
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
