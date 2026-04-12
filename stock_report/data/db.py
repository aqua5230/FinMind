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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_records (
                    stock_id TEXT NOT NULL,
                    stock_name TEXT NOT NULL DEFAULT '',
                    signal_date DATE NOT NULL,
                    entry_price DOUBLE PRECISION,
                    t10_date DATE,
                    t10_price DOUBLE PRECISION,
                    t10_return_pct DOUBLE PRECISION,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (stock_id, signal_date)
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


def insert_signal(
    stock_id: str,
    stock_name: str,
    signal_date: str | date,
    entry_price: float | None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO signal_records (stock_id, stock_name, signal_date, entry_price)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (stock_id, signal_date) DO NOTHING
                """,
                (stock_id, stock_name, signal_date, entry_price),
            )


def _map_signal_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "stock_id": row[0],
        "stock_name": row[1],
        "signal_date": row[2].isoformat() if row[2] is not None else None,
        "entry_price": float(row[3]) if row[3] is not None else None,
        "t10_date": row[4].isoformat() if row[4] is not None else None,
        "t10_price": float(row[5]) if row[5] is not None else None,
        "t10_return_pct": float(row[6]) if row[6] is not None else None,
        "status": row[7],
        "created_at": row[8].isoformat() if row[8] is not None else None,
    }


def get_pending_signals() -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT stock_id, stock_name, signal_date, entry_price, t10_date,
                       t10_price, t10_return_pct, status, created_at
                FROM signal_records
                WHERE status = 'pending'
                ORDER BY signal_date
                """
            )
            rows = cursor.fetchall()

    return [_map_signal_row(row) for row in rows]


def resolve_signal(
    stock_id: str,
    signal_date: str | date,
    t10_date: str | date | None,
    t10_price: float | None,
    t10_return_pct: float | None,
    status: str = "resolved",
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE signal_records
                SET t10_date = %s,
                    t10_price = %s,
                    t10_return_pct = %s,
                    status = %s
                WHERE stock_id = %s
                  AND signal_date = %s
                """,
                (t10_date, t10_price, t10_return_pct, status, stock_id, signal_date),
            )


def get_all_signals(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT stock_id, stock_name, signal_date, entry_price, t10_date,
                       t10_price, t10_return_pct, status, created_at
                FROM signal_records
                ORDER BY signal_date DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()

    return [_map_signal_row(row) for row in rows]


def get_signal_stats() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'resolved') AS resolved,
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                    COUNT(*) FILTER (
                        WHERE status = 'resolved' AND t10_return_pct > 0
                    ) AS wins
                FROM signal_records
                """
            )
            row = cursor.fetchone()

    total = int(row[0]) if row else 0
    resolved = int(row[1]) if row else 0
    pending = int(row[2]) if row else 0
    wins = int(row[3]) if row else 0
    win_rate_pct = round((wins / resolved) * 100, 2) if resolved else 0.0
    return {
        "total": total,
        "resolved": resolved,
        "pending": pending,
        "wins": wins,
        "win_rate_pct": win_rate_pct,
    }
