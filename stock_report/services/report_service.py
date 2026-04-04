from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from stock_report.api.finmind import FinMindClient
from stock_report.data.processors import balance, cashflow, income, institutional
from stock_report.exceptions import InvalidStockError
from stock_report.logger import get_logger
from stock_report.models import FinancialData, StockReport
from stock_report.report.generator import ReportGenerator


logger = get_logger(__name__)

_DATASETS: tuple[tuple[str, str], ...] = (
    ("income_statement", "TaiwanStockFinancialStatements"),
    ("balance_sheet", "TaiwanStockBalanceSheet"),
    ("cashflow", "TaiwanStockCashFlowsStatement"),
    ("institutional_investors", "TaiwanStockInstitutionalInvestorsBuySell"),
)


class ReportService:
    def __init__(self) -> None:
        self.finmind = FinMindClient()
        self.generator = ReportGenerator()

    def generate_report(
        self,
        stock_id: str,
        year: int = 2024,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> StockReport:
        start_year = start_year if start_year is not None else year
        end_year = end_year if end_year is not None else year
        stock_name = self._get_stock_name(stock_id)

        start_date = f"{start_year}-01-01"
        end_date = f"{end_year}-12-31"

        with ThreadPoolExecutor(max_workers=len(_DATASETS)) as executor:
            futures = {
                key: executor.submit(
                    self._safe_fetch,
                    dataset,
                    stock_id,
                    start_date,
                    end_date,
                )
                for key, dataset in _DATASETS
            }

        raw_income = futures["income_statement"].result()
        raw_balance = futures["balance_sheet"].result()
        raw_cashflow = futures["cashflow"].result()
        raw_institutional = futures["institutional_investors"].result()

        financial_data = FinancialData(
            stock_id=stock_id,
            stock_name=stock_name,
            period=f"{start_year} - {end_year}",
            income_statement=[self._process_or_empty(income.process, raw_income)],
            balance_sheet=[self._process_or_empty(balance.process, raw_balance)],
            cashflow=[self._process_or_empty(cashflow.process, raw_cashflow)],
            institutional_investors=[self._process_or_empty(institutional.process, raw_institutional)],
        )
        return self.generator.generate(financial_data)

    def _get_stock_name(self, stock_id: str) -> str:
        rows = self.finmind.fetch("TaiwanStockInfo", stock_id, "", "")
        for row in rows:
            stock_name = row.get("stock_name")
            if isinstance(stock_name, str) and stock_name.strip():
                return stock_name.strip()
        raise InvalidStockError(stock_id)

    def _process_or_empty(
        self,
        processor: Any,
        raw: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not raw:
            return {}
        return processor(raw)

    def _safe_fetch(
        self,
        dataset: str,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        try:
            return self.finmind.fetch(dataset, stock_id, start_date, end_date)
        except Exception as exc:
            logger.warning(
                "Failed to fetch dataset=%s stock_id=%s: %s",
                dataset,
                stock_id,
                exc,
            )
            return []
