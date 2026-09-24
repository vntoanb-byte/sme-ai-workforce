"""Kiểm thử domain/templates — 5 mẫu quy trình khớp TemplateCode, dùng đúng công
cụ có thật và qua đủ 5 phép kiểm chứng V-1..V-5 khi điền tham số hợp lệ."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from app.domain.templates.registry import (
    TEMPLATES,
    build_spec,
    get_template,
    list_templates,
    skeleton_spec,
    step_label,
)
from app.domain.validators import validate_spec
from app.schemas.workflow_spec import TemplateCode
from app.tools.base import load_all_tools


def _catalog() -> dict[str, dict]:
    return {
        code: {
            "is_enabled": True,
            "input_schema": cls.input_schema,
            "output_schema": cls.output_schema,
            "required_params": list(cls.required_params),
        }
        for code, cls in load_all_tools().items()
    }


def test_registry_matches_template_code_literal() -> None:
    # Đối chiếu NOTE trong schemas/workflow_spec.py: 5 mã Literal = 5 mẫu thật.
    assert set(TEMPLATES) == set(get_args(TemplateCode))
    assert get_template("khong_co") is None
    assert len(list_templates()) == 5


@pytest.mark.parametrize("code", sorted(TEMPLATES))
def test_template_shape(code: str) -> None:
    tpl = TEMPLATES[code]
    assert 3 <= len(tpl.examples) <= 5
    keys = [s.step_key for s in tpl.steps]
    assert len(keys) == len(set(keys))
    tools = load_all_tools()
    assert all(s.tool_code in tools for s in tpl.steps)
    for edge in tpl.edges:
        assert edge.from_key in keys and edge.to_key in keys
    for param in tpl.params:
        step_key, _, config_key = param.partition(".")
        assert step_key in keys and config_key, param


@pytest.mark.parametrize("code", sorted(TEMPLATES))
def test_filled_template_passes_all_validators(code: str, tmp_path: Path) -> None:
    config = {
        "scan_folder": {"path": str(tmp_path)},
        "reconcile": {"left_file": "a.xlsx", "right_file": "b.xlsx", "key_column": "Số HĐ"},
    }
    spec = build_spec(code, name="Thử", config=config)
    assert validate_spec(spec, _catalog()) == []


def test_unfilled_required_param_is_caught_by_v5() -> None:
    spec = build_spec("invoice_to_excel")  # scan_folder.path còn trống
    errors = validate_spec(spec, _catalog())
    assert [(e.rule, e.step_key) for e in errors] == [("V-5", "scan_folder")]


def test_skeleton_and_labels() -> None:
    skeleton = skeleton_spec("invoice_to_excel")
    assert skeleton["template_code"] == "invoice_to_excel"
    assert {e["condition"] for e in skeleton["edges"]} == {None, "pass", "fail"}
    assert step_label("invoice_to_excel", "write_excel", "x") == "Ghi hoá đơn đạt vào bảng tính"
    assert step_label("invoice_to_excel", "khong_co", "Mặc định") == "Mặc định"
