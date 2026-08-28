"""
Tập quy tắc kiểm soát chất lượng

Tám quy tắc nghiệp vụ áp lên dữ liệu hoá đơn. Toàn bộ là mã Python tất định,
không dùng mô hình — nên nhanh, miễn phí và giải thích được.

`data` có thể là dict hoặc object (đọc bằng getattr) theo đúng cấu trúc
InvoiceExtraction ở schemas/invoice.py: invoice_no, invoice_form, issue_date,
currency, seller{name, tax_code, address}, buyer{name, tax_code}, line_items
[{line_no, description, unit, quantity, unit_price, amount}],
totals{subtotal, vat_rate, vat_amount, total}.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Optional

TOLERANCE = Decimal("1")  # 1 đồng — dung sai làm tròn khi so sánh tiền tệ

VALID_VAT_RATES = {Decimal("0"), Decimal("5"), Decimal("8"), Decimal("10")}

MAX_INVOICE_AGE_MONTHS = 24

# Trọng số kiểm tra MSST theo thuật toán modulus-11 của Tổng cục Thuế, áp cho
# 9 chữ số đầu; chữ số thứ 10 là chữ số kiểm tra.
TAX_CODE_WEIGHTS = (31, 29, 23, 19, 17, 13, 7, 5, 3)

REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ("invoice_no", "Số hoá đơn"),
    ("issue_date", "Ngày lập"),
    ("currency", "Đơn vị tiền tệ"),
    ("seller.name", "Tên đơn vị bán"),
    ("seller.tax_code", "Mã số thuế bên bán"),
)


@dataclass(frozen=True)
class QCResult:
    rule_code: str
    severity: str  # 'warning' | 'critical'
    passed: bool
    field: Optional[str]
    message: str


def _get(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        if cur is None:
            return None
        cur = cur.get(part) if isinstance(cur, dict) else getattr(cur, part, None)
    return cur


def _line_items(data: Any) -> list[Any]:
    items = _get(data, "line_items")
    return list(items) if isinstance(items, (list, tuple)) else []


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _format_money(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value == value.to_integral_value():
        int_part, frac_part = str(int(value)), ""
    else:
        int_part, _, frac_part = format(value, "f").partition(".")
    groups: list[str] = []
    while len(int_part) > 3:
        groups.insert(0, int_part[-3:])
        int_part = int_part[:-3]
    groups.insert(0, int_part)
    grouped = ".".join(groups)
    return f"{sign}{grouped}{',' + frac_part if frac_part else ''}"


def _subtract_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) - months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _tax_code_error(code: Optional[str]) -> Optional[str]:
    """Trả về lý do không hợp lệ, hoặc None nếu mã số thuế hợp lệ."""
    if _is_blank(code):
        return "còn trống"
    cleaned = code.replace("-", "").replace(" ", "")
    if not cleaned.isdigit():
        return "chứa ký tự không phải chữ số"
    if len(cleaned) not in (10, 13):
        return "phải gồm 10 hoặc 13 chữ số"
    digits = [int(c) for c in cleaned[:10]]
    weighted = sum(d * w for d, w in zip(digits[:9], TAX_CODE_WEIGHTS))
    check_digit = (10 - weighted % 11) % 11
    if check_digit == 10:
        check_digit = 0
    if check_digit != digits[9]:
        return f"chữ số kiểm tra không khớp (kỳ vọng {check_digit}, đọc được {digits[9]})"
    return None


def qc_01_line_items_match_subtotal(data: Any, context: dict[str, Any]) -> QCResult:
    rule_code = "QC-01"
    severity = "critical"
    line_items = _line_items(data)
    subtotal = _to_decimal(_get(data, "totals.subtotal"))
    if subtotal is None:
        return QCResult(rule_code, severity, False, "totals.subtotal", "Không đọc được tiền trước thuế.")
    line_sum = Decimal("0")
    for item in line_items:
        line_sum += _to_decimal(_get(item, "amount")) or Decimal("0")
    diff = abs(line_sum - subtotal)
    if diff <= TOLERANCE:
        return QCResult(rule_code, severity, True, None, "Tổng các dòng hàng khớp tiền trước thuế.")
    message = (
        f"Tổng {len(line_items)} dòng hàng là {_format_money(line_sum)}, nhưng tiền trước thuế ghi "
        f"{_format_money(subtotal)}. Chênh lệch {_format_money(diff)} đ."
    )
    return QCResult(rule_code, severity, False, "totals.subtotal", message)


def qc_02_subtotal_plus_vat_equals_total(data: Any, context: dict[str, Any]) -> QCResult:
    rule_code = "QC-02"
    severity = "critical"
    subtotal = _to_decimal(_get(data, "totals.subtotal"))
    vat_amount = _to_decimal(_get(data, "totals.vat_amount"))
    total = _to_decimal(_get(data, "totals.total"))
    if subtotal is None or vat_amount is None or total is None:
        return QCResult(rule_code, severity, False, "totals.total", "Không đọc được đủ tiền trước thuế, tiền thuế và tổng thanh toán.")
    expected = subtotal + vat_amount
    diff = abs(expected - total)
    if diff <= TOLERANCE:
        return QCResult(rule_code, severity, True, None, "Tiền trước thuế cộng thuế khớp tổng thanh toán.")
    message = (
        f"{_format_money(subtotal)} + {_format_money(vat_amount)} = {_format_money(expected)}, nhưng đọc được "
        f"{_format_money(total)}. Chênh lệch {_format_money(diff)} đ."
    )
    return QCResult(rule_code, severity, False, "totals.total", message)


def qc_03_vat_rate_valid(data: Any, context: dict[str, Any]) -> QCResult:
    rule_code = "QC-03"
    severity = "critical"
    vat_rate = _to_decimal(_get(data, "totals.vat_rate"))
    if vat_rate is None:
        return QCResult(rule_code, severity, False, "totals.vat_rate", "Không đọc được thuế suất.")
    if vat_rate in VALID_VAT_RATES:
        return QCResult(rule_code, severity, True, None, f"Thuế suất {vat_rate}% hợp lệ.")
    return QCResult(
        rule_code, severity, False, "totals.vat_rate",
        f"Thuế suất {vat_rate}% không hợp lệ — chỉ chấp nhận 0%, 5%, 8% hoặc 10%.",
    )


def qc_04_seller_tax_code_valid(data: Any, context: dict[str, Any]) -> QCResult:
    rule_code = "QC-04"
    severity = "critical"
    tax_code = _get(data, "seller.tax_code")
    error = _tax_code_error(tax_code)
    if error is None:
        return QCResult(rule_code, severity, True, None, "Mã số thuế hợp lệ.")
    return QCResult(rule_code, severity, False, "seller.tax_code", f"Mã số thuế bên bán không hợp lệ: {error}.")


def qc_05_issue_date_reasonable(data: Any, context: dict[str, Any]) -> QCResult:
    rule_code = "QC-05"
    severity = "warning"
    issue_date = _to_date(_get(data, "issue_date"))
    if issue_date is None:
        return QCResult(rule_code, severity, False, "issue_date", "Không đọc được ngày lập hoá đơn.")
    today = date.today()
    if issue_date > today:
        return QCResult(
            rule_code, severity, False, "issue_date",
            f"Ngày lập {issue_date.isoformat()} nằm trong tương lai (hôm nay là {today.isoformat()}).",
        )
    cutoff = _subtract_months(today, MAX_INVOICE_AGE_MONTHS)
    if issue_date < cutoff:
        return QCResult(
            rule_code, severity, False, "issue_date",
            f"Ngày lập {issue_date.isoformat()} đã quá {MAX_INVOICE_AGE_MONTHS} tháng (giới hạn từ {cutoff.isoformat()}).",
        )
    return QCResult(rule_code, severity, True, None, "Ngày lập nằm trong khoảng hợp lý.")


def qc_06_invoice_no_not_duplicate(data: Any, context: dict[str, Any]) -> QCResult:
    rule_code = "QC-06"
    severity = "critical"
    invoice_no = _get(data, "invoice_no")
    if _is_blank(invoice_no):
        return QCResult(rule_code, severity, False, "invoice_no", "Không đọc được số hoá đơn.")
    existing: frozenset[str] = context.get("existing_invoice_numbers", frozenset())
    if invoice_no in existing:
        return QCResult(rule_code, severity, False, "invoice_no", f"Số hoá đơn '{invoice_no}' đã tồn tại trong hệ thống.")
    return QCResult(rule_code, severity, True, None, "Số hoá đơn chưa trùng với bản ghi nào khác.")


def qc_07_required_fields_present(data: Any, context: dict[str, Any]) -> QCResult:
    rule_code = "QC-07"
    severity = "critical"
    missing: list[tuple[str, str]] = [
        (path, label) for path, label in REQUIRED_FIELDS if _is_blank(_get(data, path))
    ]
    if not _line_items(data):
        missing.append(("line_items", "Chi tiết hàng hoá"))
    if not missing:
        return QCResult(rule_code, severity, True, None, "Đầy đủ các trường bắt buộc.")
    labels = ", ".join(label for _, label in missing)
    return QCResult(rule_code, severity, False, missing[0][0], f"Còn thiếu: {labels}.")


def qc_08_line_amount_matches_quantity_times_price(data: Any, context: dict[str, Any]) -> QCResult:
    rule_code = "QC-08"
    severity = "critical"
    line_items = _line_items(data)
    if not line_items:
        return QCResult(rule_code, severity, False, "line_items", "Không có dòng hàng nào để kiểm tra.")
    mismatches: list[str] = []
    first_bad_field: Optional[str] = None
    for idx, item in enumerate(line_items):
        quantity = _to_decimal(_get(item, "quantity"))
        unit_price = _to_decimal(_get(item, "unit_price"))
        amount = _to_decimal(_get(item, "amount"))
        line_no = _get(item, "line_no") or idx + 1
        if quantity is None or unit_price is None or amount is None:
            mismatches.append(f"dòng {line_no} thiếu dữ liệu")
            first_bad_field = first_bad_field or f"line_items.{idx}.amount"
            continue
        expected = quantity * unit_price
        if abs(expected - amount) > TOLERANCE:
            mismatches.append(
                f"dòng {line_no}: {quantity} × {_format_money(unit_price)} = {_format_money(expected)}, "
                f"nhưng thành tiền ghi {_format_money(amount)}"
            )
            first_bad_field = first_bad_field or f"line_items.{idx}.amount"
    if not mismatches:
        word = "cả" if len(line_items) > 1 else ""
        return QCResult(rule_code, severity, True, None, f"Đơn giá × số lượng khớp thành tiền ở {word} {len(line_items)} dòng.".replace("  ", " "))
    return QCResult(rule_code, severity, False, first_bad_field, "; ".join(mismatches) + ".")


RULES: list[Callable[[Any, dict[str, Any]], QCResult]] = [
    qc_01_line_items_match_subtotal,
    qc_02_subtotal_plus_vat_equals_total,
    qc_03_vat_rate_valid,
    qc_04_seller_tax_code_valid,
    qc_05_issue_date_reasonable,
    qc_06_invoice_no_not_duplicate,
    qc_07_required_fields_present,
    qc_08_line_amount_matches_quantity_times_price,
]


def run_qc(
    data: Any, existing_invoice_numbers: Optional[Iterable[str]] = None
) -> tuple[list[QCResult], bool]:
    context: dict[str, Any] = {"existing_invoice_numbers": frozenset(existing_invoice_numbers or ())}
    results = [rule(data, context) for rule in RULES]
    needs_review = any(r.severity == "critical" and not r.passed for r in results)
    return results, needs_review
