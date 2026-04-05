from __future__ import annotations

from collections import defaultdict

from ._helpers import _to_hundred_million, _to_quarter


def process(raw: list[dict]) -> dict:
    quarters_set: set[str] = set()
    items: dict[str, dict[str, float]] = defaultdict(dict)
    type_values: dict[str, dict[str, float]] = defaultdict(dict)

    for row in raw:
        try:
            date_value = str(row["date"])
        except KeyError:
            continue
        quarter = _to_quarter(date_value)
        if quarter is None:
            continue
        quarters_set.add(quarter)
        value = _to_hundred_million(row["value"])
        items[str(row["origin_name"])][quarter] = value
        type_values[str(row["type"])][quarter] = value

    quarters = sorted(quarters_set)
    key_metrics: dict[str, dict[str, float | None]] = {}

    for quarter in quarters:
        operating_cf = (
            type_values.get("CashProvidedByOperatingActivities", {}).get(quarter)
            or type_values.get("CashFlowsFromOperatingActivities", {}).get(quarter)
            or type_values.get("NetCashInflowFromOperatingActivities", {}).get(quarter)
        )
        investing_cf = (
            type_values.get("CashProvidedByInvestingActivities", {}).get(quarter)
            or type_values.get("CashFlowsFromInvestingActivities", {}).get(quarter)
        )
        financing_cf = (
            type_values.get("CashProvidedByFinancingActivities", {}).get(quarter)
            or type_values.get("CashFlowsProvidedFromFinancingActivities", {}).get(quarter)
            or type_values.get("CashFlowsFromFinancingActivities", {}).get(quarter)
        )

        free_cash_flow = None
        if operating_cf is not None and investing_cf is not None:
            # Approximation: operating CF + investing CF, treating usually-negative investing CF as a simplified capex deduction.
            free_cash_flow = round(operating_cf + investing_cf, 2)

        key_metrics[quarter] = {
            "operating_cf": operating_cf,
            "investing_cf": investing_cf,
            "financing_cf": financing_cf,
            "free_cash_flow": free_cash_flow,
        }

    return {
        "quarters": quarters,
        "items": dict(items),
        "key_metrics": key_metrics,
    }
