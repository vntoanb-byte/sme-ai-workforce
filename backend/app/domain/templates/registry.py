"""
Sổ đăng ký mẫu quy trình

Tập hợp các mẫu quy trình đã khai báo sẵn. Bộ biên dịch chỉ được chọn trong
tập này (ADR-002).

  - WorkflowTemplate: code, name, description, examples (few-shot cho bước phân
    loại), default_trigger, steps cố định, edges cố định, params (tham số mà bộ
    biên dịch cần điền từ mô tả của người dùng).
  - TEMPLATES / get_template(code) / list_templates().
  - skeleton_spec(code) → dict đúng cấu trúc WorkflowSpec, dùng làm "bộ khung"
    trong prompt điền tham số.
  - build_spec(...) → WorkflowSpec dựng thẳng từ mẫu, KHÔNG cần mô hình (dùng
    cho seed dữ liệu demo và kiểm thử).

Thêm mẫu mới = thêm một file trong thư mục này + một dòng trong _MODULES,
KHÔNG sửa compiler.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from app.domain.templates.base import TemplateEdge, TemplateStep, WorkflowTemplate
from app.schemas.workflow_spec import WorkflowSpec

__all__ = [
    "TEMPLATES",
    "TemplateEdge",
    "TemplateStep",
    "WorkflowTemplate",
    "build_spec",
    "get_template",
    "list_templates",
    "skeleton_spec",
    "step_label",
]


def _load() -> dict[str, WorkflowTemplate]:
    from app.domain.templates import (
        doc_classify,
        excel_clean,
        excel_reconcile,
        invoice_report,
        invoice_to_excel,
    )

    modules = (invoice_to_excel, invoice_report, excel_clean, excel_reconcile, doc_classify)
    return {m.TEMPLATE.code: m.TEMPLATE for m in modules}


TEMPLATES: dict[str, WorkflowTemplate] = _load()


def get_template(code: str) -> WorkflowTemplate | None:
    return TEMPLATES.get(code)


def list_templates() -> list[WorkflowTemplate]:
    return list(TEMPLATES.values())


def skeleton_spec(code: str) -> dict[str, Any]:
    """Bộ khung WorkflowSpec (dict) của mẫu — đúng step_key/tool_code/edges."""
    tpl = TEMPLATES[code]
    return {
        "template_code": tpl.code,
        "name": tpl.name,
        "description": tpl.description,
        "trigger": copy.deepcopy(tpl.default_trigger),
        "steps": [
            {
                "step_key": s.step_key,
                "tool_code": s.tool_code,
                "config": copy.deepcopy(s.config),
                "on_error": s.on_error,
                "retry_max": s.retry_max,
            }
            for s in tpl.steps
        ],
        "edges": [
            {"from_key": e.from_key, "to_key": e.to_key, "condition": e.condition}
            for e in tpl.edges
        ],
    }


def build_spec(
    code: str,
    *,
    name: str | None = None,
    description: str | None = None,
    trigger: Mapping[str, Any] | None = None,
    config: Mapping[str, Mapping[str, Any]] | None = None,
) -> WorkflowSpec:
    """Dựng WorkflowSpec từ mẫu + tham số, không qua mô hình.

    `config` là ánh xạ step_key -> các khoá config cần ghi đè.
    """
    data = skeleton_spec(code)
    if name:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if trigger is not None:
        data["trigger"] = dict(trigger)
    for step in data["steps"]:
        step["config"].update((config or {}).get(step["step_key"], {}))
    return WorkflowSpec.model_validate(data)


def step_label(code: str, step_key: str, fallback: str) -> str:
    """Nhãn hiển thị của bước theo mẫu; bước không có trong mẫu dùng `fallback`."""
    tpl = TEMPLATES.get(code)
    step = tpl.step(step_key) if tpl else None
    return step.label if step else fallback
