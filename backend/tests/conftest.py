"""
Cấu hình chung cho pytest

Fixture dùng lại ở mọi bài kiểm thử:
  - engine / session_factory / db — CSDL SQLite tạm trong FILE (không phải
    :memory: — mỗi connection :memory: là 1 DB riêng, không mô phỏng đúng WAL/FK
    thật), đủ PRAGMA + event begin giống app/db/session.py, đã seed dữ liệu gốc
    (vai trò, danh mục công cụ, cấu hình mặc định — db/init_db.seed).
  - fake_llm — LLMProvider giả (FakeLLM), mặc định trả 1 hoá đơn hợp lệ
    (VALID_INVOICE_PAYLOAD) đã tự xác nhận qua domain/qc_rules.run_qc() thật cho
    kết quả 8/8 pass.
  - users — 3 tài khoản: ketoan (USER), quanly (USER+MANAGER), admin (cả 3).
  - client (admin) / manager_client / user_client / anon_client — TestClient
    FastAPI đã ghi đè get_db/get_llm/get_storage/get_session_factory (KHÔNG chạm
    DB/kho tệp thật), kèm header Authorization của người dùng tương ứng.
  - scan_dir — thư mục quét tạm, gán vào settings.WATCH_PATH (công cụ fs.* chỉ
    đọc được tệp dưới thư mục này).
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.storage_local import LocalFileStorage
from app.api.deps import get_db, get_llm, get_session_factory, get_storage
from app.core import security
from app.core.config import settings
from app.db import init_db
from app.db.base import Base
from app.main import app
from app.models.user import User
from app.ports.llm import LLMResult
from app.services import auth_service

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
def engine(tmp_path: Path) -> Generator[Engine, None, None]:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'conftest.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    _register_sqlite_events(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Phiên CSDL tạm, schema đầy đủ + dữ liệu gốc đã seed."""
    session = session_factory()
    init_db.seed(session)
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def scan_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "scan"
    path.mkdir()
    monkeypatch.setattr(settings, "WATCH_PATH", str(path))
    return path


@pytest.fixture()
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(str(tmp_path / "artifacts"))


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


PASSWORD = "matkhau123"


@pytest.fixture()
def users(db: Session) -> dict[str, User]:
    created = {
        "ketoan": auth_service.create_user(
            db, username="ketoan", full_name="Nguyễn Thị Hoa", email="hoa@example.vn",
            password=PASSWORD, roles=["USER"],
        ),
        "quanly": auth_service.create_user(
            db, username="quanly", full_name="Trần Thu Hương", email="huong@example.vn",
            password=PASSWORD, roles=["USER", "MANAGER"],
        ),
        "admin": auth_service.create_user(
            db, username="admin", full_name="Quản trị hệ thống", email="admin@example.vn",
            password=PASSWORD, roles=["USER", "MANAGER", "ADMIN"],
        ),
    }
    db.commit()
    return created


@pytest.fixture()
def _overrides(
    db: Session,
    fake_llm: FakeLLM,
    storage: LocalFileStorage,
    session_factory: sessionmaker[Session],
) -> Generator[None, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        # Dùng chung phiên của test (để test đọc/ghi cùng dữ liệu) nhưng kết thúc
        # transaction + bỏ cache đầu mỗi request — giống production (mỗi request
        # một phiên mới). Thiếu bước này phiên giữ snapshot đọc WAL cũ, không
        # thấy dữ liệu worker vừa ghi ở phiên khác.
        db.commit()
        db.expire_all()
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm] = lambda: fake_llm
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def _client_for(user: User | None) -> TestClient:
    client = TestClient(app)
    if user is not None:
        token = security.create_access_token(user.id, auth_service.role_codes(user))
        client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture()
def client(_overrides: None, users: dict[str, User]) -> TestClient:
    """Client đăng nhập bằng tài khoản admin (đủ cả 3 vai trò)."""
    return _client_for(users["admin"])


@pytest.fixture()
def manager_client(_overrides: None, users: dict[str, User]) -> TestClient:
    return _client_for(users["quanly"])


@pytest.fixture()
def user_client(_overrides: None, users: dict[str, User]) -> TestClient:
    return _client_for(users["ketoan"])


@pytest.fixture()
def anon_client(_overrides: None) -> TestClient:
    return _client_for(None)


# ─── Tiện ích cho kiểm thử luồng quy trình ───


def invoice_payload(invoice_no: str, *, bad_total: bool = False) -> dict[str, Any]:
    """Hoá đơn hợp lệ 8/8 quy tắc (ngày lập = 10 ngày trước hôm nay để QC-05 luôn
    đạt); bad_total=True làm lệch tổng thanh toán 10.000đ → QC-02 (critical) trượt."""
    from datetime import date, timedelta

    total = 110000 + (10000 if bad_total else 0)
    return {
        **VALID_INVOICE_PAYLOAD,
        "invoice_no": invoice_no,
        "issue_date": (date.today() - timedelta(days=10)).isoformat(),
        "totals": {**VALID_INVOICE_PAYLOAD["totals"], "total": str(total)},
    }


def png_bytes(seed: int) -> bytes:
    """Ảnh PNG nhỏ, khác nhau theo seed (khử trùng sha256 không gộp nhầm)."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (24, 16), color=(seed % 256, (seed * 7) % 256, 90)).save(buf, format="PNG")
    return buf.getvalue()


class SmartLLM:
    """LLM giả định tuyến theo schema của lời gọi:
      - phân loại mẫu (schema có template_code enum) → classify_code
      - điền WorkflowSpec → spec (dict) hoặc hàm dựng spec
      - đọc hoá đơn (InvoiceExtraction) → lần lượt từng phần tử của `invoices`
        (phần tử là Exception thì ném ra)
      - phân loại tài liệu (label enum) → label
      - không schema (thử kết nối) → "OK"
    """

    def __init__(
        self,
        *,
        classify_code: str | None = "invoice_to_excel",
        spec: dict[str, Any] | None = None,
        invoices: list[Any] | None = None,
        label: str = "hoa_don",
    ) -> None:
        self.classify_code = classify_code
        self.spec = spec
        self.invoices = list(invoices or [])
        self.label = label
        self.calls: list[str] = []

    def _result(self, parsed: dict[str, Any] | None, content: str = "{}") -> LLMResult:
        return LLMResult(
            content=content, parsed=parsed, model="fake-vl", token_in=100, token_out=50,
            latency_ms=1200,
        )

    def complete(self, messages, *, schema=None, images=None, timeout=None):  # noqa: ANN001, ANN201
        props = (schema or {}).get("properties", {})
        if schema is None:
            self.calls.append("ping")
            return self._result(None, "OK")
        if "template_code" in props and "steps" not in props:
            self.calls.append("classify")
            return self._result({"template_code": self.classify_code})
        if "steps" in props:
            self.calls.append("spec")
            return self._result(self.spec)
        if "label" in props:
            self.calls.append("label")
            return self._result({"label": self.label})
        self.calls.append("invoice")
        item = self.invoices.pop(0) if self.invoices else invoice_payload("9999999")
        if isinstance(item, Exception):
            raise item
        return self._result(item)


@pytest.fixture()
def make_employee(db: Session, scan_dir: Path):  # noqa: ANN201
    """Tạo nhân viên AI + quy trình từ mẫu (không qua mô hình), đã duyệt."""
    from app.domain.templates.registry import build_spec
    from app.models.employee import AIEmployee
    from app.services import workflow_service

    def _make(
        code: str = "invoice_to_excel",
        *,
        name: str = "Kế toán hoá đơn",
        config: dict[str, dict[str, Any]] | None = None,
        trigger: dict[str, Any] | None = None,
        approve: bool = True,
    ) -> AIEmployee:
        employee = AIEmployee(name=name, job_description=f"Mô tả cho {name}", status="draft")
        db.add(employee)
        db.flush()
        spec = build_spec(
            code,
            name=name,
            trigger=trigger or {"type": "manual"},
            config={"scan_folder": {"path": str(scan_dir), "stable_seconds": 0}, **(config or {})},
        )
        wf = workflow_service.save_new_version(db, employee, spec)
        if approve:
            workflow_service.approve(db, wf, None)
        db.commit()
        return employee

    return _make


@pytest.fixture()
def queue(engine: Engine):  # noqa: ANN201
    from app.adapters.queue_sqlite import SQLiteJobQueue

    return SQLiteJobQueue(engine)
