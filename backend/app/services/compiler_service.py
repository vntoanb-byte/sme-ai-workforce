"""
Dịch vụ biên dịch

Bọc domain.compiler, thêm phần ghi CSDL và ghi nhật ký:
  - compile_text(): biên dịch mô tả tiếng Việt → (spec, errors). Lỗi tầng mô
    hình ở bước phân loại (nằm ngoài vòng thử lại của compiler) được đổi thành
    COMPILE-1 thay vì lọt ra thành lỗi 500.
  - Mô tả GỐC của người dùng + kết quả luôn được lưu vào audit_logs
    (action='compiler.compile') để về sau phân tích và cải tiến prompt.
  - Mỗi lời gọi mô hình ghi một dòng llm_calls (qua RecordingLLM).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import structlog
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain import compiler
from app.domain.validators import SpecError
from app.models.audit import AuditLog
from app.ports.llm import LLMInvalidOutput, LLMProvider, LLMTimeout, LLMUnavailable
from app.schemas.workflow_spec import WorkflowSpec
from app.services.document_service import RecordingLLM
from app.tools.base import tool_catalog

logger = structlog.get_logger(__name__)


@dataclass
class CompileOutcome:
    spec: WorkflowSpec | None
    errors: list[SpecError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.spec is not None and not self.errors


def compile_text(db: Session, llm: LLMProvider, text: str, user_id: int | None) -> CompileOutcome:
    hints = {
        "thư mục quét trên máy chủ (scan_folder.path, trigger.watch_path)": settings.WATCH_PATH,
        "múi giờ (trigger.timezone)": settings.TIMEZONE,
    }
    try:
        spec, errors = compiler.compile(
            text, RecordingLLM(llm, db), tool_catalog(db), hints=hints
        )
    except (LLMTimeout, LLMUnavailable, LLMInvalidOutput) as exc:
        logger.warning("compiler.llm_error", error=str(exc))
        spec, errors = None, [
            SpecError(rule="COMPILE-1", step_key=None, message=compiler.COMPILE_1_MESSAGE)
        ]
    outcome = CompileOutcome(spec, list(errors))
    db.add(
        AuditLog(
            user_id=user_id,
            action="compiler.compile",
            entity_type="compile",
            detail_json=json.dumps(
                {
                    "text": text,
                    "prompt_version": compiler.PROMPT_VERSION,
                    "ok": outcome.ok,
                    "template_code": spec.template_code if spec else None,
                    "errors": [e.rule for e in errors],
                },
                ensure_ascii=False,
            ),
        )
    )
    db.flush()
    return outcome
