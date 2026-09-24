"""
Công cụ xử lý tài liệu

  - doc.render_pdf: kết xuất mọi trang PDF thành ảnh PNG (pypdfium2, độ phân
    giải PDF_RENDER_DPI); tệp ảnh giữ nguyên đi tiếp.
  - doc.preprocess_image: chuẩn hoá ảnh (utils.images.preprocess) trước khi
    đưa vào mô hình.
Kết quả trung gian được lưu vào kho (artifact) và chuyển tiếp dưới dạng file
entry {"filename", "artifact_id"} cho bước sau. Bảng artifacts không có cột
`kind` — tệp trung gian chỉ được tham chiếu qua trạng thái của lần chạy.
"""

from __future__ import annotations

import io
from pathlib import PurePath
from typing import Any

from PIL import Image

from app.core.config import settings
from app.services.document_service import ensure_artifact
from app.tools.base import ToolBase, ToolContext, ToolResult, read_entry, register_tool
from app.utils import images

_FILES = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "path": {"type": "string"},
            "artifact_id": {"type": "integer"},
        },
    },
}


def _store(ctx: ToolContext, data: bytes, filename: str) -> dict[str, Any]:
    artifact = ensure_artifact(ctx.db, ctx.storage, data, filename)
    return {"filename": filename, "artifact_id": artifact.id}


@register_tool
class RenderPdf(ToolBase):
    code = "doc.render_pdf"
    name = "Kết xuất PDF thành ảnh"
    category = "doc"
    description = "Chuyển từng trang PDF thành ảnh PNG; tệp ảnh giữ nguyên."
    input_schema = {"type": "object", "properties": {"files": _FILES}, "required": ["files"]}
    output_schema = {"type": "object", "properties": {"files": _FILES}}

    def run(self, ctx: ToolContext, config: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        import pypdfium2 as pdfium

        out: list[dict[str, Any]] = []
        pages = 0
        for entry in inputs.get("files") or []:
            filename = str(entry.get("filename") or "tep")
            if not filename.lower().endswith(".pdf"):
                out.append(entry)
                continue
            pdf = pdfium.PdfDocument(read_entry(ctx, entry))
            try:
                stem = PurePath(filename).stem
                for index in range(len(pdf)):
                    bitmap = pdf[index].render(scale=settings.PDF_RENDER_DPI / 72.0)
                    buf = io.BytesIO()
                    bitmap.to_pil().save(buf, format="PNG")
                    out.append(_store(ctx, buf.getvalue(), f"{stem}_p{index + 1}.png"))
                    pages += 1
            finally:
                pdf.close()
        return ToolResult(outputs={"files": out}, detail=f"Kết xuất {pages} trang PDF")


@register_tool
class PreprocessImage(ToolBase):
    code = "doc.preprocess_image"
    name = "Tiền xử lý ảnh"
    category = "doc"
    description = "Xoay đúng chiều, thu nhỏ theo giới hạn điểm ảnh, chuyển RGB."
    input_schema = {"type": "object", "properties": {"files": _FILES}, "required": ["files"]}
    output_schema = {"type": "object", "properties": {"files": _FILES}}

    def run(self, ctx: ToolContext, config: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        out: list[dict[str, Any]] = []
        for entry in inputs.get("files") or []:
            filename = str(entry.get("filename") or "tep")
            if filename.lower().endswith(".pdf"):
                out.append(entry)
                continue
            img = images.preprocess(Image.open(io.BytesIO(read_entry(ctx, entry))))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            out.append(_store(ctx, buf.getvalue(), f"{PurePath(filename).stem}.jpg"))
        return ToolResult(outputs={"files": out}, detail=f"Đã xử lý {len(out)} tệp")
