from __future__ import annotations

import os
from datetime import date
from typing import Any, Iterable


def get_connection():
    import psycopg2

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_prices (
                    stock_id TEXT NOT NULL,
                    date DATE NOT NULL,
                    close DOUBLE PRECISION NOT NULL,
                    low DOUBLE PRECISION NOT NULL,
                    volume BIGINT NOT NULL,
                    PRIMARY KEY (stock_id, date)
                )
                """
            )


def has_price_data() -> bool:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT EXISTS (SELECT 1 FROM stock_prices LIMIT 1)")
            row = cursor.fetchone()
            return bool(row and row[0])


def get_latest_price_date() -> date | None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT MAX(date) FROM stock_prices")
            row = cursor.fetchone()
            if not row:
                return None
            return row[0]


def upsert_prices(stock_id: str, prices: Iterable[dict[str, Any]]) -> int:
    values = []
    for price in prices:
        price_date = price["date"]
        if isinstance(price_date, str):
            price_date = date.fromisoformat(price_date)
        values.append(
            (
                stock_id,
                price_date,
                float(price["close"]),
                float(price["low"]),
                int(price["volume"]),
            )
        )

    if not values:
        return 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            from psycopg2.extras import execute_values

            execute_values(
                cursor,
                """
                INSERT INTO stock_prices (stock_id, date, close, low, volume)
                VALUES %s
                ON CONFLICT (stock_id, date) DO UPDATE SET
                    close = EXCLUDED.close,
                    low = EXCLUDED.low,
                    volume = EXCLUDED.volume
                """,
                values,
            )
    return len(values)


def query_prices(stock_id: str, start_date: str | date, end_date: str | date) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT date, close, low, volume
                FROM stock_prices
                WHERE stock_id = %s
                  AND date BETWEEN %s AND %s
                ORDER BY date
                """,
                (stock_id, start_date, end_date),
            )
            rows = cursor.fetchall()

    return [
        {
            "date": row[0].isoformat(),
            "close": float(row[1]),
            "min": float(row[2]),
            "volume": int(row[3]),
            "Trading_Volume": int(row[3]),
        }
        for row in rows
    ]
