from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from cachetools import TTLCache
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
import requests
import urllib3

from stock_report.data.db import query_prices


router = APIRouter()

TWSE_DISPOSITION_URL = "https://www.twse.com.tw/zh/api/getDisposition"
TWSE_DISPOSITION_FALLBACK_URL = "https://www.twse.com.tw/announcement/punish"
TWSE_DISPOSITION_TIMEOUT_SECONDS = 10
DISPOSITION_CACHE_KEY = "disposition_scan"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_disposition_scan_cache: TTLCache[str, "DispositionScanResponse"] = TTLCache(
    maxsize=1,
    ttl=3600,
)
_disposition_scan_lock = asyncio.Lock()


class DispositionScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    stock_name: str
    disposition_start: str
    disposition_end: str
    days_to_release: int
    price_change_during: float


class DispositionScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_at: str
    total_scanned: int
    results: list[DispositionScanResult]


def _fetch_disposition_payload() -> dict[str, Any]:
    for url in (TWSE_DISPOSITION_URL, TWSE_DISPOSITION_FALLBACK_URL):
        try:
            response = requests.get(
                url,
                params={"response": "json"},
                timeout=TWSE_DISPOSITION_TIMEOUT_SECONDS,
                verify=False,
            )
            payload = response.json()
        except (requests.RequestException, ValueError):
            continue

        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload

    raise RuntimeError(
        "[STOP] 原因: TWSE 處置股 API 未回傳可解析 JSON\n"
        "建議: 檢查 TWSE getDisposition / announcement/punish API 狀態與欄位"
    )


def _parse_roc_date(value: Any) -> date | None:
    raw = str(value).strip()
    parts = raw.split("/")
    if len(parts) != 3:
        return None

    try:
        year = int(parts[0]) + 1911
        month = int(parts[1])
        day = int(parts[2])
        return date(year, month, day)
    except ValueError:
        return None


def _parse_disposition_period(value: Any) -> tuple[date, date] | None:
    raw = str(value).strip()
    separator = "～" if "～" in raw else "~"
    parts = [part.strip() for part in raw.split(separator)]
    if len(parts) != 2:
        return None

    start = _parse_roc_date(parts[0])
    end = _parse_roc_date(parts[1])
    if start is None or end is None:
        return None
    return start, end


def _compute_price_change(stock_id: str, start: date, end: date) -> float:
    try:
        rows = query_prices(stock_id, start, min(end, date.today()))
    except Exception:
        return 0.0

    if len(rows) < 2:
        return 0.0

    first_close = float(rows[0].get("close") or 0)
    last_close = float(rows[-1].get("close") or 0)
    if first_close <= 0:
        return 0.0

    return round(((last_close - first_close) / first_close) * 100, 2)


def _scan_disposition_rows(payload: dict[str, Any]) -> tuple[int, list[DispositionScanResult]]:
    fields = payload.get("fields")
    rows = payload.get("data")
    if not isinstance(fields, list) or not isinstance(rows, list):
        raise RuntimeError(
            "[STOP] 原因: TWSE API response 結構與預期差異過大，無法解析欄位\n"
            "建議: 先確認 getDisposition / announcement/punish 最新欄位"
        )

    field_index = {str(field): index for index, field in enumerate(fields)}
    required_fields = ("證券代號", "證券名稱", "處置起迄時間")
    if any(field not in field_index for field in required_fields):
        raise RuntimeError(
            "[STOP] 原因: TWSE API response 缺少必要處置欄位\n"
            "建議: 先確認 getDisposition / announcement/punish 最新欄位"
        )

    parsed_count = 0
    results: list[DispositionScanResult] = []
    today = date.today()

    for row in rows:
        if not isinstance(row, list):
            continue

        try:
            stock_id = str(row[field_index["證券代號"]]).strip()
            stock_name = str(row[field_index["證券名稱"]]).strip()
            period = _parse_disposition_period(row[field_index["處置起迄時間"]])
        except IndexError:
            continue

        if not stock_id.isdigit() or len(stock_id) != 4 or period is None:
            continue

        parsed_count += 1
        start, end = period
        days_to_release = (end - today).days
        price_change_during = _compute_price_change(stock_id, start, end)

        if 0 <= days_to_release <= 5 and price_change_during > -8.0:
            results.append(
                DispositionScanResult(
                    stock_id=stock_id,
                    stock_name=stock_name or stock_id,
                    disposition_start=start.isoformat(),
                    disposition_end=end.isoformat(),
                    days_to_release=days_to_release,
                    price_change_during=price_change_during,
                )
            )

    results.sort(key=lambda item: (item.days_to_release, item.stock_id))
    return parsed_count, results


def _compute_disposition_scan() -> DispositionScanResponse:
    payload = _fetch_disposition_payload()
    total_scanned, results = _scan_disposition_rows(payload)
    return DispositionScanResponse(
        scanned_at=datetime.now().replace(microsecond=0).isoformat(),
        total_scanned=total_scanned,
        results=results,
    )


@router.get("/api/disposition-scan", response_model=DispositionScanResponse)
async def disposition_scan() -> DispositionScanResponse:
    cached = _disposition_scan_cache.get(DISPOSITION_CACHE_KEY)
    if cached is not None:
        return cached

    async with _disposition_scan_lock:
        cached = _disposition_scan_cache.get(DISPOSITION_CACHE_KEY)
        if cached is not None:
            return cached

        response = await asyncio.to_thread(_compute_disposition_scan)
        _disposition_scan_cache[DISPOSITION_CACHE_KEY] = response
        return response
