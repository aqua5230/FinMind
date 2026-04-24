# Tech Stack

更新日期：2026-04-16

## 後端

框架：

- FastAPI
- Uvicorn

主要入口：

- `main.py`

主要模組：

- `stock_report/api/`：API routes 與掃描器
- `stock_report/data/`：資料庫、價格同步、營收同步
- `stock_report/services/`：報表服務
- `stock_report/report/`：報告產生

資料庫：

- PostgreSQL
- 透過 `DATABASE_URL` 連線
- 使用 `psycopg2`

已知資料表：

- `stock_prices`
- `signal_records`
- `stock_revenue_monthly`

排程：

- APScheduler
- 每日價格同步
- 每日 pending signals 結算
- 每月 12 日同步月營收

外部資料：

- FinMind API
- TWSE MIS 即時報價 API
- yfinance 備援

## 前端

框架：

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4

主要入口：

- `frontend/app/page.tsx`
- `frontend/app/stock/page.tsx`

API 包裝：

- `frontend/lib/api.ts`

圖表：

- `klinecharts`
- `lightweight-charts`

注意：

- `frontend/app/page.tsx` 目前承擔太多功能。
- 新功能不應繼續無限制塞進首頁。
- 若新增大型功能，應優先考慮拆 component 或獨立 feature module。

## 部署

前端與後端是兩個 Railway service。

後端：

- service：`FinMind`
- start command：`uvicorn main:app --host 0.0.0.0 --port $PORT`
- healthcheck：`/api/health`

前端：

- service：`frontend`
- 部署腳本：`./deploy.sh`
- 線上 URL：`https://frontend-production-8b27.up.railway.app`

部署限制：

- 前端部署必須從專案根目錄執行 `./deploy.sh`
- 後端部署使用 `railway service FinMind && railway up`
- 不要從 `frontend/` 目錄執行 `railway up`
- deploy 前要注意 git 是否有未 commit 改動

## 驗證方式

Python：

- `pytest`

前端：

- `cd frontend && npm run lint`
- `cd frontend && npm run build`

API：

- `/api/health`
- `/api/revenue-scan`
- `/api/pair-scan`
- `/api/realtime/{stock_id}`

部署後：

- 前端線上 bundle 驗證
- 後端 healthcheck

## 工作規則

- 不碰 `trading/`，除非任務明確要求。
- 不改 `.env`、token、憑證。
- 不在同一步混合策略研究、程式刪除、部署。
- 新功能先寫 feature spec，再實作。
- 回測差的策略要明確標記，不要只留下輸出圖。
- 刪除舊策略時，要同時檢查前端、後端、文件與測試引用。
