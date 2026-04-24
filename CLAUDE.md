# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

本專案所有回應與文件用**繁體中文**。

## 啟動必讀

改任何程式前，依序讀：

1. `SESSION.md` — 當前狀態、已完成、下一步、禁區（使用者規定未讀不得改 code）
2. `AGENTS.md` — 工作規則與策略紀律
3. `specs/mission.md`、`specs/current-state.md`、`specs/tech-stack.md`、`specs/backtest-standards.md`
4. 做特定功能再讀 `specs/features/*.md`

結束 session / context 快滿前，必須更新 `SESSION.md`。

## 架構總覽

FinMind 是台股**量化研究與掃描系統**，不是自動下單、也不是財務建議工具。前後端是兩個獨立 Railway service，共用 PostgreSQL。

### 後端（`stock_report/` + `main.py`）

- FastAPI 應用，進入點 `main.py`；`lifespan` 啟動 APScheduler 與初始價格同步
- Router 分散在多個檔案，各自 `APIRouter()` 後於 `main.py` 用 `include_router()` 掛載：
  - `stock_report/api/routes.py` — 核心 route（`/api/health`、`/api/price/{id}`、`/api/realtime/{id}`、`/api/report`、`/api/stocks`、`/api/signals*`）
  - `stock_report/api/scan.py` — 月營收動能掃描（`/api/revenue-scan`，主策略）
  - `stock_report/api/pair_scan.py` — 雙刀配對（研究工具，回測未達標不可實盤）
  - `stock_report/api/institution_scan.py` — 法人籌碼（TWSE T86）
  - `stock_report/api/disposition.py` — 處置股（TWSE punish API）
  - `stock_report/api/chips_scan.py` — 籌碼好掃描（DB 價格 + T86 法人）
  - `stock_report/api/cb_scan.py` — 可轉債（TPEX OpenAPI `bond_ISSBD5_data`）
  - `stock_report/api/ws.py` — Fugle WebSocket 即時報價
- 資料層 `stock_report/data/`：
  - `db.py`（PostgreSQL via `psycopg2`，`DATABASE_URL` 必填；資料表 `stock_prices`、`signal_records`、`stock_revenue_monthly`）
  - `price_sync.py`、`revenue_sync.py`、`tw_stocks.py`（TWSE+TPEX 股票清單）
- 服務層 `stock_report/services/`、`stock_report/report/`、`stock_report/data/processors/`
- 快取：各 route 用 `cachetools.TTLCache`，TTL 從 30s（realtime）到 3600s（法人/籌碼）不等
- 排程（`main.py` lifespan）：
  - 每日 08:30 UTC（16:30 台北）同步價格
  - 每日 09:00 UTC 結算 T+10 pending signals
  - 每月 12 日 02:00 UTC（10:00 台北）同步月營收
- 設定在 `stock_report/config.py`（`pydantic_settings`，nested delimiter `__`）

### 前端（`frontend/`）

- Next.js 16 + React 19 + TypeScript + Tailwind 4
- `frontend/app/page.tsx` 是量化終端機首頁，承載所有掃描器 tab（scan / pair / institution / disposition / chips / cb…），目前過重，新功能優先拆 component 或獨立 module
- `frontend/lib/api.ts` 用 `NEXT_PUBLIC_API_BASE_URL`（優先）或 `API_BASE_URL` 對應後端 URL
- 圖表：`klinecharts`、`lightweight-charts`（`frontend/components/chart/`）
- `frontend/app/stock/page.tsx` 是個股頁
- 注意：`frontend/AGENTS.md` 提醒這是新版 Next.js，API 可能與訓練資料不同，寫前先看 `node_modules/next/dist/docs/`

### 禁區（不碰）

- `trading/` — 模擬下單與憑證，除非任務明確要求
- `.env`、token、憑證
- `frontend/components/chart/CandlestickChart.tsx`（chart 繪製）與 `KLinePanel.tsx`（handler）— 已穩定
- 舊 RSI 策略已廢棄；刪除前必讀 `specs/features/remove-rsi-legacy.md`

## 常用指令

### 後端

```bash
# 本機啟動（需設 DATABASE_URL）
uvicorn main:app --reload

# 測試
python3 -m pytest
python3 -m pytest tests/test_routes.py::test_map_price_row_returns_price_bar_for_valid_row

# CLI（產生個股報告）
python3 -m stock_report.cli report 2330 --year 2024
```

### 前端

```bash
cd frontend
npm run dev      # 本機開發，http://localhost:3000
npm run build    # webpack 打包
npm run lint     # eslint
npx tsc --noEmit # 型別檢查
```

專案全域套件管理優先 `bun`，其次 `npm`；Python 統一 `python3`（3.13）。

### 回測腳本（專案根目錄）

```bash
python3 backtest_revenue.py            # 月營收動能（現役主策略）
python3 backtest_pairs.py              # 雙刀配對（baseline，未達標）
python3 grid_search_pairs.py           # 雙刀配對參數網格搜尋
python3 backtest_strength_pullback.py  # 強勢回檔研究
```

輸出慣例：`<name>_trades.csv`、`<name>_equity.png`、`<name>_report.json`。

### 部署

```bash
# 前端（一定從專案根目錄執行；腳本會擋未 commit 改動、切到 frontend service、跑線上 bundle 驗證）
./deploy.sh

# 後端
railway service FinMind && railway up
```

**部署限制**：`railway up` 不可從 `frontend/` 目錄執行；deploy 前所有改動必須已 commit；前後端各自部署。

線上 URL：
- 後端 `https://finmind-production-23fd.up.railway.app`
- 前端 `https://frontend-production-8b27.up.railway.app`

## 策略紀律（硬規則）

- **勝率不等於賺錢**。任何回測至少要看 Sharpe、MaxDD、平均單筆報酬、交易次數、Profit Factor、Train/Test 分段（細節 `specs/backtest-standards.md`）
- 沒有通過完整回測的策略**不可**上前端主掃描器、不可標記為可實盤
- 失敗策略要留下教訓（spec 或 session 紀錄），不要靜默刪檔
- 事件型資料必須遵守公告日邏輯，不得偷看未來
- 目前狀態：月營收動能 = 主策略；雙刀配對 = 研究工具（回測未達標）；RSI = 已廢棄

## AI 分工與協作

- 寫 code / debug → Codex（使用者手動執行，Claude 只輸出任務書）
- 查資料 / 研究 → Gemini（`gemini -p "..." --model gemini-2.5-pro --yolo`）
- 詳細分工、任務書格式與驗收流程見使用者全域 `~/.claude/CLAUDE.md` 與 `SKILL.md`
- 不用 `Agent` 工具派 Codex/Gemini（雙倍計費），改用 Bash 直接呼叫
- 不自動 push、不跳過 hooks、改 UI 元件前先 grep 確認有被 import
