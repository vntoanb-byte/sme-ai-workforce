"""
Kiểu dữ liệu mô tả một mẫu quy trình (dùng chung cho các file mẫu và registry).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TemplateStep:
    step_key: str
    tool_code: str
    label: str
    config: dict[str, Any] = field(default_factory=dict)
    on_error: str = "stop"
    retry_max: int = 0


@dataclass(frozen=True)
class TemplateEdge:
    from_key: str
    to_key: str
    condition: str | None = None


@dataclass(frozen=True)
class WorkflowTemplate:
    code: str
    name: str
    description: str
    examples: tuple[str, ...]
    default_trigger: dict[str, Any]
    steps: tuple[TemplateStep, ...]
    edges: tuple[TemplateEdge, ...] = ()
    # "step_key.config_key" -> giải thích cho mô hình cần điền gì.
    params: dict[str, str] = field(default_factory=dict)

    def step(self, step_key: str) -> TemplateStep | None:
        return next((s for s in self.steps if s.step_key == step_key), None)
