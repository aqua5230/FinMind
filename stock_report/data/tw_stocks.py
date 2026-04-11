from __future__ import annotations

import re
from typing import Iterator, List

import requests
from cachetools import TTLCache, cached

TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"


@cached(cache=TTLCache(maxsize=1, ttl=86400))
def get_tw_stock_ids() -> List[str]:
    """
    從 TWSE 和 TPEX Open API 獲取上市和上櫃公司列表，
    並過濾出 4 位數字的股票代號。
    結果會被快取 24 小時。
    """
    stock_ids = set()
    urls = [TWSE_URL, TPEX_URL]
    for url in urls:
        try:
            response = requests.get(url, timeout=10, verify=False)
            response.raise_for_status()
            data = response.json()
            for item in data:
                stock_id = item.get("公司代號")
                if stock_id and re.match(r"^\d{4}$", stock_id):
                    stock_ids.add(stock_id)
        except (requests.RequestException, ValueError) as e:
            # 在一個 API 失敗時，可以選擇記錄錯誤但繼續
            print(f"Could not fetch stock IDs from {url}: {e}")
            continue
    return sorted(list(stock_ids))


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
