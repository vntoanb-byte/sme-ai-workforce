"""
Chấm điểm bộ đánh giá

Tính các chỉ số của Chương 8 bằng cách so kết quả hệ thống với nhãn chuẩn.

  1. Chỉ số chính: độ chính xác theo trường = 1 − (số trường sai / tổng số trường)
  2. Chuẩn hoá TRƯỚC khi so: bỏ khoảng trắng thừa, ngày về ISO-8601, bỏ dấu phân
     cách nghìn, tên riêng không phân biệt hoa thường
  3. Trường tiền tệ: so bằng Decimal, sai lệch phải bằng 0 mới tính đúng
  4. Dòng hàng: độ chính xác (precision) và độ bao phủ (recall) trên TẬP dòng,
     không so theo thứ tự
  5. Tổng hợp theo từng nhóm chất lượng ảnh (clean/noisy...) để thấy mô hình yếu ở đâu

Không phụ thuộc gì ngoài thư viện chuẩn — dùng được độc lập với backend.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

# Trường đầu hoá đơn được chấm (đường dẫn dạng a.b) và kiểu so sánh.
HEADER_FIELDS: dict[str, str] = {
    "invoice_no": "code",
    "invoice_form": "code",
    "issue_date": "date",
    "seller.name": "name",
    "seller.tax_code": "code",
    "buyer.name": "name",
    "totals.subtotal": "money",
    "totals.vat_rate": "money",
    "totals.vat_amount": "money",
    "totals.total": "money",
}
LINE_FIELDS = ("description", "quantity", "unit_price", "amount")

_SPACES = re.compile(r"\s+")


def _get(data: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    return _SPACES.sub(" ", text).strip()


def norm_money(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    text = norm_text(value).replace(" ", "").replace("đ", "").replace("VND", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    elif "," in text:
        text = (
            text.replace(",", "")
            if re.fullmatch(r"\d{1,3}(,\d{3})+", text)
            else text.replace(",", ".")
        )
    try:
        return Decimal(text).normalize()
    except InvalidOperation:
        return None


def norm_date(value: Any) -> str:
    text = norm_text(value)
    m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$", text)
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        except ValueError:
            return text
    return text[:10]


def normalize(kind: str, value: Any) -> Any:
    if kind == "money":
        return norm_money(value)
    if kind == "date":
        return norm_date(value)
    if kind == "name":
        return norm_text(value).casefold()
    return norm_text(value).replace(" ", "").upper()


@dataclass
class DocScore:
    name: str
    quality: str
    fields_total: int
    fields_wrong: int
    wrong: list[str]
    line_precision: float
    line_recall: float

    @property
    def field_accuracy(self) -> float:
        return 1 - self.fields_wrong / self.fields_total if self.fields_total else 0.0


def _line_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        norm_text(item.get("description")).casefold(),
        norm_money(item.get("quantity")),
        norm_money(item.get("unit_price")),
        norm_money(item.get("amount")),
    )


def score_document(name: str, predicted: dict[str, Any] | None, truth: dict[str, Any]) -> DocScore:
    """Chấm một chứng từ. predicted=None (hệ thống không đọc được) → sai mọi trường."""
    predicted = predicted or {}
    wrong = [
        path
        for path, kind in HEADER_FIELDS.items()
        if normalize(kind, _get(truth, path)) != normalize(kind, _get(predicted, path))
    ]
    truth_lines = [_line_key(i) for i in truth.get("line_items") or []]
    pred_lines = [_line_key(i) for i in predicted.get("line_items") or []]
    remaining = list(truth_lines)
    matched = 0
    for key in pred_lines:  # so theo tập (multiset), không theo thứ tự
        if key in remaining:
            remaining.remove(key)
            matched += 1
    precision = matched / len(pred_lines) if pred_lines else (1.0 if not truth_lines else 0.0)
    recall = matched / len(truth_lines) if truth_lines else 1.0
    return DocScore(
        name=name,
        quality=str(truth.get("quality") or "unknown"),
        fields_total=len(HEADER_FIELDS),
        fields_wrong=len(wrong),
        wrong=wrong,
        line_precision=precision,
        line_recall=recall,
    )


@dataclass
class Summary:
    group: str
    documents: int = 0
    fields_total: int = 0
    fields_wrong: int = 0
    precision_sum: float = 0.0
    recall_sum: float = 0.0
    wrong_by_field: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def field_accuracy(self) -> float:
        return 1 - self.fields_wrong / self.fields_total if self.fields_total else 0.0

    def row(self) -> dict[str, Any]:
        n = self.documents or 1
        return {
            "group": self.group,
            "documents": self.documents,
            "field_accuracy": round(self.field_accuracy, 4),
            "line_precision": round(self.precision_sum / n, 4),
            "line_recall": round(self.recall_sum / n, 4),
            "worst_fields": ", ".join(
                f"{k}({v})" for k, v in sorted(self.wrong_by_field.items(), key=lambda x: -x[1])[:3]
            ),
        }


def summarize(scores: Iterable[DocScore]) -> list[Summary]:
    """Tổng hợp chung ('all') và theo từng nhóm chất lượng ảnh."""
    groups: dict[str, Summary] = {"all": Summary("all")}
    for s in scores:
        for key in ("all", s.quality):
            g = groups.setdefault(key, Summary(key))
            g.documents += 1
            g.fields_total += s.fields_total
            g.fields_wrong += s.fields_wrong
            g.precision_sum += s.line_precision
            g.recall_sum += s.line_recall
            for f in s.wrong:
                g.wrong_by_field[f] += 1
    return list(groups.values())
