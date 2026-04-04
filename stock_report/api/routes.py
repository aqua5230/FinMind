from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from stock_report.api.finmind import FinMindClient
from stock_report.exceptions import FinMindAPIError, FinMindBaseError, InvalidStockError
from stock_report.models import StockReport
from stock_report.services.report_service import ReportService


router = APIRouter(prefix="/api")
service = ReportService()
_finmind = FinMindClient()

_stocks_cache: list[dict] | None = None
_stocks_cache_time: float = 0
_CACHE_TTL = 86400  # 24 小時


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


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/report", response_model=StockReport)
def create_report(payload: ReportRequest) -> StockReport:
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
    start_date: str = Query(...),
    end_date: str = Query(...),
) -> PriceResponse:
    try:
        raw = _finmind.fetch("TaiwanStockPrice", stock_id, start_date, end_date)
    except FinMindAPIError as exc:
        status_code = 429 if _is_quota_error(exc) else 502
        raise HTTPException(status_code=status_code, detail=exc.msg) from exc
    except FinMindBaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    prices: list[PriceBar] = []
    for row in raw:
        try:
            prices.append(
                PriceBar(
                    date=str(row["date"]),
                    open=float(row["open"]),
                    high=float(row["max"]),
                    low=float(row["min"]),
                    close=float(row["close"]),
                    volume=int(row["Trading_Volume"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    prices = [p for p in prices if start_date <= p.date <= end_date]
    prices.sort(key=lambda item: item.date)
    return PriceResponse(stock_id=stock_id, prices=prices)


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
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


def _is_quota_error(exc: FinMindAPIError) -> bool:
    return exc.status_code == 402 or "quota" in exc.msg.lower()


@router.get("/stocks")
def get_stocks() -> list[dict]:
    global _stocks_cache, _stocks_cache_time
    now = time.time()
    if _stocks_cache is not None and (now - _stocks_cache_time) < _CACHE_TTL:
        return _stocks_cache
    try:
        rows = _finmind.fetch("TaiwanStockInfo", "", "", "")
        stocks = [
            {"stock_id": r["stock_id"], "name": r["stock_name"], "market": r.get("type", "")}
            for r in rows
            if str(r.get("stock_id", "")).isdigit()
        ]
        _stocks_cache = stocks
        _stocks_cache_time = now
        return stocks
    except Exception:
        return _stocks_cache or []
