import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_report.api.routes import router
from stock_report.data.db import has_price_data, init_db
from stock_report.data.price_sync import sync_all_prices


logger = logging.getLogger(__name__)


def _run_initial_sync() -> None:
    thread = threading.Thread(target=sync_all_prices, name="initial-price-sync", daemon=True)
    thread.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        init_db()
        if not has_price_data():
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
