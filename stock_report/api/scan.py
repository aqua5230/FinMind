from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Sequence

from cachetools import TTLCache
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from stock_report.api.finmind import FinMindClient
from stock_report.data.tw_stocks import TW_SCAN_STOCK_IDS


BOLL_PERIOD = 20
BOLL_MULTIPLIER = 2
RSI_PERIOD = 14
VOLUME_MA_PERIOD = 10
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
RECENT_TRADING_DAYS = 5
PRICE_LOOKBACK_DAYS = 120
MAX_CONCURRENT_FETCHES = 10

router = APIRouter()
logger = logging.getLogger(__name__)

_finmind = FinMindClient()
_scan_cache: TTLCache[str, "ScanResponse"] = TTLCache(maxsize=1, ttl=600)
_stock_name_cache: TTLCache[str, dict[str, str]] = TTLCache(maxsize=1, ttl=3600)
_scan_lock = asyncio.Lock()


@dataclass(frozen=True)
class PriceBar:
    date: date
    close: float
    low: float
    volume: int


class ScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    stock_name: str
    signal_date: str
    days_ago: int


class ScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_at: str
    total_scanned: int
    results: list[ScanResult]


def calculate_signals(prices: Sequence[PriceBar]) -> list[date]:
    bars = sorted(prices, key=lambda item: item.date)
    if len(bars) < MACD_SLOW + MACD_SIGNAL:
        return []

    boll = _calculate_boll(bars)
    rsi = _calculate_rsi(bars)
    macd = _calculate_macd(bars)
    volume_ma = _calculate_volume_ma(bars)
    recent_start = max(1, len(bars) - RECENT_TRADING_DAYS)
    signals: list[date] = []

    for index in range(recent_start, len(bars)):
        previous_lower = boll[index - 1]
        current_lower = boll[index]
        current_rsi = rsi[index]
        previous_histogram = macd[index - 1]
        current_histogram = macd[index]
        current_volume_ma = volume_ma[index]

        if (
            previous_lower is not None
            and current_lower is not None
            and current_rsi is not None
            and previous_histogram is not None
            and current_histogram is not None
            and current_volume_ma is not None
            and bars[index - 1].close < previous_lower
            and bars[index].close > current_lower
            and current_rsi < 35
            and current_histogram > previous_histogram
            and previous_histogram < 0
            and bars[index].volume > current_volume_ma * 1.2
        ):
            signals.append(bars[index].date)

    return signals


@router.get("/scan", response_model=ScanResponse)
async def scan_stocks() -> ScanResponse:
    cached = _scan_cache.get("scan")
    if cached is not None:
        return cached

    async with _scan_lock:
        cached = _scan_cache.get("scan")
        if cached is not None:
            return cached

        end_date = date.today()
        start_date = end_date - timedelta(days=PRICE_LOOKBACK_DAYS)
        stock_names = await asyncio.to_thread(_get_stock_names)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

        tasks = [
            _scan_one_stock(stock_id, stock_names.get(stock_id, stock_id), start_date, end_date, semaphore)
            for stock_id in TW_SCAN_STOCK_IDS
        ]
        scanned = await asyncio.gather(*tasks)
        results = [item for item in scanned if item is not None]
        results.sort(key=lambda item: (item.days_ago, item.stock_id))

        response = ScanResponse(
            scanned_at=datetime.now().replace(microsecond=0).isoformat(),
            total_scanned=len(TW_SCAN_STOCK_IDS),
            results=results,
        )
        _scan_cache["scan"] = response
        return response


async def _scan_one_stock(
    stock_id: str,
    stock_name: str,
    start_date: date,
    end_date: date,
    semaphore: asyncio.Semaphore,
) -> ScanResult | None:
    async with semaphore:
        try:
            rows = await asyncio.to_thread(
                _fetch_stock_prices,
                stock_id,
                start_date.isoformat(),
                end_date.isoformat(),
            )
            prices = _map_price_rows(rows)
            signal_dates = calculate_signals(prices)
        except Exception as exc:
            logger.warning("Skipping stock_id=%s during scan: %s", stock_id, exc)
            return None

    if not signal_dates:
        return None

    signal_date = max(signal_dates)
    return ScanResult(
        stock_id=stock_id,
        stock_name=stock_name,
        signal_date=signal_date.isoformat(),
        days_ago=(end_date - signal_date).days,
    )


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
        if str(row.get("stock_id", "")) in TW_SCAN_STOCK_IDS and row.get("stock_name")
    }
    _stock_name_cache["stock_names"] = names
    return names


def _fetch_stock_prices(stock_id: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    return FinMindClient().fetch("TaiwanStockPrice", stock_id, start_date, end_date)


def _map_price_rows(rows: Sequence[dict[str, Any]]) -> list[PriceBar]:
    prices: list[PriceBar] = []
    for row in rows:
        try:
            bar = PriceBar(
                date=date.fromisoformat(str(row["date"])),
                close=float(row["close"]),
                low=float(row["min"]),
                volume=int(row["Trading_Volume"]),
            )
        except (KeyError, TypeError, ValueError):
            continue

        if bar.close <= 0 or bar.low <= 0 or bar.volume <= 0:
            continue
        prices.append(bar)

    prices.sort(key=lambda item: item.date)
    return prices


def _calculate_boll(prices: Sequence[PriceBar]) -> list[float | None]:
    values: list[float | None] = []
    window_sum = 0.0

    for index, bar in enumerate(prices):
        window_sum += bar.close
        if index < BOLL_PERIOD - 1:
            values.append(None)
            continue

        start = index - BOLL_PERIOD + 1
        window = prices[start : index + 1]
        middle = window_sum / BOLL_PERIOD
        variance = sum((item.close - middle) ** 2 for item in window) / BOLL_PERIOD
        values.append(middle - BOLL_MULTIPLIER * math.sqrt(variance))
        window_sum -= prices[start].close

    return values


def _calculate_rsi(prices: Sequence[PriceBar]) -> list[float | None]:
    values: list[float | None] = [None] * len(prices)
    if len(prices) <= RSI_PERIOD:
        return values

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, RSI_PERIOD + 1):
        change = prices[index].close - prices[index - 1].close
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    average_gain = sum(gains) / RSI_PERIOD
    average_loss = sum(losses) / RSI_PERIOD
    values[RSI_PERIOD] = _rsi_from_averages(average_gain, average_loss)

    for index in range(RSI_PERIOD + 1, len(prices)):
        change = prices[index].close - prices[index - 1].close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        average_gain = ((average_gain * (RSI_PERIOD - 1)) + gain) / RSI_PERIOD
        average_loss = ((average_loss * (RSI_PERIOD - 1)) + loss) / RSI_PERIOD
        values[index] = _rsi_from_averages(average_gain, average_loss)

    return values


def _rsi_from_averages(average_gain: float, average_loss: float) -> float:
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)


def _calculate_macd(prices: Sequence[PriceBar]) -> list[float | None]:
    fast_ema = _calculate_ema([item.close for item in prices], MACD_FAST)
    slow_ema = _calculate_ema([item.close for item in prices], MACD_SLOW)
    dif: list[float | None] = [
        fast - slow if fast is not None and slow is not None else None
        for fast, slow in zip(fast_ema, slow_ema)
    ]
    dea = _calculate_ema_for_optional_values(dif, MACD_SIGNAL)
    return [
        dif_value - dea_value if dif_value is not None and dea_value is not None else None
        for dif_value, dea_value in zip(dif, dea)
    ]


def _calculate_ema(values: Sequence[float], period: int) -> list[float | None]:
    ema: list[float | None] = [None] * len(values)
    if len(values) < period:
        return ema

    current = sum(values[:period]) / period
    ema[period - 1] = current
    multiplier = 2 / (period + 1)
    for index in range(period, len(values)):
        current = (values[index] - current) * multiplier + current
        ema[index] = current

    return ema


def _calculate_ema_for_optional_values(values: Sequence[float | None], period: int) -> list[float | None]:
    ema: list[float | None] = [None] * len(values)
    ready_values: list[float] = []
    current: float | None = None
    multiplier = 2 / (period + 1)

    for index, value in enumerate(values):
        if value is None:
            continue

        if current is None:
            ready_values.append(value)
            if len(ready_values) == period:
                current = sum(ready_values) / period
                ema[index] = current
            continue

        current = (value - current) * multiplier + current
        ema[index] = current

    return ema


def _calculate_volume_ma(prices: Sequence[PriceBar]) -> list[float | None]:
    values: list[float | None] = []
    window_sum = 0

    for index, bar in enumerate(prices):
        window_sum += bar.volume
        if index < VOLUME_MA_PERIOD - 1:
            values.append(None)
            continue

        values.append(window_sum / VOLUME_MA_PERIOD)
        window_sum -= prices[index - VOLUME_MA_PERIOD + 1].volume

    return values
