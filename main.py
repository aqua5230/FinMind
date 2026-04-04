from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_report.api.routes import router


app = FastAPI(title="FinMind Stock Report API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
