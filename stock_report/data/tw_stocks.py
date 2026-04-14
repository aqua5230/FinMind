from __future__ import annotations

import re
from typing import Iterator, List, TypedDict

import requests
from cachetools import TTLCache, cached

TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"


class TwStock(TypedDict):
    id: str
    name: str
    market: str


def _parse_stock_rows(data: list[dict], market: str) -> list[TwStock]:
    stocks: list[TwStock] = []
    for item in data:
        stock_id = item.get("公司代號") or item.get("SecuritiesCompanyCode")
        if not stock_id or not re.match(r"^\d{4}$", stock_id):
            continue
        stocks.append(
            {
                "id": stock_id,
                "name": str(
                    item.get("公司簡稱")
                    or item.get("公司名稱")
                    or item.get("CompanyAbbreviation")
                    or item.get("CompanyName")
                    or stock_id
                ).strip(),
                "market": market,
            }
        )
    return stocks


@cached(cache=TTLCache(maxsize=2, ttl=86400))
def get_tw_stocks(verify_ssl: bool = True) -> List[TwStock]:
    """
    從 TWSE 和 TPEX Open API 獲取上市和上櫃公司列表。
    market 會標記為 TWSE 或 TPEX，供 yfinance suffix 選擇使用。
    """
    stocks_by_id: dict[str, TwStock] = {}
    for url, market in ((TWSE_URL, "TWSE"), (TPEX_URL, "TPEX")):
        try:
            response = requests.get(url, timeout=10, verify=verify_ssl)
            response.raise_for_status()
            data = response.json()
            for stock in _parse_stock_rows(data, market):
                stocks_by_id[stock["id"]] = stock
        except (requests.RequestException, ValueError) as e:
            print(f"Could not fetch stock IDs from {url}: {e}")
            continue
    return [stocks_by_id[stock_id] for stock_id in sorted(stocks_by_id)]


@cached(cache=TTLCache(maxsize=1, ttl=86400))
def get_tw_stock_ids() -> List[str]:
    """
    從 TWSE 和 TPEX Open API 獲取上市和上櫃公司列表，
    並過濾出 4 位數字的股票代號。
    結果會被快取 24 小時。
    """
    return [stock["id"] for stock in get_tw_stocks()]


class _StockIDProxy:
    """
    一個代理類，使其行為類似於股票代號列表。
    它會延遲加載並快取股票代號，同時保持對
    `TW_STOCK_IDS` 的導入的向後兼容性。
    """

    def __iter__(self) -> Iterator[str]:
        return iter(get_tw_stock_ids())

    def __len__(self) -> int:
        return len(get_tw_stock_ids())

    def __getitem__(self, item: int | slice) -> str | List[str]:
        return get_tw_stock_ids()[item]

    def __contains__(self, item: object) -> bool:
        return item in get_tw_stock_ids()


TW_STOCK_IDS: _StockIDProxy = _StockIDProxy()
