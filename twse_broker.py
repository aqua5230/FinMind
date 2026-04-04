#!/usr/bin/env python3
"""Probe TWSE broker-related endpoints and parse paid E-Shop daily broker ZIP files.

The public BFIAUU family on TWSE is for block trading, not broker branch daily flow.
Broker branch data is sold through TWSE Data E-Shop as "買賣日報表".
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from typing import Iterable

import requests


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


@dataclass
class ProbeResult:
    label: str
    url: str
    ok: bool
    status: str
    detail: str


def candidate_requests(date_yyyymmdd: str, stock_no: str) -> list[tuple[str, str, dict[str, str]]]:
    return [
        (
            "current_rwd_broker_bfiauu_json",
            "https://www.twse.com.tw/rwd/zh/broker/BFIAUU",
            {"response": "json", "date": date_yyyymmdd, "stockNo": stock_no},
        ),
        (
            "current_rwd_block_bfiauu_json",
            "https://www.twse.com.tw/rwd/zh/trading/block/BFIAUU",
            {"response": "json", "date": date_yyyymmdd, "stockNo": stock_no},
        ),
        (
            "legacy_block_bfiauu_html",
            "https://www.twse.com.tw/block/BFIAUU",
            {"response": "html", "date": date_yyyymmdd, "selectType": "S", "stockNo": stock_no},
        ),
        (
            "legacy_block_bfiauu_json",
            "https://www.twse.com.tw/block/BFIAUU",
            {"response": "json", "date": date_yyyymmdd, "selectType": "S", "stockNo": stock_no},
        ),
        (
            "exchange_report_bfiauu_json",
            "https://www.twse.com.tw/exchangeReport/BFIAUU",
            {"response": "json", "date": date_yyyymmdd, "stockNo": stock_no},
        ),
    ]


def probe_public_endpoints(date_yyyymmdd: str, stock_no: str, timeout: int) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})

    for label, url, params in candidate_requests(date_yyyymmdd, stock_no):
        try:
            response = session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            results.append(
                ProbeResult(
                    label=label,
                    url=requests.Request("GET", url, params=params).prepare().url,
                    ok=False,
                    status="request_error",
                    detail=str(exc),
                )
            )
            continue

        content_type = response.headers.get("content-type", "")
        body = response.text.strip()
        prepared_url = str(response.url)

        if "json" in content_type.lower():
            try:
                payload = response.json()
            except json.JSONDecodeError as exc:
                results.append(
                    ProbeResult(label, prepared_url, False, f"http_{response.status_code}", f"invalid json: {exc}")
                )
                continue

            summary = []
            for key in ("stat", "title", "message", "notes"):
                if key in payload and payload[key]:
                    summary.append(f"{key}={payload[key]}")
            if not summary:
                summary.append(f"json keys={sorted(payload.keys())[:8]}")
            results.append(
                ProbeResult(label, prepared_url, response.ok, f"http_{response.status_code}", "; ".join(summary))
            )
            continue

        snippet = re.sub(r"\s+", " ", body[:180])
        results.append(
            ProbeResult(
                label=label,
                url=prepared_url,
                ok=response.ok,
                status=f"http_{response.status_code}",
                detail=f"content-type={content_type or 'unknown'}; body={snippet}",
            )
        )

    return results


def decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp950", "big5", "latin1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_int(value: str) -> int:
    cleaned = re.sub(r"[,\s]", "", value)
    if cleaned in {"", "--"}:
        return 0
    return int(float(cleaned))


def split_broker_field(value: str) -> tuple[str, str]:
    match = re.match(r"^([A-Za-z0-9]{4,7})(.*)$", value.strip())
    if not match:
        return "", value.strip()
    return match.group(1).strip(), match.group(2).strip()


def iter_rows_from_zip(zip_path: str) -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith("/"):
                continue

            text = decode_bytes(archive.read(name))
            sample = "\n".join(text.splitlines()[:5])
            delimiter = "|" if "|" in sample else ","

            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            header: list[str] | None = None
            for raw_row in reader:
                row = [item.strip() for item in raw_row]
                if not any(row):
                    continue
                if header is None:
                    header = row
                    continue
                if len(row) < len(header):
                    row += [""] * (len(header) - len(row))
                yield dict(zip(header, row))


def find_key(row: dict[str, str], candidates: Iterable[str]) -> str | None:
    lowered = {key.lower(): key for key in row}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def parse_paid_zip(zip_path: str, stock_no: str) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for row in iter_rows_from_zip(zip_path):
        stock_key = find_key(row, ("證券代號", "股票代號", "stock_no", "stockno"))
        broker_key = find_key(row, ("證券商", "券商", "broker"))
        buy_key = find_key(row, ("買進股數", "買進", "buy", "buy_shares"))
        sell_key = find_key(row, ("賣出股數", "賣出", "sell", "sell_shares"))
        if not all((stock_key, broker_key, buy_key, sell_key)):
            continue
        if row[stock_key].strip() != stock_no:
            continue

        broker_code, broker_name = split_broker_field(row[broker_key])
        buy_shares = parse_int(row[buy_key])
        sell_shares = parse_int(row[sell_key])
        buy_lots = buy_shares // 1000
        sell_lots = sell_shares // 1000
        parsed.append(
            {
                "券商代號": broker_code,
                "券商名稱": broker_name,
                "買進張數": buy_lots,
                "賣出張數": sell_lots,
                "買賣超": buy_lots - sell_lots,
            }
        )

    return sorted(parsed, key=lambda item: (-abs(int(item["買賣超"])), item["券商代號"], item["券商名稱"]))


def render_markdown_table(rows: list[dict[str, object]]) -> str:
    headers = ["券商代號", "券商名稱", "買進張數", "賣出張數", "買賣超"]
    out = ["| " + " | ".join(headers) + " |", "| --- | --- | ---: | ---: | ---: |"]
    for row in rows:
        out.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe TWSE broker endpoints and parse E-Shop broker ZIP files.")
    parser.add_argument("--date", default="2026-04-02", help="trade date in YYYY-MM-DD")
    parser.add_argument("--stock", default="1001", help="stock number to query")
    parser.add_argument("--zip", dest="zip_path", help="optional local TWSE Data E-Shop ZIP file path")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds")
    args = parser.parse_args()

    date_yyyymmdd = args.date.replace("-", "")
    print(f"查詢日期: {args.date}")
    print(f"查詢股票代號: {args.stock}")
    if args.stock == "1001":
        print("注意: 台泥的上市代號是 1101，不是 1001。這次仍照指令用 1001 測試。")

    print("\n[1] 測試公開 BFIAUU 類端點")
    probe_results = probe_public_endpoints(date_yyyymmdd=date_yyyymmdd, stock_no=args.stock, timeout=args.timeout)
    for result in probe_results:
        print(f"- {result.label}")
        print(f"  URL: {result.url}")
        print(f"  狀態: {result.status}")
        print(f"  摘要: {result.detail}")

    print("\n[2] 判斷")
    print("BFIAUU 系列是鉅額交易查詢代碼，並非公開的券商分點買賣 API。")
    print("TWSE 券商分點日資料對應的是 Data E-Shop 的「買賣日報表」ZIP。")

    if not args.zip_path:
        print("\n未提供本地 ZIP，因此無法輸出指定日期/股票的券商分點表格。")
        print("若你已購買 E-Shop 檔案，請重新執行：")
        print(f"  python3 twse_broker.py --date {args.date} --stock {args.stock} --zip /path/to/BSR_*.ZIP")
        return 0

    if not os.path.exists(args.zip_path):
        print(f"\n找不到 ZIP 檔案: {args.zip_path}", file=sys.stderr)
        return 1

    print(f"\n[3] 解析付費 ZIP: {args.zip_path}")
    rows = parse_paid_zip(args.zip_path, args.stock)
    if not rows:
        print("ZIP 已讀取，但找不到符合該股票代號的券商分點資料。")
        return 1

    print(render_markdown_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
