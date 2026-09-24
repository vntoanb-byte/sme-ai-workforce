"""Kiểm thử API nhân viên AI + quy trình (biên dịch mô tả tiếng Việt → duyệt)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_llm
from app.domain.templates.registry import skeleton_spec
from app.main import app
from app.models.audit import AuditLog, LlmCall
from app.models.employee import AIEmployee
from tests.conftest import SmartLLM

DESC = "Mỗi sáng 8 giờ đọc hoá đơn mới trong thư mục Scan rồi nhập vào SoHoaDon2026.xlsx"


def _spec(scan_dir: Path) -> dict[str, Any]:
    spec = skeleton_spec("invoice_to_excel")
    spec["name"] = "Kế toán hoá đơn"
    spec["steps"][0]["config"]["path"] = str(scan_dir)
    spec["steps"][3]["config"]["file"] = "SoHoaDon2026.xlsx"
    return spec


@pytest.fixture()
def smart(client: TestClient) -> SmartLLM:
    llm = SmartLLM()
    app.dependency_overrides[get_llm] = lambda: llm
    return llm


def _create(client: TestClient, smart: SmartLLM, scan_dir: Path) -> dict[str, Any]:
    smart.spec = _spec(scan_dir)
    resp = client.post("/api/v1/employees", json={"name": "Kế toán hoá đơn", "job_description": DESC})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_create_employee_compiles_workflow(
    client: TestClient, smart: SmartLLM, scan_dir: Path, db: Session
) -> None:
    body = _create(client, smart, scan_dir)
    assert body["ok"] is True and body["errors"] == []
    wf = body["workflow"]
    assert wf["template_code"] == "TPL_INVOICE_TO_EXCEL"
    assert wf["status"] == "pending" and wf["version"] == 1
    assert wf["trigger"] == {
        "type": "cron", "label": "Mỗi ngày lúc 08:00", "cron_expr": "0 8 * * *",
        "watch_path": None, "timezone": "Asia/Ho_Chi_Minh",
    }
    steps = {s["step_key"]: s for s in wf["steps"]}
    assert steps["write_excel"]["branch"] == "pass" and steps["to_review"]["branch"] == "fail"
    assert steps["read_invoice"]["label"] == "AI đọc hoá đơn → dữ liệu có cấu trúc"
    assert smart.calls == ["classify", "spec"]

    # Mô tả gốc được lưu để cải tiến prompt; mọi lời gọi mô hình được ghi nhận.
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "compiler.compile"))
    assert audit is not None and DESC in (audit.detail_json or "")
    assert db.scalar(select(func.count(LlmCall.id))) == 2

    emp = client.get(f"/api/v1/employees/{wf['employee_id']}").json()
    assert emp["status"] == "draft"
    assert emp["workflow_id"] == wf["id"]
    assert emp["schedule_label"] is None  # chưa duyệt → chưa có lịch hiệu lực


def test_compile_failure_returns_errors_and_creates_nothing(
    client: TestClient, smart: SmartLLM, db: Session
) -> None:
    smart.classify_code = None  # mô hình không khớp mẫu nào
    resp = client.post(
        "/api/v1/employees",
        json={"name": "x", "job_description": "Gửi email chúc mừng sinh nhật khách hàng"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False and body["workflow"] is None
    assert body["errors"][0]["rule"] == "COMPILE-0"
    assert db.scalar(select(func.count(AIEmployee.id))) == 0


def test_invalid_spec_reports_validator_errors(
    client: TestClient, smart: SmartLLM, scan_dir: Path
) -> None:
    spec = _spec(scan_dir)
    spec["steps"][3]["tool_code"] = "email.send"  # mô hình bịa công cụ
    smart.spec = spec
    body = client.post(
        "/api/v1/employees", json={"name": "x", "job_description": DESC}
    ).json()
    assert body["ok"] is False
    assert any(e["rule"] == "V-1" and e["step_key"] == "write_excel" for e in body["errors"])
    assert smart.calls.count("spec") == 3  # thử lại đủ 3 lần kèm lỗi


def test_approve_activates_and_schedules(
    client: TestClient, smart: SmartLLM, scan_dir: Path
) -> None:
    wf = _create(client, smart, scan_dir)["workflow"]
    emp_id = wf["employee_id"]
    # Chưa duyệt thì không bật được.
    resp = client.patch(f"/api/v1/employees/{emp_id}", json={"status": "active"})
    assert resp.status_code == 409

    approved = client.post(f"/api/v1/workflows/{wf['id']}/approve?employee_id={emp_id}")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved" and approved.json()["approved_at"].endswith("Z")

    emp = client.get(f"/api/v1/employees/{emp_id}").json()
    assert emp["status"] == "active"
    assert emp["schedule_label"] == "Mỗi ngày lúc 08:00"
    assert emp["next_run_at"] is not None

    paused = client.patch(f"/api/v1/employees/{emp_id}", json={"status": "paused", "name": "KT"})
    assert paused.json()["status"] == "paused" and paused.json()["name"] == "KT"
    assert paused.json()["next_run_at"] is None

    archived = client.delete(f"/api/v1/employees/{emp_id}")
    assert archived.json()["status"] == "archived"
    assert client.get("/api/v1/employees").json()["total"] == 0  # mặc định ẩn bản lưu trữ
    assert client.get("/api/v1/employees?status=archived").json()["total"] == 1
    assert client.patch(f"/api/v1/employees/{emp_id}", json={"status": "active"}).status_code == 409


def test_list_filter_and_search(client: TestClient, make_employee) -> None:
    make_employee(name="Kế toán hoá đơn")
    make_employee(name="Báo cáo cuối ngày", approve=False)
    resp = client.get("/api/v1/employees?q=báo cáo")
    assert [e["name"] for e in resp.json()["items"]] == ["Báo cáo cuối ngày"]
    assert client.get("/api/v1/employees?status=active").json()["total"] == 1
    page = client.get("/api/v1/employees?page=2&page_size=1").json()
    assert page["page"] == 2 and len(page["items"]) == 1 and page["total"] == 2


def test_put_workflow_creates_new_version_and_validate(
    client: TestClient, smart: SmartLLM, scan_dir: Path
) -> None:
    wf = _create(client, smart, scan_dir)["workflow"]
    edited = _spec(scan_dir)
    edited["template_code"] = "TPL_INVOICE_TO_EXCEL"  # nhận cả mã kiểu frontend
    edited["trigger"] = {"type": "cron", "cron_expr": "30 17 * * 1-5"}

    ok = client.post(f"/api/v1/workflows/{wf['id']}/validate", json=edited)
    assert ok.json() == {"ok": True, "errors": []}

    bad = dict(edited, trigger={"type": "cron", "cron_expr": "99 99 * * *"})
    result = client.post(f"/api/v1/workflows/{wf['id']}/validate", json=bad).json()
    assert result["ok"] is False and result["errors"][0]["rule"] == "V-5"
    assert client.put(f"/api/v1/workflows/{wf['id']}", json=bad).status_code == 422

    v2 = client.put(f"/api/v1/workflows/{wf['id']}", json=edited)
    assert v2.status_code == 200
    assert v2.json()["version"] == 2
    assert v2.json()["trigger"]["label"] == "Thứ Hai–Thứ Sáu lúc 17:30"
    assert client.get(f"/api/v1/workflows/{wf['id']}").json()["version"] == 1  # bản cũ giữ nguyên

    malformed = client.put(f"/api/v1/workflows/{wf['id']}", json={"steps": []})
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "VALIDATION_FAILED"


def test_tools_catalog(client: TestClient) -> None:
    tools = client.get("/api/v1/tools").json()
    codes = [t["code"] for t in tools]
    assert "vision.extract_invoice" in codes and len(codes) == 14
    fs = next(t for t in tools if t["code"] == "fs.list_new_files")
    assert fs["required_params"] == ["path"] and fs["category"] == "fs"
