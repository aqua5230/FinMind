from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from stock_report.api.routes import PriceBar, PriceQueryParams, _map_price_row, verify_api_key
from stock_report.config import settings


def test_map_price_row_returns_price_bar_for_valid_row() -> None:
    row = {
        "date": "2024-01-02",
        "open": "10.5",
        "max": "11.0",
        "min": "10.0",
        "close": "10.8",
        "Trading_Volume": "123456",
    }

    result = _map_price_row(row)

    assert result == PriceBar(
        date="2024-01-02",
        open=10.5,
        high=11.0,
        low=10.0,
        close=10.8,
        volume=123456,
    )


def test_map_price_row_returns_none_when_max_key_missing() -> None:
    row = {
        "date": "2024-01-02",
        "open": "10.5",
        "min": "10.0",
        "close": "10.8",
        "Trading_Volume": "123456",
    }

    assert _map_price_row(row) is None


def test_map_price_row_returns_none_when_open_is_not_numeric() -> None:
    row = {
        "date": "2024-01-02",
        "open": "not-a-number",
        "max": "11.0",
        "min": "10.0",
        "close": "10.8",
        "Trading_Volume": "123456",
    }

    assert _map_price_row(row) is None


def test_map_price_row_returns_none_when_volume_is_none() -> None:
    row = {
        "date": "2024-01-02",
        "open": "10.5",
        "max": "11.0",
        "min": "10.0",
        "close": "10.8",
        "Trading_Volume": None,
    }

    assert _map_price_row(row) is None


def test_price_query_params_accepts_start_date_before_end_date() -> None:
    params = PriceQueryParams(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

    assert params.start_date == date(2024, 1, 1)
    assert params.end_date == date(2024, 1, 31)


def test_price_query_params_rejects_start_date_after_end_date() -> None:
    with pytest.raises(ValidationError):
        PriceQueryParams(start_date=date(2024, 2, 1), end_date=date(2024, 1, 31))


def test_verify_api_key_raises_503_when_api_key_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "api_key", None)

    with pytest.raises(HTTPException) as exc_info:
        verify_api_key("any")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "API key not configured"


def test_verify_api_key_passes_when_header_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_key", "expected-key")

    verify_api_key("expected-key")


def test_verify_api_key_raises_403_when_header_does_not_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "api_key", "expected-key")

    with pytest.raises(HTTPException) as exc_info:
        verify_api_key("wrong-key")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Forbidden"
