"""
Kiểm thử tập quy tắc

Mỗi quy tắc QC-01..QC-08 có ít nhất một ca đạt và một ca không đạt; ca biên
sai lệch đúng 1 đồng (đạt) và 2 đồng (không đạt); mã số thuế 10 số, 13 số,
9 số, có chữ cái.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Any

import pytest

from app.domain import qc_rules


def _invoice() -> dict[str, Any]:
    return {
        "invoice_no": "0000123",
        "invoice_form": "1C26TAA",
        "issue_date": (date.today() - timedelta(days=5)).isoformat(),
        "currency": "VND",
        "seller": {"name": "Công ty TNHH ABC", "tax_code": "0101234565"},
        "line_items": [
            {"line_no": 1, "description": "A", "unit": "cái", "quantity": "2",
             "unit_price": "30000", "amount": "60000"},
            {"line_no": 2, "description": "B", "unit": "cái", "quantity": "1",
             "unit_price": "40000", "amount": "40000"},
        ],
        "totals": {"subtotal": "100000", "vat_rate": "10", "vat_amount": "10000",
                   "total": "110000"},
    }


def _result(
    code: str, data: dict[str, Any], existing: list[str] | None = None
) -> qc_rules.QCResult:
    results, _ = qc_rules.run_qc(data, existing_invoice_numbers=existing)
    return next(r for r in results if r.rule_code == code)


def test_valid_invoice_passes_all_eight_rules() -> None:
    results, needs_review = qc_rules.run_qc(_invoice())
    assert [r.rule_code for r in results] == [f"QC-0{i}" for i in range(1, 9)]
    assert all(r.passed for r in results)
    assert needs_review is False


def test_qc01_line_sum_vs_subtotal() -> None:
    data = _invoice()
    data["totals"]["subtotal"] = "100001"  # lệch 1 đồng → đạt
    assert _result("QC-01", data).passed
    data["totals"]["subtotal"] = "100002"  # lệch 2 đồng → không đạt
    bad = _result("QC-01", data)
    assert not bad.passed and bad.field == "totals.subtotal"


def test_qc02_subtotal_plus_vat_equals_total_tolerance() -> None:
    data = _invoice()
    data["totals"]["total"] = "110001"
    assert _result("QC-02", data).passed
    data["totals"]["total"] = "110002"
    bad = _result("QC-02", data)
    assert not bad.passed
    assert bad.field == "totals.total"


@pytest.mark.parametrize(("rate", "ok"), [("0", True), ("5", True), ("8", True), ("10", True),
                                            ("7", False), ("12", False)])
def test_qc03_vat_rate(rate: str, ok: bool) -> None:
    data = _invoice()
    data["totals"]["vat_rate"] = rate
    assert _result("QC-03", data).passed is ok


@pytest.mark.parametrize(
    ("tax_code", "ok"),
    [
        ("0101234565", True),          # 10 số, chữ số kiểm tra đúng
        ("0101234565-001", True),      # 13 số (mã chi nhánh)
        ("0101234566", False),         # sai chữ số kiểm tra
        ("010123456", False),          # 9 số
        ("0309884I72", False),         # có chữ cái (AI đọc nhầm 1 → I)
        ("", False),
    ],
)
def test_qc04_seller_tax_code(tax_code: str, ok: bool) -> None:
    data = _invoice()
    data["seller"]["tax_code"] = tax_code
    assert _result("QC-04", data).passed is ok


def test_qc05_issue_date_reasonable() -> None:
    data = _invoice()
    assert _result("QC-05", data).passed
    data["issue_date"] = (date.today() + timedelta(days=3)).isoformat()
    assert not _result("QC-05", data).passed
    data["issue_date"] = (date.today() - timedelta(days=365 * 3)).isoformat()
    assert not _result("QC-05", data).passed


def test_qc06_duplicate_invoice_number() -> None:
    data = _invoice()
    assert _result("QC-06", data, ["0000999"]).passed
    assert not _result("QC-06", data, ["0000123"]).passed


def test_qc07_required_fields() -> None:
    data = _invoice()
    assert _result("QC-07", data).passed
    missing = copy.deepcopy(data)
    missing["seller"]["name"] = "  "
    assert not _result("QC-07", missing).passed


def test_qc08_line_amount_matches_quantity_times_price() -> None:
    data = _invoice()
    assert _result("QC-08", data).passed
    data["line_items"][0]["amount"] = "60002"
    data["totals"]["subtotal"] = "100002"
    assert not _result("QC-08", data).passed


def test_critical_failure_sets_needs_review() -> None:
    data = _invoice()
    data["totals"]["total"] = "120000"
    _, needs_review = qc_rules.run_qc(data)
    assert needs_review is True


def test_warning_alone_does_not_set_needs_review() -> None:
    # QC-05 (ngày lập) là mức warning — chỉ riêng nó trượt thì không chặn tự động.
    data = _invoice()
    data["issue_date"] = (date.today() + timedelta(days=3)).isoformat()
    results, needs_review = qc_rules.run_qc(data)
    failed = [r for r in results if not r.passed]
    assert [(r.rule_code, r.severity) for r in failed] == [("QC-05", "warning")]
    assert needs_review is False


def test_works_with_object_input() -> None:
    class Obj:
        def __init__(self, **kw: Any) -> None:
            self.__dict__.update(kw)

    data = _invoice()
    obj = Obj(**{**data, "seller": Obj(**data["seller"]), "totals": Obj(**data["totals"])})
    results, needs_review = qc_rules.run_qc(obj)
    assert all(r.passed for r in results)
    assert needs_review is False
