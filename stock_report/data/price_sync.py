from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any

import yfinance as yf

from stock_report.data.db import upsert_prices
from stock_report.data.tw_stocks import TW_STOCK_IDS


LOOKBACK_DAYS = 150
MAX_CONCURRENT = 10
MAX_RETRIES = 3
BACKOFF_SECONDS = 2

logger = logging.getLogger(__name__)


def sync_all_prices() -> dict[str, int]:
    end_date = date.today() + timedelta(days=1)
    start_date = date.today() - timedelta(days=LOOKBACK_DAYS)
    stock_ids = list(TW_STOCK_IDS)
    synced = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = {
            executor.submit(_sync_one_stock, stock_id, start_date, end_date): stock_id
            for stock_id in stock_ids
        }
        for future in as_completed(futures):
            stock_id = futures[future]
            try:
                synced += future.result()
            except Exception as exc:
                failed += 1
                logger.warning("Failed to sync prices for stock_id=%s: %s", stock_id, exc)

    logger.info(
        "Finished stock price sync: stocks=%s rows=%s failed=%s",
        len(stock_ids),
        synced,
        failed,
    )
    return {"stocks": len(stock_ids), "rows": synced, "failed": failed}


def _sync_one_stock(stock_id: str, start_date: date, end_date: date) -> int:
    rows = _fetch_yfinance_rows(stock_id, start_date.isoformat(), end_date.isoformat())
    return upsert_prices(stock_id, rows)


def _fetch_yfinance_rows(stock_id: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    for suffix in (".TW", ".TWO"):
        ticker = f"{stock_id}{suffix}"
        rows = _download_with_retry(ticker, start_date, end_date)
        if rows:
            return rows
    return []


def _download_with_retry(ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            rows = _download_once(ticker, start_date, end_date)
            if rows:
                return rows
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Attempt %s/%s failed for %s: %s",
                attempt,
                MAX_RETRIES,
                ticker,
                exc,
            )

        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF_SECONDS * attempt)

    if last_error is not None:
        logger.warning("Giving up yfinance download for %s: %s", ticker, last_error)
    return []


def _download_once(ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    history = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        progress=False,
        auto_adjust=False,
    )
    if history.empty:
        return []

    if getattr(history.columns, "nlevels", 1) > 1:
        history.columns = history.columns.get_level_values(0)

    rows: list[dict[str, Any]] = []
    for index, row in history.iterrows():
        close = float(row["Close"])
        low = float(row["Low"])
        volume = int(row["Volume"])
        if math.isnan(close) or math.isnan(low) or volume <= 0:
            continue
        rows.append(
            {
                "date": index.date(),
                "close": close,
                "low": low,
                "volume": volume,
            }
        )
    return rows
