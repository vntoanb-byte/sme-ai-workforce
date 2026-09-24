"""Kiểm thử services/workflow_service.py — nhãn lịch, tô-pô, lưu/duyệt phiên bản."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.domain.templates.registry import build_spec
from app.models.employee import AIEmployee
from app.services import workflow_service as ws


@pytest.mark.parametrize(
    ("expr", "label"),
    [
        ("0 8 * * *", "Mỗi ngày lúc 08:00"),
        ("30 17 * * 1-5", "Thứ Hai–Thứ Sáu lúc 17:30"),
        ("0 9 * * 1", "Thứ Hai lúc 09:00"),
        ("0 9 * * 1,3", "Thứ Hai, Thứ Tư lúc 09:00"),
        ("0 7 1 * *", "Ngày 1 hằng tháng lúc 07:00"),
        ("*/5 * * * *", "Theo lịch (*/5 * * * *)"),
        (None, "Theo lịch"),
    ],
)
def test_cron_label(expr: str | None, label: str) -> None:
    assert ws.cron_label(expr) == label


def test_template_code_mapping_roundtrip() -> None:
    assert ws.to_api_template_code("invoice_to_excel") == "TPL_INVOICE_TO_EXCEL"
    assert ws.from_api_template_code("TPL_INVOICE_TO_EXCEL") == "invoice_to_excel"
    assert ws.from_api_template_code("excel_clean") == "excel_clean"


def test_topo_levels_put_branches_on_same_level() -> None:
    keys = ["a", "b", "c", "pass_step", "fail_step"]
    edges = [("a", "b"), ("b", "c"), ("c", "pass_step"), ("c", "fail_step")]
    levels = ws.topo_levels(keys, edges)
    assert levels == {"a": 1, "b": 2, "c": 3, "pass_step": 4, "fail_step": 4}
    assert ws.topo_order(keys, edges) == keys


def test_topo_order_rejects_cycle() -> None:
    with pytest.raises(ValidationFailed):
        ws.topo_order(["a", "b"], [("a", "b"), ("b", "a")])


def _employee(db: Session) -> AIEmployee:
    emp = AIEmployee(name="Kế toán", job_description="Đọc hoá đơn hằng ngày", status="draft")
    db.add(emp)
    db.flush()
    return emp


def test_save_and_approve_roundtrip(db: Session, tmp_path: Path) -> None:
    emp = _employee(db)
    spec = build_spec(
        "invoice_to_excel", name="Kế toán hoá đơn",
        config={"scan_folder": {"path": str(tmp_path)}},
    )
    wf = ws.save_new_version(db, emp, spec)
    assert wf.version == 1 and wf.status == "pending"
    assert wf.schedule is not None and wf.schedule.is_enabled is False
    assert ws.spec_from_workflow(wf) == spec  # lưu rồi đọc lại không mất thông tin

    out = ws.workflow_out(wf)
    assert out["template_code"] == "TPL_INVOICE_TO_EXCEL"
    assert out["trigger"]["label"] == "Mỗi ngày lúc 08:00"
    branches = {s["step_key"]: s.get("branch") for s in out["steps"]}
    assert branches["write_excel"] == "pass" and branches["to_review"] == "fail"
    levels = {s["step_key"]: s["order_index"] for s in out["steps"]}
    assert levels["write_excel"] == levels["to_review"] == 4

    ws.approve(db, wf, None)
    assert wf.status == "approved" and wf.approved_at is not None
    assert emp.status == "active" and emp.current_workflow_id == wf.id
    assert wf.schedule.is_enabled is True
    assert wf.schedule.next_run_at is not None

    # Phiên bản mới → duyệt → phiên bản cũ bị lưu trữ, không sửa tại chỗ.
    wf2 = ws.save_new_version(db, emp, spec)
    assert wf2.version == 2
    ws.approve(db, wf2, None)
    db.refresh(wf)
    assert wf.status == "archived"
    assert emp.current_workflow_id == wf2.id


def test_approve_rejects_invalid_spec(db: Session) -> None:
    emp = _employee(db)
    wf = ws.save_new_version(db, emp, build_spec("invoice_to_excel"))  # thiếu path
    with pytest.raises(ValidationFailed) as exc:
        ws.approve(db, wf, None)
    assert exc.value.details[0]["rule"] == "V-5"
