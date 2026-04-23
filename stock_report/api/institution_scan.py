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

router = APIRouter()

LOOKBACK_CALENDAR_DAYS = 35
RECENT_TRADING_DAYS = 20
MIN_FOREIGN_CONSECUTIVE_BUY = 5
MIN_TRUST_BUY_DAYS = 3
TWSE_T86_URL = "https://www.twse.com.tw/fund/T86"
TWSE_T86_SLEEP_SECONDS = 0.5
TWSE_T86_TIMEOUT_SECONDS = 10
TWSE_T86_MAX_CONSECUTIVE_EMPTY = 3

_institution_scan_cache: TTLCache[str, "InstitutionScanResponse"] = TTLCache(
    maxsize=1,
    ttl=3600,
)
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
        sorted_rows = sorted(
            stock_rows,
            key=lambda item: str(item.get("date", "")),
            reverse=True,
        )
        recent_rows = sorted_rows[:RECENT_TRADING_DAYS]
        if not recent_rows:
            continue

        foreign_consecutive_buy = 0
        for row in sorted_rows:
            if _as_float(row.get("foreign_net")) <= 0:
                break
            foreign_consecutive_buy += 1

        trust_buy_days = sum(
            1 for row in recent_rows if _as_float(row.get("trust_net")) > 0
        )
        foreign_net_20d = int(
            round(sum(_as_float(row.get("foreign_net")) for row in recent_rows))
        )

        if (
            foreign_consecutive_buy < MIN_FOREIGN_CONSECUTIVE_BUY
            or trust_buy_days < MIN_TRUST_BUY_DAYS
        ):
            continue

        results.append(
            InstitutionScanResult(
                stock_id=stock_id,
                stock_name=str(sorted_rows[0].get("stock_name", stock_id)).strip()
                or stock_id,
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
    rows: list[dict[str, Any]] = []
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
                raise RuntimeError(
                    "[STOP] 原因: TWSE API 連續 3 次回傳非 OK 或空資料\n"
                    "建議: 檢查 TWSE T86 API 狀態、日期格式或稍後重試"
                )
            current_date += timedelta(days=1)
            continue

        consecutive_empty = 0
        for row in daily_rows:
            rows.append({**row, "date": date_str})

        current_date += timedelta(days=1)

    results = _scan_institution_rows(rows)
    return InstitutionScanResponse(
        scanned_at=datetime.now().replace(microsecond=0).isoformat(),
        total_scanned=len(results),
        results=results,
    )


@router.get("/api/institution-scan", response_model=InstitutionScanResponse)
@limiter.limit("5/minute")
async def institution_scan(request: Request) -> InstitutionScanResponse:
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
