import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_report.api.routes import router


app = FastAPI(title="FinMind Stock Report API")

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
