from __future__ import annotations


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
