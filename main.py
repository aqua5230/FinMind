import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from stock_report.api._limiter import limiter
from stock_report.api import cb_scan, chips_scan, disposition, institution_scan, pair_scan
from stock_report.api.routes import router
from stock_report.api.ws import ws_router
from stock_report.config import settings
from stock_report.data.db import (
    get_latest_price_date,
    get_pending_signals,
    init_db,
    query_prices,
    resolve_signal,
)
from stock_report.data.price_sync import sync_all_prices
from stock_report.data.revenue_sync import sync_latest_revenue


logger = logging.getLogger(__name__)
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
MARKET_SYNC_READY_TIME = time(hour=16, minute=30)


@lru_cache(maxsize=1)
def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS")
    if raw is None:
        logger.warning("ALLOWED_ORIGINS not set; defaulting to http://localhost:3000")
        raw = "http://localhost:3000"
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


async def verify_origin(request: Request) -> None:
    if settings.debug:
        return
    if request.url.path in ("/api/health", "/api/db-status"):
        return
    if request.headers.get("x-api-key") == settings.api_key and settings.api_key:
        return

    allowed = _allowed_origins()
    origin = request.headers.get("origin") or ""
    referer = request.headers.get("referer") or ""
    if any(origin.startswith(item) or referer.startswith(item) for item in allowed if item):
        return
    raise HTTPException(status_code=403, detail="Origin not allowed")


def _run_initial_sync() -> None:
    thread = threading.Thread(target=sync_all_prices, name="initial-price-sync", daemon=True)
    thread.start()


def _previous_weekday(day: date) -> date:
    current = day - timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def _expected_latest_price_date(now: datetime | None = None) -> date:
    local_now = now or datetime.now(TAIPEI_TZ)
    current_day = local_now.date()
    if current_day.weekday() >= 5 or local_now.time() < MARKET_SYNC_READY_TIME:
        return _previous_weekday(current_day)
    return current_day


def _should_run_initial_sync() -> bool:
    latest_price_date = get_latest_price_date()
    expected_price_date = _expected_latest_price_date()
    should_sync = latest_price_date is None or latest_price_date < expected_price_date
    logger.info(
        "Price DB status: latest=%s expected=%s should_sync=%s",
        latest_price_date,
        expected_price_date,
        should_sync,
    )
    return should_sync


def _resolve_pending_signals() -> None:
    today = datetime.now(TAIPEI_TZ).date()
    try:
        pending_signals = get_pending_signals()
    except Exception as exc:
        logger.warning("Failed to query pending signals: %s", exc)
        return

    for signal in pending_signals:
        stock_id = str(signal["stock_id"])
        signal_date = date.fromisoformat(str(signal["signal_date"]))
        try:
            prices = query_prices(stock_id, signal_date + timedelta(days=1), today)
            if len(prices) >= 10:
                t10_bar = prices[9]
                t10_date = date.fromisoformat(str(t10_bar["date"]))
                t10_price = float(t10_bar["close"])
                entry_price = signal.get("entry_price")
                return_pct = None
                if entry_price is not None and float(entry_price) > 0:
                    return_pct = ((t10_price - float(entry_price)) / float(entry_price)) * 100
                resolve_signal(stock_id, signal_date, t10_date, t10_price, return_pct)
            elif signal_date + timedelta(days=20) < today:
                resolve_signal(stock_id, signal_date, None, None, None, status="expired")
        except Exception as exc:
            logger.warning(
                "Failed to resolve signal stock_id=%s signal_date=%s: %s",
                stock_id,
                signal_date,
                exc,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        init_db()
        if _should_run_initial_sync():
            _run_initial_sync()

        created_scheduler = BackgroundScheduler(timezone="UTC")
        created_scheduler.add_job(
            sync_all_prices,
            CronTrigger(hour=8, minute=30, timezone="UTC"),
            id="sync_stock_prices",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        created_scheduler.add_job(
            _resolve_pending_signals,
            CronTrigger(hour=9, minute=0, timezone="UTC"),
            id="resolve_pending_signals",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        # 每月 12 日 02:00 UTC（= 台北 10:00）自動同步上月月營收
        created_scheduler.add_job(
            sync_latest_revenue,
            CronTrigger(day=12, hour=2, minute=0, timezone="UTC"),
            id="sync_monthly_revenue",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        created_scheduler.start()
        scheduler = created_scheduler
    except Exception as exc:
        logger.warning("Price sync scheduler disabled: %s", exc)

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="FinMind Stock Report API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, dependencies=[Depends(verify_origin)])
app.include_router(ws_router)
app.include_router(disposition.router, dependencies=[Depends(verify_origin)])
app.include_router(institution_scan.router, dependencies=[Depends(verify_origin)])
app.include_router(pair_scan.router, dependencies=[Depends(verify_origin)])
app.include_router(chips_scan.router, dependencies=[Depends(verify_origin)])
app.include_router(cb_scan.router, dependencies=[Depends(verify_origin)])


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
