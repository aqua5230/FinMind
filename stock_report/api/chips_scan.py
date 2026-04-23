from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta
import time
from typing import Any

from cachetools import TTLCache
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
import requests

from stock_report.api._limiter import limiter
from stock_report.data.db import query_prices_bulk_recent

router = APIRouter()

LOOKBACK_CALENDAR_DAYS = 35
TWSE_T86_URL = "https://www.twse.com.tw/fund/T86"
TWSE_T86_SLEEP_SECONDS = 0.5
TWSE_T86_TIMEOUT_SECONDS = 10
TWSE_T86_MAX_CONSECUTIVE_EMPTY = 3

MIN_VOLUME_LOT = 300       # 張
MIN_CHANGE_PCT = 5.0       # %
MIN_VOLUME_RATIO = 2.0     # 量比

_chips_scan_cache: TTLCache[str, "ChipsScanResponse"] = TTLCache(maxsize=1, ttl=3600)
_chips_scan_lock = asyncio.Lock()


class ChipsScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    stock_name: str
    change_pct: float
    volume_lot: int
    volume_ratio: float
    net_1d: int
    net_10d: int
    net_20d: int
    ma20_deviation: float


class ChipsScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_at: str
    total_scanned: int
    results: list[ChipsScanResult]


def _as_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _fetch_t86(date_str: str) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            TWSE_T86_URL,
            params={
                "response": "json",
                "date": date_str,
                "selectType": "ALLBUT0999",
            },
            timeout=TWSE_T86_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        time.sleep(TWSE_T86_SLEEP_SECONDS)
        return []

    time.sleep(TWSE_T86_SLEEP_SECONDS)

    try:
        payload = response.json()
    except ValueError:
        return []

    rows = payload.get("data")
    if payload.get("stat") != "OK" or not rows:
        return []

    results: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) <= 10:
            continue
        stock_id = str(row[0]).strip()
        stock_name = str(row[1]).strip()
        if not stock_id:
            continue
        results.append(
            {
                "stock_id": stock_id,
                "stock_name": stock_name,
                "foreign_net": _as_float(row[4]),
                "trust_net": _as_float(row[10]),
            }
        )

    return results


def _fetch_all_t86() -> dict[str, list[dict[str, Any]]]:
    """Fetch T86 for last LOOKBACK_CALENDAR_DAYS and return {stock_id: rows} sorted newest first."""
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    all_rows: list[dict[str, Any]] = []
    consecutive_empty = 0
    current_date = start_date

    while current_date <= end_date:
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue

        date_str = current_date.strftime("%Y%m%d")
        daily_rows = _fetch_t86(date_str)

        if not daily_rows:
            consecutive_empty += 1
            if consecutive_empty >= TWSE_T86_MAX_CONSECUTIVE_EMPTY:
                break
            current_date += timedelta(days=1)
            continue

        consecutive_empty = 0
        for row in daily_rows:
            all_rows.append({**row, "date": date_str})

        current_date += timedelta(days=1)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        grouped[row["stock_id"]].append(row)

    for sid in grouped:
        grouped[sid].sort(key=lambda x: str(x["date"]), reverse=True)

    return dict(grouped)


def _compute_price_signals() -> dict[str, dict[str, Any]]:
    """Compute per-stock price signals from DB. Returns {stock_id: {...}}."""
    rows = query_prices_bulk_recent(days=35)

    grouped: dict[str, list[tuple[date, float, int]]] = defaultdict(list)
    for stock_id, dt, close, vol in rows:
        grouped[stock_id].append((dt, close, vol))

    result: dict[str, dict[str, Any]] = {}
    for stock_id, bars in grouped.items():
        bars.sort(key=lambda x: x[0])

        if len(bars) < 2:
            continue

        _, latest_close, latest_vol = bars[-1]
        _, prev_close, _ = bars[-2]

        if prev_close <= 0 or latest_close <= 0:
            continue

        change_pct = (latest_close - prev_close) / prev_close * 100
        vol_lot = latest_vol // 1000  # shares → 張

        # 量比: today vs 20-day avg (excluding today)
        vol_history = [v for _, _, v in bars[-21:-1]]
        if len(vol_history) < 5:
            continue
        avg_vol = sum(vol_history) / len(vol_history)
        vol_ratio = latest_vol / avg_vol if avg_vol > 0 else 0.0

        # 月線乖離率 (MA20): last 20 closes including today
        recent_closes = [c for _, c, _ in bars[-20:]]
        if len(recent_closes) < 10:
            continue
        ma20 = sum(recent_closes) / len(recent_closes)
        ma20_deviation = (latest_close - ma20) / ma20 * 100 if ma20 > 0 else 0.0

        result[stock_id] = {
            "change_pct": round(change_pct, 2),
            "volume_lot": vol_lot,
            "vol_ratio": round(vol_ratio, 2),
            "ma20_deviation": round(ma20_deviation, 2),
        }

    return result


def _compute_chips_scan() -> ChipsScanResponse:
    price_signals = _compute_price_signals()
    t86_data = _fetch_all_t86()

    results: list[ChipsScanResult] = []

    for stock_id, inst_rows in t86_data.items():
        price = price_signals.get(stock_id)
        if price is None:
            continue
        if price["change_pct"] < MIN_CHANGE_PCT:
            continue
        if price["volume_lot"] < MIN_VOLUME_LOT:
            continue
        if price["vol_ratio"] < MIN_VOLUME_RATIO:
            continue
        if not inst_rows:
            continue

        def _net(row: dict[str, Any]) -> float:
            return _as_float(row.get("foreign_net", 0)) + _as_float(row.get("trust_net", 0))

        net_1d = _net(inst_rows[0])
        net_10d = sum(_net(r) for r in inst_rows[:10])
        net_20d = sum(_net(r) for r in inst_rows[:20])

        if net_1d <= 0 or net_10d <= 0 or net_20d <= 0:
            continue

        stock_name = str(inst_rows[0].get("stock_name", stock_id)).strip() or stock_id

        results.append(
            ChipsScanResult(
                stock_id=stock_id,
                stock_name=stock_name,
                change_pct=price["change_pct"],
                volume_lot=price["volume_lot"],
                volume_ratio=price["vol_ratio"],
                net_1d=int(round(net_1d)),
                net_10d=int(round(net_10d)),
                net_20d=int(round(net_20d)),
                ma20_deviation=price["ma20_deviation"],
            )
        )

    # Sort by MA20 deviation ascending (closest to MA20 first)
    results.sort(key=lambda r: r.ma20_deviation)

    return ChipsScanResponse(
        scanned_at=datetime.now().replace(microsecond=0).isoformat(),
        total_scanned=len(results),
        results=results,
    )


@router.get("/api/chips-scan", response_model=ChipsScanResponse)
@limiter.limit("5/minute")
async def chips_scan(request: Request) -> ChipsScanResponse:
    cached = _chips_scan_cache.get("chips_scan")
    if cached is not None:
        return cached

    async with _chips_scan_lock:
        cached = _chips_scan_cache.get("chips_scan")
        if cached is not None:
            return cached

        response = await asyncio.to_thread(_compute_chips_scan)
        _chips_scan_cache["chips_scan"] = response
        return response
