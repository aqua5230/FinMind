from __future__ import annotations

import logging
from datetime import date

import requests
from cachetools import TTLCache
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, model_validator

from stock_report.api._limiter import limiter
from stock_report.api.finmind import FinMindClient
from stock_report.api.scan import router as scan_router
from stock_report.config import settings
from stock_report.data.db import get_all_signals, get_latest_price_date, get_signal_stats, upsert_revenue
from stock_report.data.tw_stocks import get_tw_stocks
from stock_report.exceptions import FinMindAPIError, FinMindBaseError, InvalidStockError
from stock_report.models import StockReport
from stock_report.services.report_service import ReportService


router = APIRouter(prefix="/api")
service = ReportService()
_finmind = FinMindClient()
logger = logging.getLogger(__name__)

_stocks_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=1, ttl=3600)
_price_cache: TTLCache[str, PriceResponse] = TTLCache(maxsize=200, ttl=3600)
_realtime_cache: TTLCache[str, dict] = TTLCache(maxsize=200, ttl=30)
_market_cache: TTLCache[str, str] = TTLCache(maxsize=200, ttl=86400)


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    year: int = date.today().year
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


class DbStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_price_data: bool
    latest_price_date: str | None


class SignalRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    stock_name: str
    signal_date: str
    entry_price: float | None
    t10_date: str | None
    t10_price: float | None
    t10_return_pct: float | None
    status: str
    created_at: str


class SignalStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    resolved: int
    pending: int
    wins: int
    win_rate_pct: float


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
def health(request: Request) -> dict[str, str]:
    return {"status": "ok"}


@router.get("/db-status", response_model=DbStatusResponse)
def get_db_status(request: Request) -> DbStatusResponse:
    try:
        latest_price_date = get_latest_price_date()
    except Exception as exc:
        logger.warning("Failed to query DB status: %s", exc)
        raise HTTPException(status_code=503, detail="Database status unavailable") from exc

    return DbStatusResponse(
        has_price_data=latest_price_date is not None,
        latest_price_date=latest_price_date.isoformat() if latest_price_date is not None else None,
    )


@router.get("/signals", response_model=list[SignalRecordResponse])
@limiter.limit("20/minute")
def list_signals(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[SignalRecordResponse]:
    try:
        return [SignalRecordResponse(**row) for row in get_all_signals(limit)]
    except Exception as exc:
        logger.warning("Failed to query signal records: %s", exc)
        raise HTTPException(status_code=503, detail="Signal records unavailable") from exc


@router.get("/signals/stats", response_model=SignalStatsResponse)
@limiter.limit("20/minute")
def signal_stats(request: Request) -> SignalStatsResponse:
    try:
        return SignalStatsResponse(**get_signal_stats())
    except Exception as exc:
        logger.warning("Failed to query signal stats: %s", exc)
        raise HTTPException(status_code=503, detail="Signal stats unavailable") from exc


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if settings.debug:
        return
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="API key not configured")
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Forbidden")


router.include_router(scan_router, dependencies=[Depends(verify_api_key)])


@router.post("/report", response_model=StockReport)
@limiter.limit("5/minute")
def create_report(
    request: Request,
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
@limiter.limit("5/minute")
def get_report(
    request: Request,
    stock_id: str,
    year: int = Query(default=date.today().year),
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
@limiter.limit("30/minute")
def get_price(
    request: Request,
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

    prices.sort(key=lambda item: item.date)
    response = PriceResponse(stock_id=stock_id, prices=prices)
    _price_cache[cache_key] = response
    return response


@router.get("/realtime/{stock_id}")
@limiter.limit("60/minute")
def get_realtime_price(request: Request, stock_id: str) -> dict:
    cached = _realtime_cache.get(stock_id)
    if cached is not None:
        return cached

    cached_market = _market_cache.get(stock_id)
    markets = (cached_market,) if cached_market is not None else ("tse", "otc")
    result = None
    for market in markets:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={market}_{stock_id}.tw&json=1&delay=0"
        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
            arr = data.get("msgArray", [])
            if not arr:
                continue
            item = arr[0]
            z = item.get("z", "-")
            o = item.get("o", "-")
            h = item.get("h", "-")
            l = item.get("l", "-")
            v = item.get("v", "-")
            d = item.get("d", "-")
            y = item.get("y", "-")
            if "-" in (z, o, h, l, v, d):
                continue
            date_str = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            bar = {
                "stock_id": stock_id,
                "date": date_str,
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(z),
                "volume": int(float(v) * 1000),
                "prev_close": float(y) if y != "-" else None,
            }
            _realtime_cache[stock_id] = bar
            _market_cache[stock_id] = market
            result = bar
            break
        except Exception:
            continue

    if result is None:
        raise HTTPException(status_code=404, detail="Realtime price not available")
    return result


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


class RevenueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_id: str
    revenue_ym: str
    revenue: int


class LoadRevenueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[RevenueRecord]


@router.post("/admin/load-revenue")
def admin_load_revenue(
    request: Request,
    body: LoadRevenueRequest,
    _: None = Depends(verify_api_key),
) -> dict:
    records = [r.model_dump() for r in body.records]
    try:
        n = upsert_revenue(records)
    except Exception as exc:
        logger.warning("Failed to upsert revenue: %s", exc)
        raise HTTPException(status_code=503, detail=f"DB error: {exc}") from exc
    return {"upserted": n}


@router.get("/stocks")
@limiter.limit("10/minute")
def get_stocks(request: Request, _: None = Depends(verify_api_key)) -> list[dict]:
    cached = _stocks_cache.get("stocks")
    if cached is not None:
        return cached

    try:
        stocks = [
            {"stock_id": s["id"], "name": s["name"], "market": s["market"]}
            for s in get_tw_stocks()
        ]
        _stocks_cache["stocks"] = stocks
        return stocks
    except Exception as exc:
        logger.exception("Failed to fetch stocks list")
        raise HTTPException(status_code=502, detail="Failed to fetch stocks list") from exc
