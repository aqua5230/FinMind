from __future__ import annotations

from stock_report.data.processors._helpers import _to_hundred_million, _to_quarter


def test_to_quarter_returns_q1_for_march_end() -> None:
    assert _to_quarter("2024-03-31") == "2024Q1"


def test_to_quarter_returns_q2_for_june_end() -> None:
    assert _to_quarter("2024-06-30") == "2024Q2"


def test_to_quarter_returns_q3_for_september_end() -> None:
    assert _to_quarter("2024-09-30") == "2024Q3"


def test_to_quarter_returns_q4_for_december_end() -> None:
    assert _to_quarter("2024-12-31") == "2024Q4"


def test_to_quarter_returns_none_for_invalid_format() -> None:
    assert _to_quarter("not-a-date") is None


def test_to_quarter_returns_none_for_non_quarter_end_month() -> None:
    assert _to_quarter("2024-05-31") is None


def test_to_hundred_million_converts_one_hundred_million() -> None:
    assert _to_hundred_million(100000000) == 1.0


def test_to_hundred_million_converts_two_hundred_fifty_million() -> None:
    assert _to_hundred_million(250000000) == 2.5


def test_to_hundred_million_converts_zero() -> None:
    assert _to_hundred_million(0) == 0.0
