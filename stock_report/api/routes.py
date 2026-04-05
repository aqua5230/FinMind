from __future__ import annotations

import logging
from datetime import date

from cachetools import TTLCache
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, model_validator

from stock_report.api.finmind import FinMindClient
from stock_report.config import settings
from stock_report.exceptions import FinMindAPIError, FinMindBaseError, InvalidStockError
from stock_report.models import StockReport
from stock_report.services.report_service import ReportService


router = APIRouter(prefix="/api")
service = ReportService()
_finmind = FinMindClient()
logger = logging.getLogger(__name__)

_stocks_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=1, ttl=3600)
_price_cache: TTLCache[str, PriceResponse] = TTLCache(maxsize=200, ttl=600)


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    year: int = 2024
    start_year: int | None = None
    end_year: int | None = None


class PriceBar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    prices: list[PriceBar]


class PriceQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> PriceQueryParams:
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be greater than end_date")
        return self


def _map_price_row(row: dict) -> PriceBar | None:
    try:
        bar = PriceBar(
            date=str(row["date"]),
            open=float(row["open"]),
            high=float(row["max"]),
            low=float(row["min"]),
            close=float(row["close"]),
            volume=int(row["Trading_Volume"]),
        )
        if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
            return None
        return bar
    except (KeyError, TypeError, ValueError):
        logger.warning("Skipping malformed price row: %s", row)
        return None


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.api_key:
        return

    if x_api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/report", response_model=StockReport)
def create_report(
    payload: ReportRequest,
    _: None = Depends(verify_api_key),
) -> StockReport:
    return _generate_report(
        stock_id=payload.stock_id,
        year=payload.year,
        start_year=payload.start_year,
        end_year=payload.end_year,
    )


@router.get("/report/{stock_id}", response_model=StockReport)
def get_report(
    stock_id: str,
    year: int = Query(default=2024),
    start_year: int | None = Query(default=None),
    end_year: int | None = Query(default=None),
    _: None = Depends(verify_api_key),
) -> StockReport:
    return _generate_report(
        stock_id=stock_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )


@router.get("/price/{stock_id}", response_model=PriceResponse)
def get_price(
    stock_id: str,
    params: PriceQueryParams = Depends(),
) -> PriceResponse:
    start_date = params.start_date.isoformat()
    end_date = params.end_date.isoformat()
    cache_key = f"{stock_id}:{start_date}:{end_date}"
    cached = _price_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        raw = _finmind.fetch("TaiwanStockPrice", stock_id, start_date, end_date)
    except FinMindAPIError as exc:
        status_code = 429 if _is_quota_error(exc) else 502
        raise HTTPException(status_code=status_code, detail=exc.msg) from exc
    except FinMindBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    prices: list[PriceBar] = []
    for row in raw:
        price = _map_price_row(row)
        if price is not None:
            prices.append(price)

    prices = [p for p in prices if start_date <= p.date <= end_date]
    prices.sort(key=lambda item: item.date)
    response = PriceResponse(stock_id=stock_id, prices=prices)
    _price_cache[cache_key] = response
    return response


def _generate_report(
    stock_id: str,
    year: int,
    start_year: int | None = None,
    end_year: int | None = None,
) -> StockReport:
    if (start_year is None) != (end_year is None):
        raise HTTPException(
            status_code=422,
            detail="start_year and end_year must be provided together",
        )

    if start_year is not None and end_year is not None and start_year > end_year:
        raise HTTPException(
            status_code=422,
            detail="start_year cannot be greater than end_year",
        )

    try:
        if start_year is not None and end_year is not None:
            return service.generate_report(
                stock_id=stock_id,
                start_year=start_year,
                end_year=end_year,
            )
        return service.generate_report(stock_id=stock_id, year=year)
    except InvalidStockError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FinMindAPIError as exc:
        status_code = 429 if _is_quota_error(exc) else 502
        raise HTTPException(status_code=status_code, detail=exc.msg) from exc
    except FinMindBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _is_quota_error(exc: FinMindAPIError) -> bool:
    return exc.status_code == 402 or "quota" in exc.msg.lower()


@router.get("/stocks")
def get_stocks(_: None = Depends(verify_api_key)) -> list[dict]:
    cached = _stocks_cache.get("stocks")
    if cached is not None:
        return cached

    try:
        rows = _finmind.fetch("TaiwanStockInfo", "", "", "")
        stocks = [
            {"stock_id": r["stock_id"], "name": r["stock_name"], "market": r.get("type", "")}
            for r in rows
            if str(r.get("stock_id", "")).isdigit()
        ]
        _stocks_cache["stocks"] = stocks
        return stocks
    except FinMindBaseError as exc:
        logger.exception("Failed to fetch stocks list")
        raise HTTPException(status_code=502, detail="Failed to fetch stocks list") from exc
