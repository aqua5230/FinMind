from __future__ import annotations

from collections import defaultdict

from ._helpers import _to_hundred_million, _to_quarter


def process(raw: list[dict]) -> dict:
    quarters_set: set[str] = set()
    items: dict[str, dict[str, float]] = defaultdict(dict)
    type_values: dict[str, dict[str, float]] = defaultdict(dict)

    for row in raw:
        row_type = str(row["type"])
        if row_type.endswith("_per"):
            continue

        quarter = _to_quarter(str(row["date"]))
        if quarter is None:
            continue
        quarters_set.add(quarter)
        value = _to_hundred_million(row["value"])
        items[str(row["origin_name"])][quarter] = value
        type_values[row_type][quarter] = value

    quarters = sorted(quarters_set)
    key_metrics: dict[str, dict[str, float | None]] = {}

    for quarter in quarters:
        total_liabilities = (
            type_values.get("TotalLiabilities", {}).get(quarter)
            or type_values.get("Liabilities", {}).get(quarter)
        )
        equity = (
            type_values.get("TotalEquity", {}).get(quarter)
            or type_values.get("EquityAttributableToOwnersOfParent", {}).get(quarter)
            or type_values.get("Equity", {}).get(quarter)
        )

        key_metrics[quarter] = {
            "total_assets": type_values.get("TotalAssets", {}).get(quarter),
            "total_liabilities": total_liabilities,
            "equity": equity,
            "cash": type_values.get("CashAndCashEquivalents", {}).get(quarter),
        }

    return {
        "quarters": quarters,
        "items": dict(items),
        "key_metrics": key_metrics,
    }
