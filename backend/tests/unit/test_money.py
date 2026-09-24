"""
Kiểm thử xử lý số tiền

Phân tích đúng các định dạng số tiền thường gặp trên hoá đơn Việt Nam.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.utils.money import format_money, parse_money


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.234.567", Decimal("1234567")),
        ("1.234.567,50", Decimal("1234567.50")),
        ("1,234,567.50", Decimal("1234567.50")),
        ("12.500", Decimal("12500")),
        ("12,5", Decimal("12.5")),
        ("0.75", Decimal("0.75")),
        ("3.300.000 đ", Decimal("3300000")),
        ("3.300.000 VNĐ", Decimal("3300000")),
        ("₫ 250.000", Decimal("250000")),
        ("-15.000", Decimal("-15000")),
        ("(15.000)", Decimal("-15000")),
        ("100", Decimal("100")),
        (100, Decimal("100")),
        (Decimal("9.99"), Decimal("9.99")),
    ],
)
def test_parse_money(text: object, expected: Decimal) -> None:
    result = parse_money(text)  # type: ignore[arg-type]
    assert isinstance(result, Decimal)
    assert result == expected


@pytest.mark.parametrize("text", [None, "", "abc", "1.2.3,4,5", "12a"])
def test_parse_money_invalid_returns_none(text: str | None) -> None:
    assert parse_money(text) is None


def test_parse_money_never_returns_float() -> None:
    assert not isinstance(parse_money("0,1"), float)
    assert parse_money("0,1") + parse_money("0,2") == Decimal("0.3")  # type: ignore[operator]


def test_format_money() -> None:
    assert format_money(Decimal("1234567")) == "1.234.567"
    assert format_money(Decimal("1234567.5")) == "1.234.568"
    assert format_money(Decimal("1234567.5"), decimals=2) == "1.234.567,50"
    assert format_money(Decimal("-15000")) == "-15.000"
    assert format_money(0) == "0"
