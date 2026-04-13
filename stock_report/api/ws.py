from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from typing import Any

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)

FUGLE_WS_URL = "wss://api.fugle.tw/marketdata/v1.0/stock/streaming"

ws_router = APIRouter()


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _iter_trade_payloads(message: dict[str, Any]) -> list[dict[str, Any]]:
    data = message.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []

    for key in ("trade", "trades"):
        nested = data.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict):
            return [nested]

    return [data]


def _parse_trade(message: str, stock_id: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        logger.debug("Skipping non-JSON Fugle message for stock_id=%s: %s", stock_id, message)
        return []

    if not isinstance(payload, dict):
        return []

    event = payload.get("event")
    data = payload.get("data")
    channel = payload.get("channel") or (data.get("channel") if isinstance(data, dict) else None)
    if event not in (None, "data", "trade", "trades") and channel != "trades":
        return []

    trades: list[dict[str, Any]] = []
    for item in _iter_trade_payloads(payload):
        price = _to_float(item.get("price"))
        if price is None:
            continue

        size = _to_int(item.get("size"))
        if size is None:
            size = _to_int(item.get("volume"))
        trade_time = item.get("time") or item.get("at") or item.get("timestamp")
        trades.append(
            {
                "stock_id": stock_id,
                "price": price,
                "size": size if size is not None else 0,
                "time": str(trade_time) if trade_time is not None else None,
            }
        )

    return trades


async def _forward_fugle_trades(fugle_ws: Any, websocket: WebSocket, stock_id: str) -> None:
    async for message in fugle_ws:
        if not isinstance(message, str):
            continue
        for trade in _parse_trade(message, stock_id):
            await websocket.send_json(trade)


async def _wait_for_client_disconnect(websocket: WebSocket) -> None:
    while True:
        await websocket.receive_text()


@ws_router.websocket("/ws/realtime/{stock_id}")
async def realtime_websocket(websocket: WebSocket, stock_id: str) -> None:
    await websocket.accept()

    api_key = os.getenv("FUGLE_API_KEY")
    if not api_key:
        await websocket.send_json({"error": "FUGLE_API_KEY is not configured"})
        await websocket.close(code=1011)
        return

    fugle_ws = None
    tasks: set[asyncio.Task[None]] = set()
    try:
        fugle_ws = await websockets.connect(FUGLE_WS_URL)
        await fugle_ws.send(json.dumps({"event": "auth", "data": {"apikey": api_key}}))
        await fugle_ws.send(
            json.dumps({"event": "subscribe", "data": {"channel": "trades", "symbol": stock_id}})
        )

        tasks = {
            asyncio.create_task(_forward_fugle_trades(fugle_ws, websocket, stock_id)),
            asyncio.create_task(_wait_for_client_disconnect(websocket)),
        }
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in done:
            with contextlib.suppress(WebSocketDisconnect, asyncio.CancelledError):
                task.result()

        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Realtime websocket failed for stock_id=%s: %s", stock_id, exc)
        with contextlib.suppress(Exception):
            await websocket.send_json({"error": "Realtime stream unavailable"})
            await websocket.close(code=1011)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if fugle_ws is not None:
            await fugle_ws.close()
