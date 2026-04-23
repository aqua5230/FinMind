from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from cachetools import TTLCache
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from stock_report.api._limiter import limiter
from stock_report.data import db


router = APIRouter()
logger = logging.getLogger(__name__)

CORR_LOOKBACK_DAYS = 130
CORR_THRESHOLD = 0.75
MIN_DAILY_TURNOVER = 5_000_000
RECENT_DAYS = 5
TOP_N = 30

_pair_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=1, ttl=3600)
_pair_lock = asyncio.Lock()


class PairScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_a: str
    stock_b: str
    correlation: float
    deviation: float
    suggestion: str
    a_return_5d: float
    b_return_5d: float


class PairScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairs: list[PairScanResult]
    computed_at: str
    stock_count: int


def _stock_code(stock_id: str) -> str:
    return stock_id.split("_", 1)[0]


def _compute_pairs() -> list[dict[str, Any]]:
    """Core computation. Runs synchronously; caller should use run_in_executor."""
    rows = db.query_prices_bulk_recent(CORR_LOOKBACK_DAYS)
    if not rows:
        return []

    df = pd.DataFrame(rows, columns=["stock_id", "date", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["stock_id", "date", "close", "volume"])
    if df.empty:
        return []

    df["turnover"] = df["close"] * df["volume"]
    avg_turnover = df.groupby("stock_id")["turnover"].mean()
    liquid_ids = avg_turnover[avg_turnover >= MIN_DAILY_TURNOVER].index
    df = df[df["stock_id"].isin(liquid_ids)]
    if df.empty:
        return []

    pivot = df.pivot(index="date", columns="stock_id", values="close")
    pivot = pivot.dropna(thresh=60, axis=1)
    pivot = pivot.ffill()
    pivot = pivot.sort_index().tail(95)

    if pivot.shape[1] < 2:
        return []

    returns = pivot.pct_change().dropna(how="all")
    if returns.empty:
        return []

    corr_matrix = returns.corr()
    stocks = list(corr_matrix.columns)

    pairs: list[dict[str, Any]] = []
    for i in range(len(stocks)):
        for j in range(i + 1, len(stocks)):
            corr_val = float(corr_matrix.iloc[i, j])
            if np.isnan(corr_val) or corr_val < CORR_THRESHOLD:
                continue

            sa, sb = stocks[i], stocks[j]
            spread = (returns[sa] - returns[sb]).dropna()

            if len(spread) < RECENT_DAYS + 10:
                continue

            hist = spread.iloc[:-RECENT_DAYS]
            hist_mean = hist.mean()
            hist_std = hist.std()
            recent_mean = spread.iloc[-RECENT_DAYS:].mean()

            deviation = (recent_mean - hist_mean) / hist_std if hist_std > 0 else 0.0
            if not np.isfinite(deviation):
                continue

            a_ret = float(pivot[sa].pct_change(RECENT_DAYS).iloc[-1] * 100)
            b_ret = float(pivot[sb].pct_change(RECENT_DAYS).iloc[-1] * 100)
            if not np.isfinite(a_ret) or not np.isfinite(b_ret):
                continue

            stock_a = _stock_code(str(sa))
            stock_b = _stock_code(str(sb))
            suggestion = f"空{stock_a} 買{stock_b}" if deviation > 0 else f"空{stock_b} 買{stock_a}"

            pairs.append(
                {
                    "stock_a": stock_a,
                    "stock_b": stock_b,
                    "correlation": round(corr_val, 3),
                    "deviation": round(float(deviation), 2),
                    "suggestion": suggestion,
                    "a_return_5d": round(a_ret, 2),
                    "b_return_5d": round(b_ret, 2),
                }
            )

    pairs.sort(key=lambda x: abs(float(x["deviation"])), reverse=True)
    return pairs[:TOP_N]


@router.get("/api/pair-scan", response_model=PairScanResponse)
@limiter.limit("5/minute")
async def pair_scan(request: Request) -> PairScanResponse:
    async with _pair_lock:
        cached = _pair_cache.get("pairs")
        if cached is not None:
            return PairScanResponse(
                pairs=[PairScanResult(**p) for p in cached["pairs"]],
                computed_at=str(cached["computed_at"]),
                stock_count=int(cached["stock_count"]),
            )

        loop = asyncio.get_running_loop()
        pairs = await loop.run_in_executor(None, _compute_pairs)
        computed_at = datetime.now(timezone.utc).isoformat()
        stock_count = len({p["stock_a"] for p in pairs} | {p["stock_b"] for p in pairs})

        _pair_cache["pairs"] = {
            "pairs": pairs,
            "computed_at": computed_at,
            "stock_count": stock_count,
        }

        return PairScanResponse(
            pairs=[PairScanResult(**p) for p in pairs],
            computed_at=computed_at,
            stock_count=stock_count,
        )
