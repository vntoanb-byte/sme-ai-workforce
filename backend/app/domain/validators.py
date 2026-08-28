"""
Kiểm chứng ngữ nghĩa đặc tả quy trình

Năm phép kiểm tra tất định, KHÔNG dùng mô hình. Đây là lớp chống ảo giác quan
trọng nhất.

  V-1: mọi tool_code phải tồn tại trong bảng tools và is_enabled=True
  V-2: step_key duy nhất, mọi cạnh trỏ tới bước có thật
  V-3: đồ thị không chứa chu trình — kiểm tra bằng sắp xếp tô-pô (thuật toán
    Kahn)
  V-4: output_schema của bước trước tương thích input_schema của bước sau
  V-5: tham số bắt buộc của từng công cụ có mặt và hợp lệ (cron đúng cú
    pháp, thư mục tồn tại)

`tools` truyền vào là ánh xạ tool_code -> thông tin công cụ, đọc theo kiểu
duck-typed (dict hoặc object có attribute: is_enabled, input_schema,
output_schema, required_params) — không import app/tools/base.py hay bất cứ
gì từ adapters/api/workers, giữ đúng ranh giới domain/ (xem ARCHITECTURE.md).
Bên gọi (services/) tự dựng ánh xạ này từ bảng `tools` trong DB.

Cú pháp cron được kiểm bằng apscheduler.triggers.cron.CronTrigger.from_crontab
— apscheduler đã là dependency của dự án (dùng cho lập lịch thật), không thêm
dependency mới.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from app.schemas.workflow_spec import WorkflowSpec


@dataclass(frozen=True)
class SpecError:
    rule: str
    step_key: str | None
    message: str


def _tool_attr(tool: Any, name: str, default: Any = None) -> Any:
    if tool is None:
        return default
    if isinstance(tool, dict):
        return tool.get(name, default)
    return getattr(tool, name, default)


def _schema_required_fields(schema: Any) -> set[str]:
    if not isinstance(schema, dict):
        return set()
    required = schema.get("required")
    if isinstance(required, list | tuple | set):
        return set(required)
    return set()


def _schema_available_fields(schema: Any) -> set[str] | None:
    if not isinstance(schema, dict):
        return None
    properties = schema.get("properties")
    if isinstance(properties, dict):
        return set(properties.keys())
    return None


def _v1_tool_exists_and_enabled(spec: WorkflowSpec, tools: Mapping[str, Any]) -> list[SpecError]:
    errors: list[SpecError] = []
    for step in spec.steps:
        tool = tools.get(step.tool_code)
        if tool is None:
            errors.append(SpecError(
                "V-1", step.step_key,
                f"Công cụ '{step.tool_code}' không tồn tại trong danh mục công cụ.",
            ))
            continue
        if not _tool_attr(tool, "is_enabled", False):
            errors.append(SpecError(
                "V-1", step.step_key,
                f"Công cụ '{step.tool_code}' đang bị tắt, không thể dùng trong quy trình.",
            ))
    return errors


def _v2_step_keys_and_edges_valid(spec: WorkflowSpec) -> list[SpecError]:
    errors: list[SpecError] = []
    seen: set[str] = set()
    for step in spec.steps:
        if step.step_key in seen:
            errors.append(SpecError(
                "V-2", step.step_key, f"Khoá bước '{step.step_key}' bị lặp lại.",
            ))
        seen.add(step.step_key)

    step_keys = {step.step_key for step in spec.steps}
    for edge in spec.edges:
        if edge.from_key not in step_keys:
            errors.append(SpecError(
                "V-2", edge.from_key,
                f"Cạnh trỏ từ bước không tồn tại '{edge.from_key}'.",
            ))
        if edge.to_key not in step_keys:
            errors.append(SpecError(
                "V-2", edge.to_key,
                f"Cạnh trỏ tới bước không tồn tại '{edge.to_key}'.",
            ))
    return errors


def _v3_no_cycles(spec: WorkflowSpec) -> list[SpecError]:
    step_keys = [step.step_key for step in spec.steps]
    valid_keys = set(step_keys)

    adjacency: dict[str, list[str]] = {key: [] for key in step_keys}
    in_degree: dict[str, int] = {key: 0 for key in step_keys}
    for edge in spec.edges:
        # Cạnh trỏ tới bước không tồn tại đã được V-2 báo lỗi riêng — bỏ qua
        # ở đây để tránh gây lỗi phái sinh (KeyError) hoặc báo trùng.
        if edge.from_key not in valid_keys or edge.to_key not in valid_keys:
            continue
        adjacency[edge.from_key].append(edge.to_key)
        in_degree[edge.to_key] += 1

    queue = [key for key in step_keys if in_degree[key] == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in adjacency[node]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if visited < len(step_keys):
        cyclic = sorted(key for key in step_keys if in_degree[key] > 0)
        return [SpecError(
            "V-3", None,
            f"Đồ thị quy trình chứa chu trình, liên quan các bước: {', '.join(cyclic)}.",
        )]
    return []


def _v4_schema_compatibility(spec: WorkflowSpec, tools: Mapping[str, Any]) -> list[SpecError]:
    errors: list[SpecError] = []
    step_by_key = {step.step_key: step for step in spec.steps}

    for edge in spec.edges:
        from_step = step_by_key.get(edge.from_key)
        to_step = step_by_key.get(edge.to_key)
        if from_step is None or to_step is None:
            continue  # đã báo ở V-2

        from_tool = tools.get(from_step.tool_code)
        to_tool = tools.get(to_step.tool_code)
        if from_tool is None or to_tool is None:
            continue  # đã báo ở V-1

        output_fields = _schema_available_fields(_tool_attr(from_tool, "output_schema"))
        required_fields = _schema_required_fields(_tool_attr(to_tool, "input_schema"))
        if output_fields is None or not required_fields:
            # Thiếu lược đồ để so sánh -> không đủ căn cứ kết luận, bỏ qua
            # thay vì báo lỗi false-positive.
            continue

        missing = sorted(required_fields - output_fields)
        if missing:
            errors.append(SpecError(
                "V-4", to_step.step_key,
                f"Bước '{to_step.step_key}' cần trường {missing} nhưng bước trước "
                f"'{from_step.step_key}' không tạo ra.",
            ))
    return errors


def _v5_trigger_and_required_params(
    spec: WorkflowSpec, tools: Mapping[str, Any]
) -> list[SpecError]:
    errors: list[SpecError] = []
    trigger = spec.trigger

    if trigger.type == "cron":
        try:
            CronTrigger.from_crontab(trigger.cron_expr or "")
        except Exception as exc:
            errors.append(SpecError(
                "V-5", None,
                f"Biểu thức lịch (cron) '{trigger.cron_expr}' không hợp lệ: {exc}",
            ))
    elif trigger.type == "file_watch":
        watch_path = trigger.watch_path or ""
        if not os.path.isdir(watch_path):
            errors.append(SpecError(
                "V-5", None, f"Thư mục theo dõi '{watch_path}' không tồn tại.",
            ))

    for step in spec.steps:
        tool = tools.get(step.tool_code)
        if tool is None:
            continue  # đã báo ở V-1
        required_params = _tool_attr(tool, "required_params") or []
        for param in required_params:
            value = step.config.get(param)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(SpecError(
                    "V-5", step.step_key,
                    f"Thiếu tham số bắt buộc '{param}' cho công cụ '{step.tool_code}'.",
                ))
    return errors


def validate_spec(spec: WorkflowSpec, tools: Mapping[str, Any]) -> list[SpecError]:
    """Chạy đủ 5 phép kiểm tra V-1..V-5 trên `spec`.

    Trả về danh sách rỗng nghĩa là hợp lệ. `tools` là ánh xạ tool_code ->
    thông tin công cụ (xem docstring module) do bên gọi (services/) dựng từ
    bảng `tools` trong DB — domain/ không tự truy DB.
    """
    errors: list[SpecError] = []
    errors.extend(_v1_tool_exists_and_enabled(spec, tools))
    errors.extend(_v2_step_keys_and_edges_valid(spec))
    errors.extend(_v3_no_cycles(spec))
    errors.extend(_v4_schema_compatibility(spec, tools))
    errors.extend(_v5_trigger_and_required_params(spec, tools))
    return errors
