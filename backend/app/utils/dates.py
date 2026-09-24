"""
Xử lý ngày tháng

Phân tích ngày từ nhiều định dạng hay gặp trên chứng từ Việt Nam và chuẩn hoá
về `date` (ISO-8601). Toàn hệ thống lưu UTC, chỉ đổi múi giờ ở tầng hiển thị.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

_NUMERIC = re.compile(r"^\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\s*$")
_ISO = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})")
_WORDS = re.compile(
    r"ng[àa]y\s*(\d{1,2})\s*th[áa]ng\s*(\d{1,2})\s*n[ăa]m\s*(\d{4})", re.IGNORECASE
)


def parse_vn_date(value: str | date | datetime | None) -> date | None:
    """Hỗ trợ: dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy, yyyy-mm-dd và
    "Ngày 05 tháng 08 năm 2026". Không hợp lệ → None (không đoán)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    for pattern, order in ((_WORDS, "dmy"), (_NUMERIC, "dmy"), (_ISO, "ymd")):
        match = pattern.search(text) if pattern is _WORDS else pattern.match(text)
        if not match:
            continue
        a, b, c = (int(x) for x in match.groups())
        day, month, year = (a, b, c) if order == "dmy" else (c, b, a)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(dt: datetime) -> datetime:
    """datetime không có tzinfo (SQLite trả về như vậy) được coi là UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
