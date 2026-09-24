"""Kiểm thử utils/dates.py — phân tích ngày trên chứng từ Việt Nam."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.utils.dates import as_utc, parse_vn_date


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("05/08/2026", date(2026, 8, 5)),
        ("5-8-2026", date(2026, 8, 5)),
        ("05.08.2026", date(2026, 8, 5)),
        ("2026-08-05", date(2026, 8, 5)),
        ("Ngày 05 tháng 08 năm 2026", date(2026, 8, 5)),
        ("ngay 5 thang 8 nam 2026", date(2026, 8, 5)),
        (date(2026, 1, 2), date(2026, 1, 2)),
        (datetime(2026, 1, 2, 10, 30), date(2026, 1, 2)),
    ],
)
def test_parse_vn_date(text: object, expected: date) -> None:
    assert parse_vn_date(text) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize("text", [None, "", "31/02/2026", "hôm nay", "2026/13/01"])
def test_parse_vn_date_invalid(text: str | None) -> None:
    assert parse_vn_date(text) is None


def test_as_utc_treats_naive_as_utc() -> None:
    naive = datetime(2026, 1, 1, 8, 0)
    assert as_utc(naive) == datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
