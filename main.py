import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_report.api.routes import router
from stock_report.data.db import get_latest_price_date, init_db
from stock_report.data.price_sync import sync_all_prices


logger = logging.getLogger(__name__)
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
MARKET_SYNC_READY_TIME = time(hour=16, minute=30)


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

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
