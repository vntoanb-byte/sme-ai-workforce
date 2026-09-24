"""
Điểm cuối danh mục công cụ

  GET /tools — danh sách công cụ đang bật kèm lược đồ vào/ra (dùng khi hiển thị
               sơ đồ quy trình và khi người dùng sửa tham số bước).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.employee import ToolOut
from app.tools.base import load_all_tools, tool_catalog

router = APIRouter()


@router.get("", response_model=list[ToolOut])
def list_tools(db: DbSession, _user: CurrentUser) -> list[dict[str, Any]]:
    registry = load_all_tools()
    return [
        {
            "code": code,
            "name": info["name"],
            "category": registry[code].category,
            "input_schema": info["input_schema"],
            "output_schema": info["output_schema"],
            "required_params": info["required_params"],
        }
        for code, info in sorted(tool_catalog(db).items())
        if info["is_enabled"]
    ]
