"""
Công cụ kiểm soát chất lượng

  - qc.validate_invoice: chạy 8 quy tắc (domain.qc_rules qua services.qc_service)
    trên extraction mới nhất của từng chứng từ, ghi qc_results, đặt trạng thái
    chứng từ ok | needs_review và TÁCH danh sách cho hai nhánh đạt / không đạt.
  - qc.escalate: nhánh không đạt — bảo đảm chứng từ nằm trong hàng chờ xác nhận
    (status=needs_review, ADR-003) và ghi nhật ký kiểm toán người được giao.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.models.artifact import Document
from app.models.audit import AuditLog
from app.models.extraction import Extraction, QCResult
from app.services import qc_service
from app.tools.base import ToolBase, ToolContext, ToolResult, register_tool

_IDS = {"type": "array", "items": {"type": "integer"}}


def latest_extraction(ctx: ToolContext, document_id: int) -> Extraction | None:
    return ctx.db.scalar(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc(), Extraction.id.desc())
        .limit(1)
    )


@register_tool
class ValidateInvoice(ToolBase):
    code = "qc.validate_invoice"
    name = "Kiểm tra số liệu hoá đơn"
    category = "qc"
    description = "Chạy 8 quy tắc QC-01..QC-08, tách hoá đơn đạt / cần xác nhận."
    input_schema = {
        "type": "object",
        "properties": {"document_ids": _IDS},
        "required": ["document_ids"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "document_ids": _IDS,
            "passed_document_ids": _IDS,
            "review_document_ids": _IDS,
        },
    }

    def run(self, ctx: ToolContext, config: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        passed: list[int] = []
        review: list[int] = []
        for document_id in inputs.get("document_ids") or []:
            document = ctx.db.get(Document, document_id)
            extraction = latest_extraction(ctx, document_id)
            if document is None or extraction is None:
                continue
            needs_review = qc_service.evaluate(ctx.db, extraction)
            ctx.db.flush()
            document.status = "needs_review" if needs_review else "ok"
            if needs_review:
                review.append(document_id)
                failed = ctx.db.scalars(
                    select(QCResult.rule_code).where(
                        QCResult.extraction_id == extraction.id, QCResult.passed.is_(False)
                    )
                ).all()
                ctx.log(
                    "WARN",
                    f"HĐ {extraction.invoice_no or document.filename} · KHÔNG ĐẠT: "
                    f"{', '.join(failed)}",
                )
            else:
                passed.append(document_id)
        ctx.db.flush()
        return ToolResult(
            outputs={
                "document_ids": passed + review,
                "passed_document_ids": passed,
                "review_document_ids": review,
            },
            detail=f"Đạt {len(passed)} · cần xác nhận {len(review)}",
        )


@register_tool
class Escalate(ToolBase):
    code = "qc.escalate"
    name = "Chuyển sang chờ xác nhận"
    category = "qc"
    description = "Đưa chứng từ không đạt kiểm tra vào hàng chờ người xác nhận."
    input_schema = {
        "type": "object",
        "properties": {"document_ids": _IDS},
        "required": ["document_ids"],
    }
    output_schema = {"type": "object", "properties": {"review_document_ids": _IDS}}

    def run(self, ctx: ToolContext, config: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        ids = list(inputs.get("document_ids") or [])
        assign_to = str(config.get("assign_to") or "").strip() or None
        for document_id in ids:
            document = ctx.db.get(Document, document_id)
            if document is None:
                continue
            document.status = "needs_review"
            ctx.db.add(
                AuditLog(
                    action="document.escalate",
                    entity_type="document",
                    entity_id=document_id,
                    detail_json=json.dumps(
                        {"run_id": ctx.run_id, "assign_to": assign_to}, ensure_ascii=False
                    ),
                )
            )
        ctx.db.flush()
        who = f" — giao cho {assign_to}" if assign_to else ""
        ctx.log("INFO", f"Chuyển {len(ids)} chứng từ sang hàng đợi CHỜ XÁC NHẬN{who}")
        return ToolResult(
            outputs={"review_document_ids": ids},
            detail=f"{len(ids)} chứng từ chờ xác nhận{who}",
        )
