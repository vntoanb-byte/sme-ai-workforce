"""
Lớp cơ sở và sổ đăng ký công cụ

Mọi công cụ kế thừa ToolBase và tự đăng ký vào TOOL_REGISTRY qua
@register_tool khi module được import (load_all_tools() import đủ các module).

Hợp đồng dữ liệu giữa các bước (blackboard):
  - Mỗi bước nhận `inputs` (dict — trạng thái tích luỹ của lần chạy) và
    `config` (tham số của bước trong WorkflowSpec), trả về ToolResult.outputs
    được gộp vào trạng thái cho các bước sau.
  - input_schema/output_schema là JSON Schema rút gọn; validators V-4 so
    `required` của bước sau với `properties` của bước trước.
  - Tệp đi qua các bước dưới dạng "file entry": {"filename", "path"} (tệp
    trên đĩa) hoặc {"filename", "artifact_id"} (tệp trong kho).

Mỗi công cụ phải bất biến khi lặp: chạy lại trên cùng đầu vào cho cùng kết
quả — worker có thể thử lại cả lần chạy sau lỗi tạm thời.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationFailed
from app.models.artifact import Artifact
from app.models.audit import AuditLog
from app.models.workflow import Tool
from app.ports.llm import LLMProvider
from app.ports.storage import ArtifactRef, FileStorage

LogFn = Callable[[str, str], None]


@dataclass
class ToolContext:
    db: Session
    storage: FileStorage
    llm: LLMProvider
    run_id: int | None = None
    employee_id: int | None = None
    step_key: str | None = None
    # Mốc thời gian lần chạy thành công gần nhất của cùng nhân viên AI
    # (fs.list_new_files chỉ lấy tệp mới hơn mốc này).
    since: datetime | None = None
    log: LogFn = field(default=lambda _level, _message: None)


@dataclass
class ToolResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    detail: str | None = None


class ToolBase:
    code: ClassVar[str]
    name: ClassVar[str]
    category: ClassVar[str]
    description: ClassVar[str] = ""
    input_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}
    output_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}
    required_params: ClassVar[tuple[str, ...]] = ()

    def run(self, ctx: ToolContext, config: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        raise NotImplementedError


TOOL_REGISTRY: dict[str, type[ToolBase]] = {}


def register_tool(cls: type[ToolBase]) -> type[ToolBase]:
    if cls.code in TOOL_REGISTRY and TOOL_REGISTRY[cls.code] is not cls:
        raise RuntimeError(f"Trùng mã công cụ: {cls.code}")
    TOOL_REGISTRY[cls.code] = cls
    return cls


def load_all_tools() -> dict[str, type[ToolBase]]:
    """Import mọi module công cụ để chúng tự đăng ký; trả về registry."""
    from app.tools import (  # noqa: F401
        doc_tools,
        fs_tools,
        qc_tools,
        report_tools,
        vision_tools,
        xlsx_tools,
    )

    return TOOL_REGISTRY


def get_tool(code: str) -> ToolBase:
    cls = load_all_tools().get(code)
    if cls is None:
        raise ValidationFailed(f"Công cụ '{code}' không tồn tại.", code="TOOL_NOT_FOUND")
    return cls()


def sync_tools_to_db(db: Session) -> None:
    """Đồng bộ registry → bảng tools: thêm mới/cập nhật lược đồ; mã không còn
    trong registry thì tắt (is_enabled=False), KHÔNG xoá (lịch sử còn tham chiếu).
    Công cụ admin đã tắt tay thì giữ nguyên trạng thái tắt."""
    registry = load_all_tools()
    existing = {t.code: t for t in db.scalars(select(Tool))}
    for code, cls in registry.items():
        row = existing.get(code)
        if row is None:
            row = Tool(code=code, is_enabled=True)
            db.add(row)
        row.name = cls.name
        row.category = cls.category
        row.input_schema_json = json.dumps(cls.input_schema, ensure_ascii=False)
        row.output_schema_json = json.dumps(cls.output_schema, ensure_ascii=False)
    for code, row in existing.items():
        if code not in registry:
            row.is_enabled = False
    db.flush()


def tool_catalog(db: Session) -> dict[str, dict[str, Any]]:
    """Ánh xạ tool_code -> thông tin công cụ cho domain/validators (duck-typed).

    Trạng thái bật/tắt lấy từ DB (quản trị viên có thể tắt), lược đồ và tham
    số bắt buộc lấy từ registry trong mã nguồn (nguồn sự thật).
    """
    registry = load_all_tools()
    enabled = {t.code: t.is_enabled for t in db.scalars(select(Tool))}
    return {
        code: {
            "is_enabled": enabled.get(code, True),
            "input_schema": cls.input_schema,
            "output_schema": cls.output_schema,
            "required_params": list(cls.required_params),
            "name": cls.name,
        }
        for code, cls in registry.items()
    }


# ─── Tiện ích dùng chung cho các công cụ ───


def allowed_roots() -> list[Path]:
    return [Path(p).resolve() for p in [settings.WATCH_PATH, *settings.FS_ALLOWED_ROOTS] if p]


def resolve_allowed_path(raw: str, *, base: str | None = None) -> Path:
    """Đường dẫn trong cấu hình quy trình → Path tuyệt đối, bắt buộc nằm dưới
    một thư mục được phép. Đường dẫn tương đối tính từ `base` (mặc định
    WATCH_PATH)."""
    if not raw or not str(raw).strip():
        raise ValidationFailed("Thiếu đường dẫn tệp/thư mục trong cấu hình bước.")
    path = Path(str(raw).strip())
    if not path.is_absolute():
        path = Path(base or settings.WATCH_PATH) / path
    resolved = path.resolve()
    for root in allowed_roots():
        if resolved == root or root in resolved.parents:
            return resolved
    raise ValidationFailed(
        f"Đường dẫn '{raw}' nằm ngoài các thư mục được phép truy cập.",
        code="PATH_NOT_ALLOWED",
    )


def read_entry(ctx: ToolContext, entry: dict[str, Any]) -> bytes:
    """Đọc nội dung một file entry (tệp trên đĩa hoặc artifact trong kho)."""
    if entry.get("artifact_id") is not None:
        artifact = ctx.db.get(Artifact, int(entry["artifact_id"]))
        if artifact is None:
            raise ValidationFailed(f"Không tìm thấy tệp #{entry['artifact_id']} trong kho.")
        with ctx.storage.open(artifact_ref(artifact)) as fh:
            return fh.read()
    return resolve_allowed_path(str(entry["path"])).read_bytes()


def artifact_ref(artifact: Artifact) -> ArtifactRef:
    return ArtifactRef(
        sha256=artifact.sha256,
        path=artifact.path,
        size_bytes=artifact.size_bytes,
        content_type=artifact.content_type,
    )


def save_output(ctx: ToolContext, data: bytes, filename: str) -> Artifact:
    """Lưu tệp kết quả vào kho + ghi audit 'run.output' để trang chi tiết lần
    chạy liệt kê được tệp đầu ra (artifacts không có cột tên tệp — tệp được khử
    trùng theo nội dung nên một artifact có thể mang nhiều tên)."""
    from app.services.document_service import ensure_artifact

    artifact = ensure_artifact(ctx.db, ctx.storage, data, filename)
    ctx.db.add(
        AuditLog(
            action="run.output",
            entity_type="artifact",
            entity_id=artifact.id,
            detail_json=json.dumps(
                {"run_id": ctx.run_id, "step_key": ctx.step_key, "filename": filename},
                ensure_ascii=False,
            ),
        )
    )
    ctx.db.flush()
    return artifact


def split_list(value: Any) -> list[str]:
    """"a, b ,c" hoặc ["a","b"] → ["a","b","c"] (bỏ phần tử rỗng)."""
    if value is None:
        return []
    items = value if isinstance(value, list | tuple) else str(value).split(",")
    return [str(x).strip() for x in items if str(x).strip()]
