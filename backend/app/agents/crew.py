"""
Định nghĩa tác tử (crew) — CHẾ ĐỘ TUẦN TỰ

Tác tử ở đây chỉ ĐIỀU PHỐI việc gọi công cụ theo thứ tự ĐÃ ĐƯỢC KIỂM CHỨNG
TRƯỚC (domain/validators, sắp xếp tô-pô) — không tự suy luận lại kế hoạch, không
có vòng lặp tự chủ (ADR-002).

  - Ba tác tử: Tài liệu (fs.*, doc.*, vision.*), Dữ liệu (xlsx.*, report.*),
    Kiểm soát (qc.*).
  - Mỗi tác tử chỉ được gọi công cụ trong phạm vi của mình — lớp phòng vệ thứ
    hai chống cấu hình sai (sau V-1): một bước gán công cụ ngoài mọi phạm vi bị
    từ chối ngay khi dựng crew, trước khi chạy bất kỳ bước nào.
  - build_crew(steps) → SequentialCrew với danh sách nhiệm vụ theo đúng thứ tự.

Quyết định hiện thực: dùng vòng lặp tuần tự thuần Python thay cho thư viện
CrewAI — docstring gốc cho phép ("kiến trúc không phụ thuộc vào CrewAI"), và
CrewAI 0.80 kéo theo hàng trăm gói phụ thuộc (không cài được trong môi trường
offline — xem backend/requirements-no-crewai.txt), trong khi Process.sequential
không cần suy luận của mô hình ở tầng điều phối.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.core.errors import ValidationFailed
from app.tools.base import ToolBase, ToolContext, ToolResult, get_tool


@dataclass(frozen=True)
class Agent:
    key: str
    role: str
    goal: str
    tool_prefixes: tuple[str, ...]

    def allows(self, tool_code: str) -> bool:
        return any(tool_code.startswith(prefix) for prefix in self.tool_prefixes)


DOC_AGENT = Agent(
    "doc", "Tác tử Tài liệu", "Lấy tệp và đọc nội dung chứng từ", ("fs.", "doc.", "vision.")
)
DATA_AGENT = Agent("data", "Tác tử Dữ liệu", "Ghi bảng tính và lập báo cáo", ("xlsx.", "report."))
QC_AGENT = Agent("qc", "Tác tử Kiểm soát", "Kiểm tra số liệu, chuyển người xác nhận", ("qc.",))
AGENTS: tuple[Agent, ...] = (DOC_AGENT, DATA_AGENT, QC_AGENT)


def agent_for(tool_code: str) -> Agent:
    for agent in AGENTS:
        if agent.allows(tool_code):
            return agent
    raise ValidationFailed(
        f"Công cụ '{tool_code}' không thuộc phạm vi của tác tử nào.", code="TOOL_OUT_OF_SCOPE"
    )


@dataclass(frozen=True)
class StepPlan:
    """Một bước đã kiểm chứng, đầu vào cho crew (không phụ thuộc models/)."""

    step_key: str
    tool_code: str
    config: dict[str, Any]


@dataclass(frozen=True)
class CrewTask:
    step_key: str
    agent: Agent
    tool: ToolBase
    config: dict[str, Any]

    def execute(self, ctx: ToolContext, inputs: dict[str, Any]) -> ToolResult:
        if not self.agent.allows(self.tool.code):  # bất biến — phòng khi bị dựng tay sai
            raise ValidationFailed(f"{self.agent.role} không được dùng '{self.tool.code}'.")
        return self.tool.run(ctx, dict(self.config), inputs)


@dataclass(frozen=True)
class SequentialCrew:
    tasks: tuple[CrewTask, ...]
    process: str = "sequential"

    def task(self, step_key: str) -> CrewTask:
        return next(t for t in self.tasks if t.step_key == step_key)


def build_crew(steps: Sequence[StepPlan]) -> SequentialCrew:
    """Dựng crew theo đúng thứ tự `steps` (đã sắp tô-pô ở tầng services)."""
    return SequentialCrew(
        tuple(
            CrewTask(s.step_key, agent_for(s.tool_code), get_tool(s.tool_code), s.config)
            for s in steps
        )
    )
