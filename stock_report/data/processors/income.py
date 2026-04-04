from __future__ import annotations

from collections import defaultdict


_NET_INCOME_KEYS = (
    "ContinuingOperationsNetIncome",
    "NetIncome",
    "IncomeAfterTaxes",
    "IncomeFromContinuingOperations",
)


def _to_quarter(date_value: str) -> str | None:
    try:
        year, month, _ = date_value.split("-")
    except ValueError:
        return None
    quarter_map = {"03": "Q1", "06": "Q2", "09": "Q3", "12": "Q4"}
    quarter = quarter_map.get(month)
    if quarter is None:
        return None
    return f"{year}{quarter}"


def _to_hundred_million(value: float | int) -> float:
    return round(float(value) / 1e8, 2)


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
        net_income = None
        for key in _NET_INCOME_KEYS:
            net_income = type_values.get(key, {}).get(quarter)
            if net_income is not None:
                break

        key_metrics[quarter] = {
            "revenue": type_values.get("Revenue", {}).get(quarter),
            "operating_income": type_values.get("OperatingIncome", {}).get(quarter),
            "net_income": net_income,
            "gross_profit": type_values.get("GrossProfit", {}).get(quarter),
        }

    return {
        "quarters": quarters,
        "items": dict(items),
        "key_metrics": key_metrics,
    }
