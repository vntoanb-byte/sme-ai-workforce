"""
Công cụ hệ thống tệp

fs.list_new_files — duyệt thư mục theo dõi, lấy danh sách tệp mới:
  1. Chỉ lấy tệp có đuôi nằm trong `extensions`, mới hơn mốc lần chạy thành
     công trước (ctx.since) khi only_new=True.
  2. Bỏ qua tệp đang được ghi dở: kích thước phải ổn định qua 2 lần đọc cách
     nhau `stable_seconds`.
  3. Thư mục bắt buộc nằm dưới các thư mục được phép (tools/base.py).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.tools.base import (
    ToolBase,
    ToolContext,
    ToolResult,
    register_tool,
    resolve_allowed_path,
    split_list,
)
from app.utils.dates import as_utc

_FILES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"filename": {"type": "string"}, "path": {"type": "string"}},
    },
}


@register_tool
class ListNewFiles(ToolBase):
    code = "fs.list_new_files"
    name = "Lấy tệp mới trong thư mục"
    category = "fs"
    description = "Liệt kê tệp mới (theo phần mở rộng) trong một thư mục trên máy chủ."
    input_schema = {"type": "object", "properties": {}}
    output_schema = {"type": "object", "properties": {"files": _FILES_SCHEMA}}
    required_params = ("path",)

    def run(self, ctx: ToolContext, config: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        folder = resolve_allowed_path(str(config.get("path", "")))
        if not folder.is_dir():
            raise FileNotFoundError(f"Thư mục '{folder}' không tồn tại.")
        extensions = {
            "." + e.lower().lstrip(".")
            for e in split_list(config.get("extensions") or "jpg,jpeg,png,pdf")
        }
        only_new = bool(config.get("only_new", True))
        stable_seconds = float(config.get("stable_seconds", 1.0))
        since = as_utc(ctx.since) if (only_new and ctx.since) else None

        candidates = []
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in extensions:
                continue
            stat = path.stat()
            if since and datetime.fromtimestamp(stat.st_mtime, UTC) <= since:
                continue
            candidates.append((path, stat.st_size))

        if candidates and stable_seconds > 0:
            time.sleep(stable_seconds)
        files = []
        skipped = 0
        for path, size in candidates:
            if path.exists() and path.stat().st_size == size and size > 0:
                files.append({"filename": path.name, "path": str(path)})
            else:
                skipped += 1
                ctx.log("WARN", f"Bỏ qua {path.name}: tệp đang được ghi dở")

        ctx.log("INFO", f"Quét thư mục {folder} — tìm thấy {len(files)} tệp mới")
        detail = f"Tìm thấy {len(files)} tệp mới"
        if skipped:
            detail += f", bỏ qua {skipped} tệp đang ghi dở"
        return ToolResult(outputs={"files": files}, detail=detail)


def has_new_files(folder: str, extensions: str | None, since: datetime | None) -> bool:
    """Kiểm tra nhanh (không đợi tệp ổn định) cho bộ lập lịch file_watch."""
    try:
        root = resolve_allowed_path(folder)
    except Exception:  # noqa: BLE001 — cấu hình sai thì coi như không có tệp mới
        return False
    if not root.is_dir():
        return False
    wanted = {"." + e.lower().lstrip(".") for e in split_list(extensions or "jpg,jpeg,png,pdf")}
    cutoff = as_utc(since) if since else None
    for path in root.iterdir():
        if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in wanted:
            continue
        if cutoff is None or datetime.fromtimestamp(path.stat().st_mtime, UTC) > cutoff:
            return True
    return False
