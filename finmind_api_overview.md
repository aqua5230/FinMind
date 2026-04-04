# FinMind

> FinMind is an open-source financial data platform providing 75+ Taiwan market datasets and international market data (US, UK, Europe, Japan). This website (finmindtrade.com) is the official dashboard for data exploration, API token management, and sponsorship. For full API documentation, see the docs site.

## Website Features

- **Data Explorer** (`/analysis/#/data/document`): Browse and download 75+ financial datasets with interactive filters (date range, stock ID). Supports CSV download.
- **API Reference** (`/analysis/#/data/api`): API endpoint documentation, token display, dataset schema viewer, and Chinese-English column name translation.
- **Dashboards** (`/analysis/#/dashboards`): Stock analysis dashboards, strategy analysis, and backtesting tools with Highcharts visualizations.
- **Strategy System** (`/analysis/#/strategy`): LINE chatbot integration and custom strategy management.
- **Account** (`/analysis/#/account`): User registration, login, API token management, and billing info.
- **Sponsorship** (`/analysis/#/Sponsor`): Backer/Sponsor tier subscription via ECPay (Taiwan payment processor). Higher tiers unlock more datasets and higher API rate limits.

## API Quick Reference

- Base URL: `https://api.finmindtrade.com/api/v4`
- Auth: Bearer token in `Authorization` header
- API Usage: `GET https://api.web.finmindtrade.com/v2/user_info` (Authorization: Bearer {token}). Returns `user_count` (current usage) and `api_request_limit` (quota). HTTP 402 when quota exceeded.
- Rate limit: 600 req/hour (with token), 300/hour (without)
- Endpoints:
  - `POST /login` - Get auth token (params: user_id, password)
  - `GET /data` - Fetch dataset (params: dataset, data_id, start_date, end_date)
  - `GET /datalist` - List available data_id values for a dataset
  - `GET /translation` - Column name Chinese-English mapping

## Membership Tiers

- **Free**: Basic datasets, 600 req/hour
- **Backer**: More datasets (marked "backer" in docs), higher limits
- **Sponsor**: Full access to all datasets including real-time data, branch trading data, and minute-level US stock data

## Full API Reference

- [llms-full.txt](https://finmindtrade.com/llms-full.txt): Complete dataset schemas with all parameters, columns, tiers, and code examples

## Full Documentation

- [FinMind Docs](https://finmind.github.io/): Complete API documentation, dataset schemas, code examples (Python/R)
- [FinMind Docs llms.txt](https://finmind.github.io/llms.txt): Machine-readable documentation index with all 75+ dataset names and links
- [API Schema](https://finmindtrade.com/analysis/#/data/document): Interactive dataset browser (requires JavaScript)
- [GitHub](https://github.com/FinMind/FinMind): Python SDK source code

## Dataset Overview

### Taiwan Market - Technical (20 datasets)

| Dataset | Description | Tier |
|---------|------------|------|
| TaiwanStockInfo | 台股總覽 | Free |
| TaiwanStockPrice | 股價日成交資訊 | Free(w/ data_id) |
| TaiwanStockPriceAdj | 還原股價 | Free(w/ data_id) |
| TaiwanStockPriceTick | 歷史逐筆交易 | Backer |
| TaiwanStockPER | PER/PBR | Free |
| TaiwanStockDayTrading | 當沖交易 | Free(w/ data_id) |
| TaiwanStockTotalReturnIndex | 報酬指數 | Free |
| TaiwanVariousIndicators5Seconds | 台股加權指數 | Free |
| TaiwanStockKBar | 分K資料 | Sponsor |
| TaiwanStockWeekPrice | 週K | Backer |
| TaiwanStockMonthPrice | 月K | Backer |
| TaiwanStock10Year | 十年線 | Backer |
| TaiwanStockTradingDate | 台股交易日 | Free |
| TaiwanStockPriceLimit | 每日漲跌停價 | Free(w/ data_id) |
| TaiwanStockSuspended | 暫停交易公告 | Backer |

### Taiwan Market - Chip / Institutional (18 datasets)

| Dataset | Description | Tier |
|---------|------------|------|
| TaiwanStockInstitutionalInvestorsBuySell | 三大法人買賣 | Free(w/ data_id) |
| TaiwanStockTotalInstitutionalInvestors | 整體三大法人 | Free |
| TaiwanStockMarginPurchaseShortSale | 融資融劵 | Free(w/ data_id) |
| TaiwanStockShareholding | 外資持股 | Free(w/ data_id) |
| TaiwanStockHoldingSharesPer | 股權持股分級 | Backer |
| TaiwanStockSecuritiesLending | 借券成交 | Free(w/ data_id) |
| TaiwanStockTradingDailyReport | 分點資料 | Sponsor |
| TaiwanstockGovernmentBankBuySell | 八大行庫買賣 | Sponsor |

### Taiwan Market - Fundamental (12 datasets)

| Dataset | Description | Tier |
|---------|------------|------|
| TaiwanStockFinancialStatements | 綜合損益表 | Free(w/ data_id) |
| TaiwanStockBalanceSheet | 資產負債表 | Free(w/ data_id) |
| TaiwanStockCashFlowsStatement | 現金流量表 | Free(w/ data_id) |
| TaiwanStockDividend | 股利政策 | Free(w/ data_id) |
| TaiwanStockDividendResult | 除權除息結果 | Free(w/ data_id) |
| TaiwanStockMonthRevenue | 月營收 | Free(w/ data_id) |
| TaiwanStockMarketValue | 股價市值 | Backer |

### Taiwan Market - Derivative (16 datasets)

| Dataset | Description | Tier |
|---------|------------|------|
| TaiwanFuturesDaily | 期貨日成交 | Free(w/ data_id) |
| TaiwanOptionDaily | 選擇權日成交 | Free(w/ data_id) |
| TaiwanFuturesInstitutionalInvestors | 期貨三大法人 | Free(w/ data_id) |
| TaiwanOptionInstitutionalInvestors | 選擇權三大法人 | Free(w/ data_id) |
| TaiwanFuturesTick | 期貨交易明細 | Backer |
| TaiwanFuturesFinalSettlementPrice | 期貨最後結算價 | Backer |
| TaiwanOptionFinalSettlementPrice | 選擇權最後結算價 | Backer |

### International Markets

| Dataset | Description | Tier |
|---------|------------|------|
| USStockPrice | 美股股價 daily | Free |
| USStockInfo | 美股總覽 | Free |
| USStockPriceMinute | 美股股價 minute | Backer |
| UKStockPrice | 英股股價 | Free |
| EuropeStockPrice | 歐股股價 | Free |
| JapanStockPrice | 日股股價 | Free |

### Global Economic Data

| Dataset | Description | Tier |
|---------|------------|------|
| TaiwanExchangeRate | 外幣匯率 | Free |
| InterestRate | 央行利率 | Free |
| GoldPrice | 黃金價格 | Free |
| CrudeOilPrices | 原油價格 | Free |
| GovernmentBondsYield | 美國國債殖利率 | Free |
| CnnFearGreedIndex | CNN 恐懼貪婪指數 | Backer |

## Common Stock IDs

| stock_id | 公司 |
|----------|------|
| 2330 | 台積電 (TSMC) |
| 2317 | 鴻海 (Foxconn) |
| 2454 | 聯發科 (MediaTek) |
| 2882 | 國泰金 |
| 2881 | 富邦金 |
| 0050 | 元大台灣50 ETF |
