"""
每月自動同步月營收：每月 12 日 10:00 台北時間觸發。

邏輯：
1. 計算上個月的 YM（例如 4 月 12 日 → 202503）
2. 從 DB 取出已有該月資料的股票（跳過已同步）
3. 對剩餘股票逐一呼叫 FinMind API，每次間隔 6 秒（10 req/min）
4. 斷點續跑：已有資料的股票自動跳過，重啟後從斷點繼續
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import requests

from stock_report.config import settings
from stock_report.data import db
from stock_report.data.tw_stocks import TW_STOCK_IDS


FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"
SLEEP_BETWEEN_REQUESTS = 6  # 10 req/min，FinMind 免費/基本方案上限
MAX_RETRIES = 3

logger = logging.getLogger(__name__)


def _target_ym(reference: date | None = None) -> str:
    """回傳應該同步的月份（上個月），格式 YYYYMM。"""
    d = reference or date.today()
    if d.month == 1:
        return f"{d.year - 1}12"
    return f"{d.year}{d.month - 1:02d}"


def _get_synced_stock_ids(target_ym: str) -> set[str]:
    """從 DB 取出已有 target_ym 資料的股票 ID 集合（斷點續跑用）。"""
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT stock_id FROM stock_revenue_monthly WHERE revenue_ym = %s",
                    (target_ym,),
                )
                return {row[0] for row in cur.fetchall()}
    except Exception as exc:
        logger.warning("Failed to query synced stock ids: %s", exc)
        return set()


def _fetch_revenue_one(stock_id: str, target_ym: str) -> list[dict[str, Any]]:
    """
    從 FinMind API 抓單支股票指定月份的月營收。
    target_ym = YYYYMM，轉成 start_date / end_date 傳給 API。
    """
    year = int(target_ym[:4])
    month = int(target_ym[4:])
    start_date = f"{year}-{month:02d}-01"
    # end_date 設同月底（API 會回該月的資料即可）
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day:02d}"

    token = settings.finmind_token
    if not token:
        raise RuntimeError("FINMIND_TOKEN not configured")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                FINMIND_API_URL,
                params={
                    "dataset": "TaiwanStockMonthRevenue",
                    "data_id": stock_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "token": token,
                },
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise
            logger.debug("Retry %d for %s: %s", attempt, stock_id, exc)
            time.sleep(2 ** attempt)

    return []


def sync_latest_revenue() -> dict[str, int]:
    """
    主入口：同步上個月月營收至 DB。
    回傳 {target_ym, total, skipped, synced, failed}。
    """
    target_ym = _target_ym()
    stock_ids = list(TW_STOCK_IDS)
    total = len(stock_ids)

    already_synced = _get_synced_stock_ids(target_ym)
    remaining = [sid for sid in stock_ids if sid not in already_synced]

    skipped = len(already_synced)
    synced = 0
    failed = 0

    logger.info(
        "Revenue sync started: target_ym=%s total=%s skipped=%s remaining=%s",
        target_ym, total, skipped, len(remaining),
    )

    for i, stock_id in enumerate(remaining):
        try:
            rows = _fetch_revenue_one(stock_id, target_ym)
            if rows:
                records = [
                    {
                        "stock_id": str(row["stock_id"]),
                        "revenue_ym": f"{int(row['revenue_year'])}{int(row['revenue_month']):02d}",
                        "revenue": int(row["revenue"]),
                    }
                    for row in rows
                ]
                db.upsert_revenue(records)
                synced += 1
            else:
                # FinMind 無資料（例如該月未公告），算作 skip
                skipped += 1
        except Exception as exc:
            failed += 1
            logger.warning("Revenue sync failed for stock_id=%s: %s", stock_id, exc)

        # 每 6 秒一次，控制在 10 req/min
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if (i + 1) % 100 == 0:
            logger.info(
                "Revenue sync progress: %d/%d synced=%d failed=%d",
                i + 1, len(remaining), synced, failed,
            )

    result = {
        "target_ym": target_ym,
        "total": total,
        "skipped": skipped,
        "synced": synced,
        "failed": failed,
    }
    logger.info("Revenue sync completed: %s", result)
    return result
