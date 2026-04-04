from __future__ import annotations

from collections import defaultdict


def _empty_bucket() -> dict[str, int]:
    return {"buy": 0, "sell": 0}


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _series_from_dates(dates: list[str], grouped: dict[str, dict[str, int]]) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for date in dates:
        buy = grouped.get(date, {}).get("buy", 0)
        sell = grouped.get(date, {}).get("sell", 0)
        rows.append(
            {
                "date": date,
                "buy": buy,
                "sell": sell,
                "net": buy - sell,
            }
        )
    return rows


def process(raw: list[dict]) -> dict:
    foreign_by_date: dict[str, dict[str, int]] = defaultdict(_empty_bucket)
    investment_trust_by_date: dict[str, dict[str, int]] = defaultdict(_empty_bucket)
    dealer_by_date: dict[str, dict[str, int]] = defaultdict(_empty_bucket)
    dates = sorted({str(row["date"]) for row in raw})

    for row in raw:
        date = str(row["date"])
        try:
            buy = int(row["buy"])
        except (TypeError, ValueError, KeyError):
            buy = 0
        try:
            sell = int(row["sell"])
        except (TypeError, ValueError, KeyError):
            sell = 0
        name = _normalize_name(str(row["name"]))

        if name in {"foreign_investor", "foreign_dealer_self"}:
            foreign_by_date[date]["buy"] += buy
            foreign_by_date[date]["sell"] += sell
        elif name == "investment_trust":
            investment_trust_by_date[date]["buy"] += buy
            investment_trust_by_date[date]["sell"] += sell
        elif name in {"dealer", "dealer_self", "dealer_hedging"}:
            dealer_by_date[date]["buy"] += buy
            dealer_by_date[date]["sell"] += sell

    foreign = _series_from_dates(dates, foreign_by_date)
    investment_trust = _series_from_dates(dates, investment_trust_by_date)
    dealer = _series_from_dates(dates, dealer_by_date)

    foreign_net_total = sum(int(row["net"]) for row in foreign)
    investment_trust_net_total = sum(int(row["net"]) for row in investment_trust)
    dealer_net_total = sum(int(row["net"]) for row in dealer)

    return {
        "dates": dates,
        "foreign": foreign,
        "investment_trust": investment_trust,
        "dealer": dealer,
        "summary": {
            "foreign_net_total": foreign_net_total,
            "investment_trust_net_total": investment_trust_net_total,
            "dealer_net_total": dealer_net_total,
            "three_institutions_net": foreign_net_total + investment_trust_net_total + dealer_net_total,
        },
    }
