"""
Dịch vụ cấu hình hệ thống (bảng settings, dạng khoá–giá trị JSON)

  - DEFAULTS: các khoá được seed khi khởi tạo (db/init_db.py) và có tác dụng thật:
      company_name            — tên doanh nghiệp hiển thị/in trên báo cáo
      manual_minutes_per_doc  — số phút một người cần để nhập tay 1 chứng từ,
                                dùng tính "giờ công tiết kiệm" ở bảng điều khiển
  - Khoá bắt đầu bằng "secret." được mã hoá (Fernet, CREDENTIAL_ENC_KEY) khi
    lưu và KHÔNG BAO GIỜ trả giá trị thật ra API (chỉ "••••••").
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import ValidationFailed
from app.models.audit import Setting

DEFAULTS: dict[str, Any] = {
    "company_name": "Doanh nghiệp của bạn",
    "manual_minutes_per_doc": 4,
}
SECRET_PREFIX = "secret."
_KEY = re.compile(r"^[a-z][a-z0-9_.]{1,99}$")
MASK = "••••••"


def get(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key, default)
    value = json.loads(row.value_json)
    if key.startswith(SECRET_PREFIX) and isinstance(value, str):
        return security.decrypt_secret(value)
    return value


def list_all(db: Session) -> list[dict[str, Any]]:
    rows = {r.key: r for r in db.scalars(select(Setting))}
    out = []
    for key in sorted(set(rows) | set(DEFAULTS)):
        row = rows.get(key)
        value = json.loads(row.value_json) if row else DEFAULTS[key]
        out.append(
            {
                "key": key,
                "value": MASK if key.startswith(SECRET_PREFIX) else value,
                "updated_at": row.updated_at if row else None,
            }
        )
    return out


def put_many(db: Session, values: dict[str, Any], user_id: int | None) -> None:
    for key, value in values.items():
        if not _KEY.match(key):
            raise ValidationFailed(f"Khoá cấu hình '{key}' không hợp lệ.")
        if key.startswith(SECRET_PREFIX):
            if value == MASK:
                continue  # giao diện gửi lại giá trị che — giữ nguyên
            value = security.encrypt_secret(str(value))
        row = db.get(Setting, key) or Setting(key=key)
        row.value_json = json.dumps(value, ensure_ascii=False)
        row.updated_by = user_id
        db.add(row)
    db.flush()


def seed_defaults(db: Session) -> None:
    for key, value in DEFAULTS.items():
        if db.get(Setting, key) is None:
            db.add(Setting(key=key, value_json=json.dumps(value, ensure_ascii=False)))
    db.flush()
