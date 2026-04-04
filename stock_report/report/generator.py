from __future__ import annotations

from typing import Any

from stock_report.api.deepseek import DeepSeekClient
from stock_report.api.gemini import GeminiClient
from stock_report.config import settings
from stock_report.exceptions import ClaudeAPIError
from stock_report.models import FinancialData, ReportMetrics, StockReport


REPORT_PROMPT_TEMPLATE = """
你是一位專業的台股財報分析師，使用繁體中文，語氣專業但易懂。

## 股票資訊
股票代號：{stock_id}
公司名稱：{stock_name}
分析期間：{period}

## 損益表摘要（億元）
{income_summary}

## 資產負債表摘要（億元）
{balance_summary}

## 現金流量表摘要（億元）
{cashflow_summary}

## 三大法人動向（股）
{institutional_summary}

請依以下結構生成白話財報分析報告（約 400 字），使用繁體中文：

【🔥 營運表現】
用「做生意有多賺錢」的角度說明。避免術語，例如「淨利率」改說「每賺100塊能留下幾塊」。

【🛡️ 財務體質】
用「欠了多少錢、有多少資產」的方式說明，強調是否穩健。

【💰 現金健康度】
用「口袋剩多少零用錢」的比喻說明自由現金流是否充足。

【⚠️ 法人動向】
若外資賣超，說「外資在跑路」；若買超，說「外資在加碼」。加上本土法人立場。句末加上短期是否會震盪。

【📌 投資人結論】
一句話總結這間公司值不值得長期持有，語氣直接不繞圈子。
""".strip()


class ReportGenerator:
    def __init__(self, client: DeepSeekClient | GeminiClient | None = None):
        self.client = client or self._build_default_client()

    def generate(self, financial_data: FinancialData) -> StockReport:
        income = self._latest_key_metrics(financial_data.income_statement)
        balance = self._latest_key_metrics(financial_data.balance_sheet)
        cashflow = self._latest_key_metrics(financial_data.cashflow)
        institutional = self._institutional_summary(financial_data.institutional_investors)
        metrics = self._compute_metrics(
            financial_data.income_statement,
            financial_data.balance_sheet,
            financial_data.cashflow,
            financial_data.institutional_investors,
        )

        prompt = REPORT_PROMPT_TEMPLATE.format(
            stock_id=financial_data.stock_id,
            stock_name=financial_data.stock_name,
            period=financial_data.period,
            income_summary=self._format_metrics(
                income,
                (
                    ("quarter", "季度"),
                    ("revenue", "營收"),
                    ("operating_income", "營業利益"),
                    ("net_income", "稅後淨利"),
                    ("gross_profit", "毛利"),
                ),
            ),
            balance_summary=self._format_metrics(
                balance,
                (
                    ("quarter", "季度"),
                    ("total_assets", "總資產"),
                    ("total_liabilities", "總負債"),
                    ("equity", "股東權益"),
                    ("cash", "現金及約當現金"),
                ),
            ),
            cashflow_summary=self._format_metrics(
                cashflow,
                (
                    ("quarter", "季度"),
                    ("operating_cf", "營業現金流"),
                    ("investing_cf", "投資現金流"),
                    ("financing_cf", "融資現金流"),
                    ("free_cash_flow", "自由現金流"),
                ),
            ),
            institutional_summary=self._format_metrics(
                institutional,
                (
                    ("foreign_net_total", "外資淨買賣超"),
                    ("investment_trust_net_total", "投信淨買賣超"),
                    ("dealer_net_total", "自營商淨買賣超"),
                    ("three_institutions_net", "三大法人合計淨買賣超"),
                ),
            ),
        )
        summary = self.client.generate(prompt)

        return StockReport(
            stock_id=financial_data.stock_id,
            stock_name=financial_data.stock_name,
            summary=summary,
            metrics=metrics,
            data=financial_data,
        )

    @staticmethod
    def _unwrap_payload(payloads: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
        if isinstance(payloads, dict):
            return payloads
        if isinstance(payloads, list) and payloads and isinstance(payloads[0], dict):
            return payloads[0]
        return {}

    def _latest_key_metrics(self, payloads: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
        payload = self._unwrap_payload(payloads)
        quarters = payload.get("quarters")
        key_metrics = payload.get("key_metrics")
        if not isinstance(quarters, list) or not quarters or not isinstance(key_metrics, dict):
            return {}

        latest_quarter = str(quarters[-1])
        latest_metrics = key_metrics.get(latest_quarter, {})
        if not isinstance(latest_metrics, dict):
            latest_metrics = {}
        return {"quarter": latest_quarter, **latest_metrics}

    def _institutional_summary(self, payloads: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
        payload = self._unwrap_payload(payloads)
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            return {}
        return summary

    def _compute_metrics(
        self,
        income_payload: list[dict[str, Any]] | dict[str, Any],
        balance_payload: list[dict[str, Any]] | dict[str, Any],
        cashflow_payload: list[dict[str, Any]] | dict[str, Any],
        institutional_payload: list[dict[str, Any]] | dict[str, Any],
    ) -> ReportMetrics:
        inc = self._latest_key_metrics(income_payload)
        revenue = inc.get("revenue")
        net_income = inc.get("net_income")
        net_profit_margin = None
        if revenue and net_income and revenue > 0:
            net_profit_margin = round(net_income / revenue * 100, 1)

        bal = self._latest_key_metrics(balance_payload)
        total_assets = bal.get("total_assets")
        total_liabilities = bal.get("total_liabilities")
        debt_ratio = None
        if total_assets and total_liabilities and total_assets > 0:
            debt_ratio = round(total_liabilities / total_assets * 100, 1)

        cf_unwrapped = self._unwrap_payload(cashflow_payload)
        cf_quarters = cf_unwrapped.get("quarters", [])
        cf_key_metrics = cf_unwrapped.get("key_metrics", {})
        fcf_total = None
        total = 0.0
        has_any = False
        for quarter in cf_quarters:
            fcf = cf_key_metrics.get(quarter, {}).get("free_cash_flow")
            if fcf is not None:
                total += fcf
                has_any = True
        if has_any:
            fcf_total = round(total, 2)

        inst = self._institutional_summary(institutional_payload)
        foreign_raw = inst.get("foreign_net_total")
        foreign_net_total = int(foreign_raw) if foreign_raw is not None else None

        return ReportMetrics(
            net_profit_margin=net_profit_margin,
            debt_ratio=debt_ratio,
            free_cash_flow_total=fcf_total,
            foreign_net_total=foreign_net_total,
        )

    @staticmethod
    def _format_metrics(metrics: dict[str, Any], fields: tuple[tuple[str, str], ...]) -> str:
        lines: list[str] = []
        for key, label in fields:
            value = metrics.get(key)
            lines.append(f"{label}：{ReportGenerator._format_value(value)}")
        return "\n".join(lines)

    @staticmethod
    def _format_value(value: Any) -> str:
        if value is None:
            return "N/A"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    @staticmethod
    def _build_default_client() -> DeepSeekClient | GeminiClient:
        if settings.deepseek_api_key:
            return DeepSeekClient()
        if settings.gemini_api_key:
            return GeminiClient()
        raise ClaudeAPIError("Neither DEEPSEEK_API_KEY nor GEMINI_API_KEY is set")
