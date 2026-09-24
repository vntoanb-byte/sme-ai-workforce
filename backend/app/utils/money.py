"""
Xử lý số tiền

Phân tích và định dạng số tiền theo quy ước Việt Nam: dấu chấm phân cách
nghìn, dấu phẩy thập phân ("1.234.567,50"). TUYỆT ĐỐI không dùng float.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_CURRENCY_MARKS = re.compile(r"(?i)(vnđ|vnd|đồng|đ|₫|\s)")


def parse_money(value: str | int | Decimal | None) -> Decimal | None:
    """Chuỗi số tiền → Decimal; không đọc được thì trả None.

    Quy tắc tách phần nghìn/thập phân:
      - Có cả "." và ",": dấu xuất hiện SAU CÙNG là dấu thập phân
        ("1.234.567,50" → 1234567.50; "1,234,567.50" → 1234567.50).
      - Chỉ có một loại dấu: nếu nó lặp lại, hoặc đứng trước ĐÚNG 3 chữ số ở
        cuối, thì là phân cách nghìn ("1.234.567", "12.500"); ngược lại là dấu
        thập phân ("12,5", "0.75").
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    text = _CURRENCY_MARKS.sub("", str(value))
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    text = text.strip("-()+")
    if not text or not re.fullmatch(r"[0-9.,]+", text):
        return None

    if "." in text and "," in text:
        decimal_mark = "." if text.rfind(".") > text.rfind(",") else ","
        thousands_mark = "," if decimal_mark == "." else "."
        text = text.replace(thousands_mark, "").replace(decimal_mark, ".")
    elif "." in text or "," in text:
        mark = "." if "." in text else ","
        head, _, tail = text.rpartition(mark)
        if text.count(mark) > 1 or (len(tail) == 3 and head):
            text = text.replace(mark, "")
        else:
            text = text.replace(mark, ".")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    return -amount if negative else amount


def format_money(amount: Decimal | int, *, decimals: int = 0) -> str:
    """Decimal → chuỗi kiểu Việt Nam: 1234567.5 → "1.234.568" (decimals=0)."""
    quant = Decimal(1).scaleb(-decimals)
    value = Decimal(amount).quantize(quant)
    sign = "-" if value < 0 else ""
    int_part, _, frac_part = format(abs(value), "f").partition(".")
    groups: list[str] = []
    while len(int_part) > 3:
        groups.insert(0, int_part[-3:])
        int_part = int_part[:-3]
    groups.insert(0, int_part)
    text = ".".join(groups)
    return f"{sign}{text},{frac_part}" if frac_part else f"{sign}{text}"
