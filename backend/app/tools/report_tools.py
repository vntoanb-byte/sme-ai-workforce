"""
Công cụ báo cáo

report.build_xlsx (openpyxl) và report.build_pdf (ReportLab, phông tiếng Việt
— xem services/report_service._pdf_font). Tổng hợp theo kỳ `period` và tiêu
chí `group_by`; tệp kết quả lưu vào kho và gắn vào lần chạy.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.services import report_service
from app.tools.base import ToolBase, ToolContext, ToolResult, register_tool, save_output


class _ReportTool(ToolBase):
    fmt: ClassVar[str]
    category = "report"
    input_schema = {"type": "object", "properties": {}}
    output_schema = {
        "type": "object",
        "properties": {"artifact_ids": {"type": "array", "items": {"type": "integer"}}},
    }

    def run(self, ctx: ToolContext, config: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        date_from, date_to = report_service.resolve_period(str(config.get("period") or "today"))
        group_by = str(config.get("group_by") or "seller")
        data = report_service.aggregate(ctx.db, date_from, date_to, group_by)
        build = report_service.build_xlsx if self.fmt == "xlsx" else report_service.build_pdf
        content = build(data)
        filename = f"BaoCao_{date_from:%Y%m%d}_{date_to:%Y%m%d}.{self.fmt}"
        artifact = save_output(ctx, content, filename)
        ctx.log("INFO", f"Lập báo cáo {filename}: {len(data.rows)} nhóm")
        return ToolResult(
            outputs={"artifact_ids": [*inputs.get("artifact_ids", []), artifact.id]},
            detail=f"{filename} · {sum(r.doc_count for r in data.rows)} chứng từ",
        )


@register_tool
class BuildXlsx(_ReportTool):
    code = "report.build_xlsx"
    name = "Lập báo cáo Excel"
    description = "Tổng hợp hoá đơn đã xác nhận theo kỳ, xuất Excel."
    fmt = "xlsx"


@register_tool
class BuildPdf(_ReportTool):
    code = "report.build_pdf"
    name = "Lập báo cáo PDF"
    description = "Tổng hợp hoá đơn đã xác nhận theo kỳ, xuất PDF."
    fmt = "pdf"
