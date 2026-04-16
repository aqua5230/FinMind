from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from cachetools import TTLCache
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
import yfinance as yf

from stock_report.data import db
from stock_report.api.finmind import FinMindClient
from stock_report.data.tw_stocks import TW_STOCK_IDS


MIN_TURNOVER = 5_000_000
TWII_TICKER = '^TWII'
TWII_MA_PERIOD = 200

router = APIRouter()
logger = logging.getLogger(__name__)

_finmind = FinMindClient()
_stock_name_cache: TTLCache[str, dict[str, str]] = TTLCache(maxsize=1, ttl=3600)
_revenue_scan_cache: TTLCache[str, "RevenueScanResponse"] = TTLCache(maxsize=1, ttl=86400)
_revenue_scan_lock = asyncio.Lock()


class RevenueScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    stock_name: str
    revenue_ym: str
    revenue_yoy: float
    rank: int


class RevenueScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_at: str
    total_scanned: int
    market_filter: str
    results: list[RevenueScanResult]


def _get_stock_names() -> dict[str, str]:
    cached = _stock_name_cache.get("stock_names")
    if cached is not None:
        return cached

    try:
        rows = _finmind.fetch("TaiwanStockInfo", "", "", "")
    except Exception as exc:
        logger.warning("Failed to fetch stock names for scan: %s", exc)
        return {}

    names = {
        str(row["stock_id"]): str(row["stock_name"])
        for row in rows
        if str(row.get("stock_id", "")) in TW_STOCK_IDS and row.get("stock_name")
    }
    _stock_name_cache["stock_names"] = names
    return names


@router.get("/revenue-scan", response_model=RevenueScanResponse)
async def revenue_scan_stocks() -> RevenueScanResponse:
    cached = _revenue_scan_cache.get("revenue_scan")
    if cached is not None:
        return cached
    async with _revenue_scan_lock:
        cached = _revenue_scan_cache.get("revenue_scan")
        if cached is not None:
            return cached
        result = await asyncio.to_thread(_run_revenue_scan)
        _revenue_scan_cache["revenue_scan"] = result
        return result


def _run_revenue_scan() -> RevenueScanResponse:
    market_filter = _check_twii_filter()

    try:
        yoy_rows = db.query_revenue_yoy_bulk()
    except Exception as exc:
        logger.warning("Failed to query revenue YoY: %s", exc)
        yoy_rows = []

    if not yoy_rows:
        return RevenueScanResponse(
            scanned_at=datetime.now().replace(microsecond=0).isoformat(),
            total_scanned=0,
            market_filter=market_filter,
            results=[],
        )

    # 過濾：YoY 在合理範圍（0 ~ 10x = +1000%），排除異常極值
    positive = [r for r in yoy_rows if 0 < r["yoy"] <= 10.0]
    positive.sort(key=lambda x: x["yoy"], reverse=True)
    top20_count = max(1, len(positive) // 5)
    candidates = positive[:top20_count]

    candidate_ids = [r["stock_id"] for r in candidates]
    try:
        turnover_map = db.query_stock_avg_turnover(candidate_ids, days=20)
    except Exception as exc:
        logger.warning("Failed to query turnover: %s", exc)
        turnover_map = {}

    liquid = [r for r in candidates if turnover_map.get(r["stock_id"], 0) >= MIN_TURNOVER]

    # 股票名稱：優先從快取取，若空則同步呼叫一次
    names: dict[str, str] = _stock_name_cache.get("stock_names") or {}
    if not names:
        try:
            names = _get_stock_names()
        except Exception:
            names = {}

    results = []
    for rank, r in enumerate(liquid, start=1):
        results.append(RevenueScanResult(
            stock_id=r["stock_id"],
            stock_name=names.get(r["stock_id"], r["stock_id"]),
            revenue_ym=r["latest_ym"],
            revenue_yoy=round(r["yoy"], 4),
            rank=rank,
        ))

    return RevenueScanResponse(
        scanned_at=datetime.now().replace(microsecond=0).isoformat(),
        total_scanned=len(liquid),
        market_filter=market_filter,
        results=results,
    )


def _check_twii_filter() -> str:
    try:
        twii = yf.download(TWII_TICKER, period="300d", progress=False, auto_adjust=True)
        if twii.empty or len(twii) < TWII_MA_PERIOD:
            return "unknown"
        if getattr(twii.columns, "nlevels", 1) > 1:
            twii.columns = twii.columns.get_level_values(0)
        close = twii["Close"]
        ma200 = float(close.rolling(TWII_MA_PERIOD).mean().iloc[-1])
        current = float(close.iloc[-1])
        return "pass" if current >= ma200 else "block"
    except Exception as exc:
        logger.warning("TWII filter check failed: %s", exc)
        return "unknown"
