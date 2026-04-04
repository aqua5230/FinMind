from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class FinancialData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    stock_name: str
    period: str
    income_statement: list[dict] = Field(default_factory=list)
    balance_sheet: list[dict] = Field(default_factory=list)
    cashflow: list[dict] = Field(default_factory=list)
    institutional_investors: list[dict] = Field(default_factory=list)


class ReportMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    net_profit_margin: float | None = None
    debt_ratio: float | None = None
    free_cash_flow_total: float | None = None
    foreign_net_total: int | None = None


class StockReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_id: str
    stock_name: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str
    metrics: ReportMetrics = Field(default_factory=ReportMetrics)
    data: FinancialData
