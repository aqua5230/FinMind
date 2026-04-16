from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from cachetools import TTLCache
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from stock_report.api.finmind import FinMindClient


router = APIRouter()

LOOKBACK_CALENDAR_DAYS = 35
RECENT_TRADING_DAYS = 20
MIN_FOREIGN_CONSECUTIVE_BUY = 5
MIN_TRUST_BUY_DAYS = 3
FOREIGN_NAME = "外資及陸資(不含外資自營商)"
TRUST_NAME = "投信"

_finmind = FinMindClient()
_institution_scan_cache: TTLCache[str, "InstitutionScanResponse"] = TTLCache(maxsize=1, ttl=3600)
_institution_scan_lock = asyncio.Lock()


class InstitutionScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    stock_name: str
    foreign_consecutive_buy: int
    trust_buy_days: int
    foreign_net_20d: int


class InstitutionScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_at: str
    total_scanned: int
    results: list[InstitutionScanResult]


def _as_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _net_buy_sell(row: dict[str, Any]) -> float:
    return _as_float(row.get("buy")) - _as_float(row.get("sell"))


def _scan_institution_rows(rows: list[dict[str, Any]]) -> list[InstitutionScanResult]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        stock_id = str(row.get("stock_id", "")).strip()
        row_date = str(row.get("date", "")).strip()
        if not stock_id or not row_date:
            continue
        grouped[stock_id].append(row)

    results: list[InstitutionScanResult] = []
    for stock_id, stock_rows in grouped.items():
        foreign_rows = sorted(
            (row for row in stock_rows if str(row.get("name", "")).strip() == FOREIGN_NAME),
            key=lambda item: str(item.get("date", "")),
            reverse=True,
        )
        trust_rows = sorted(
            (row for row in stock_rows if str(row.get("name", "")).strip() == TRUST_NAME),
            key=lambda item: str(item.get("date", "")),
            reverse=True,
        )
        recent_foreign_rows = foreign_rows[:RECENT_TRADING_DAYS]
        recent_trust_rows = trust_rows[:RECENT_TRADING_DAYS]
        if not recent_foreign_rows or not recent_trust_rows:
            continue

        foreign_consecutive_buy = 0
        for row in foreign_rows:
            if _net_buy_sell(row) <= 0:
                break
            foreign_consecutive_buy += 1

        trust_buy_days = sum(1 for row in recent_trust_rows if _net_buy_sell(row) > 0)
        foreign_net_20d = int(
            round(sum(_net_buy_sell(row) for row in recent_foreign_rows))
        )

        if (
            foreign_consecutive_buy < MIN_FOREIGN_CONSECUTIVE_BUY
            or trust_buy_days < MIN_TRUST_BUY_DAYS
        ):
            continue

        results.append(
            InstitutionScanResult(
                stock_id=stock_id,
                stock_name=stock_id,
                foreign_consecutive_buy=foreign_consecutive_buy,
                trust_buy_days=trust_buy_days,
                foreign_net_20d=foreign_net_20d,
            )
        )

    results.sort(
        key=lambda item: (
            -item.foreign_consecutive_buy,
            -item.trust_buy_days,
            item.stock_id,
        )
    )
    return results


def _compute_institution_scan() -> InstitutionScanResponse:
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    rows = _finmind.fetch(
        "TaiwanStockInstitutionalInvestorsBuySell",
        "",
        start_date.isoformat(),
        end_date.isoformat(),
    )
    results = _scan_institution_rows(rows)
    return InstitutionScanResponse(
        scanned_at=datetime.now().replace(microsecond=0).isoformat(),
        total_scanned=len(results),
        results=results,
    )


@router.get("/api/institution-scan", response_model=InstitutionScanResponse)
async def institution_scan() -> InstitutionScanResponse:
    cached = _institution_scan_cache.get("institution_scan")
    if cached is not None:
        return cached

    async with _institution_scan_lock:
        cached = _institution_scan_cache.get("institution_scan")
        if cached is not None:
            return cached

        response = await asyncio.to_thread(_compute_institution_scan)
        _institution_scan_cache["institution_scan"] = response
        return response
