from __future__ import annotations

import asyncio
from datetime import date, datetime
import logging
import time
from typing import Any
from zoneinfo import ZoneInfo

from cachetools import TTLCache
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
import requests
import urllib3

from stock_report.api._limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
REQUEST_TIMEOUT_SECONDS = 15
CB_SCAN_CACHE_KEY = "cb_scan"

# TPEX OpenAPI - 上櫃可轉換公司債發行資料（含賣回條款）
TPEX_ISSBD5_URL = "https://www.tpex.org.tw/openapi/v1/bond_ISSBD5_data"

# 篩選條件
DAYS_TO_PUT_MAX = 180       # 距賣回日 < 6 個月
MIN_ANNUALIZED_RETURN = 0.01  # 年化報酬 > 1%（面值基準）
ASSUMED_CB_PRICE = 100.0    # 假設以面值 100 買入（保守基準；實際成交價需自查）

_cb_scan_cache: TTLCache[str, "CbScanResponse"] = TTLCache(maxsize=1, ttl=1800)
_cb_scan_lock = asyncio.Lock()


class CbScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bond_id: str
    stock_id: str
    stock_name: str
    put_date: str
    put_price: float
    cb_price: float       # 假設面值 100（保守基準）
    days_to_put: int
    annualized_return: float
    guarantor: str


class CbScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_at: str
    total_scanned: int
    results: list[CbScanResult]
    error: str | None = None


def _as_float(value: Any) -> float:
    try:
        raw = str(value).replace(",", "").strip()
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _parse_date_yyyymmdd(value: Any) -> date | None:
    raw = str(value).strip()
    if len(raw) != 8 or not raw.isdigit():
        return None
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return None


def _fetch_issbd5() -> list[dict[str, Any]]:
    response = requests.get(
        TPEX_ISSBD5_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
        verify=False,
    )
    time.sleep(0.5)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"TPEX ISSBD5 未回傳 list，got {type(data).__name__}")
    return data


def _compute_cb_scan() -> CbScanResponse:
    scanned_at = datetime.now(TAIPEI_TZ).replace(microsecond=0).isoformat()
    today = datetime.now(TAIPEI_TZ).date()

    try:
        raw_data = _fetch_issbd5()
    except Exception as exc:
        logger.warning("TPEX ISSBD5 fetch failed: %s", exc)
        return CbScanResponse(
            scanned_at=scanned_at,
            total_scanned=0,
            results=[],
            error=f"資料來源暫時不可用（{exc}）",
        )

    results: list[CbScanResult] = []

    for row in raw_data:
        # 只處理有 4 位數股票代號的 CB（上市/上櫃公司發行）
        stock_id = str(row.get("IssuerCode", "")).strip()
        if not (len(stock_id) == 4 and stock_id.isdigit()):
            continue

        bond_id = str(row.get("BondCode", "")).strip()
        if not bond_id:
            continue

        # 賣回條款
        put_date = _parse_date_yyyymmdd(row.get("PutOptionDate"))
        put_price = _as_float(row.get("PutOptionPrice"))
        if put_date is None or put_price <= 0:
            continue

        # 距賣回日
        days_to_put = (put_date - today).days
        if not (0 < days_to_put < DAYS_TO_PUT_MAX):
            continue

        # 銀行擔保：Guaranteed == "1"
        guaranteed = str(row.get("Guaranteed", "")).strip()
        if guaranteed != "1":
            continue

        guarantor = str(row.get("GuaranteeDescription", "")).strip() or "有擔保（詳見公開說明書）"

        # 年化報酬（假設以面值 100 買入）
        cb_price = ASSUMED_CB_PRICE
        if cb_price >= put_price:
            continue
        annualized_return = (put_price - cb_price) / cb_price / (days_to_put / 365)
        if annualized_return <= MIN_ANNUALIZED_RETURN:
            continue

        stock_name = str(row.get("IssuerName", stock_id)).strip() or stock_id

        results.append(
            CbScanResult(
                bond_id=bond_id,
                stock_id=stock_id,
                stock_name=stock_name,
                put_date=put_date.isoformat(),
                put_price=round(put_price, 4),
                cb_price=round(cb_price, 2),
                days_to_put=days_to_put,
                annualized_return=round(annualized_return, 6),
                guarantor=guarantor,
            )
        )

    results.sort(key=lambda r: r.annualized_return, reverse=True)

    note = "現價以面值100估算（實際成交價請自行查詢）" if results else None

    return CbScanResponse(
        scanned_at=scanned_at,
        total_scanned=len(raw_data),
        results=results,
        error=note,
    )


@router.get("/api/cb-scan", response_model=CbScanResponse)
@limiter.limit("5/minute")
async def cb_scan(request: Request) -> CbScanResponse:
    cached = _cb_scan_cache.get(CB_SCAN_CACHE_KEY)
    if cached is not None:
        return cached

    async with _cb_scan_lock:
        cached = _cb_scan_cache.get(CB_SCAN_CACHE_KEY)
        if cached is not None:
            return cached

        response = await asyncio.to_thread(_compute_cb_scan)
        _cb_scan_cache[CB_SCAN_CACHE_KEY] = response
        return response
