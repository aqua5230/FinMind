# Current State

更新日期：2026-04-16

## 專案定位

FinMind 目前是一個台股量化掃描與回測系統。

它已經不是單純的 FinMind API 範例。

目前核心工作是：

- 掃描台股交易機會
- 驗證策略是否真的有正期望值
- 提供前端量化終端機介面
- 用 Railway 部署前後端
- 用 PostgreSQL 保存價格、訊號、月營收資料

目前策略方向已經從舊 RSI 策略，轉向月營收動能、雙刀配對、法人籌碼與其他台股在地因子。

## 技術現況

後端：

- FastAPI
- PostgreSQL
- psycopg2
- APScheduler
- FinMind API
- TWSE 即時報價 API
- yfinance 備援
- pandas / numpy

前端：

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4
- klinecharts

測試：

- pytest
- 目前測試集中在 API helper、價格 row mapping、API key 驗證、財報處理 helper

## 主要模組

- `stock_report/`：後端主體，包含 API、資料庫、報表服務、資料處理。
- `frontend/`：Next.js 前端，首頁是量化終端機。
- `scripts/`：建 universe、抓月營收、匯入資料、驗證腳本。
- `tests/`：Python 測試。
- `data/`：本地快取資料。
- `trading/`：模擬下單相關檔案，含憑證與設定，暫時不要碰。

## 已確認功能

### 月營收動能掃描

目前是主力策略之一。

後端：

- `/api/revenue-scan`
- 使用 `stock_revenue_monthly`
- 計算最新月份 YoY
- 用流動性過濾
- 大盤低於 200MA 時不持股

前端：

- 首頁 scan tab 呼叫 `fetchRevenueScan()`
- 顯示月營收年增率、排名、月份

狀態：

- 已部署
- 每月 12 日台北 10:00 自動同步

### 盤中即時股價

後端：

- `/api/realtime/{stock_id}`
- 使用 TWSE MIS API
- 自動嘗試上市與上櫃市場
- 有 30 秒快取

前端：

- 盤中優先用 realtime
- 失敗則 fallback 到歷史價格

狀態：

- 已部署

## 需要特別標記的狀態

### 法人籌碼掃描

產品狀態：待做。

雖然目前已有：

- `stock_report/api/institution_scan.py`
- 前端 `institution` tab
- `fetchInstitutionScan()`

但使用者確認它仍視為待做。

不能因為 API 和前端 tab 已存在，就判定此功能完成。

後續需要補正式 feature spec，確認：

- 掃描條件
- 資料來源
- 驗證方式
- 是否要結合月營收 YoY
- 是否要限制小型股或流動性

### 雙刀配對策略

掃描功能已存在。

後端：

- `/api/pair-scan`
- `stock_report/api/pair_scan.py`
- 用近 130 天價格找高相關股票對
- 依最近 5 日 spread 偏離排序
- 快取 1 小時

前端：

- 首頁 pair tab
- 有說明面板
- 顯示偏離度與建議方向

回測已執行過。

目前輸出檔：

- `pairs_backtest_equity.png`
- `pairs_backtest_trades.csv`
- `pairs_gs_results.csv`
- `pairs_gs_best_equity.png`
- `pairs_gs_best_trades.csv`

2026-04-16 baseline 回測：

- 交易數：1280
- Train Sharpe：-1.84
- Test Sharpe：-0.84
- Test MaxDD：-19.33%
- Test 勝率：49.61%

2026-04-16 grid search：

- 測試參數：EntryZ 1.5 / 2.0 / 2.5，MaxHold 15 / 20 / 30，StopLoss 5% / 8% / 10%
- 最佳 Train Sharpe 組合：EntryZ=2.5，MaxHold=30，StopLoss=8%
- Train：Sharpe -0.29，MaxDD -10.1%，勝率 53.7%，交易 121 筆
- Test：Sharpe +0.01，MaxDD -5.2%，勝率 60.4%，交易 217 筆
- Test 平均單筆報酬：約 +0.49%
- 若單看 Test Sharpe，最佳組合為 EntryZ=2.5，MaxHold=20，StopLoss=5%，Test Sharpe 約 +0.10，仍未達標

目前結論：

- 結果不達標
- 不得直接上線為實盤策略
- 可保留為研究工具
- 若繼續研究，應優先檢查交易成本、放空可行性、產業群聚與其他 pair selection 條件

### RSI 舊策略

RSI 是相對強弱指標，用來判斷股票是否過弱或過熱。

本專案曾用 RSI 做低檔反彈策略。

目前結論：

- 策略已廢棄
- 禁止實盤
- 主掃描器與 API 已移除

已清除：

- `stock_report/api/scan.py` 的 `/scan` 舊 route
- `frontend/lib/api.ts` 的 `fetchScan()`
- `frontend/app/page.tsx` 的 `scanResults`

仍保留歷史研究檔，待使用者確認是否刪除或封存：

- `backtest_v2.py`
- `backtest.py`
- `grid_search.py`
- `backtest_trades.csv`
- `backtest_equity.png`

## 部署現況

後端：

- Railway service：FinMind
- URL：`https://finmind-production-23fd.up.railway.app`

前端：

- Railway service：frontend
- URL：`https://frontend-production-8b27.up.railway.app`

部署限制：

- 前端部署用 `./deploy.sh`
- 後端部署用 `railway service FinMind && railway up`
- `railway up` 不能從 `frontend/` 目錄執行

## 工作流現況

目前已有 `SKILL.md`，定義多 AI 分工：

- Claude：架構師，拆任務、寫任務單
- Codex：執行者，改程式
- Gemini：正確性審查
- 第二個 Codex：範圍審查

這套流程偏重嚴格任務單與雙線驗收。

目前已新增 `specs/` 作為專案規格資料夾。

## 目前風險

### 文件和程式碼不同步

例如法人籌碼掃描已有程式雛形，但產品狀態仍是待做。

後續 AI 不能只看檔案存在與否來判斷完成狀態。

### 舊策略殘留

RSI 舊策略已廢棄，主掃描器與前端呼叫已移除。

舊回測檔仍待使用者確認刪除或封存。

### 前端首頁過重

`frontend/app/page.tsx` 同時處理：

- 掃描
- 觀察清單
- 雙刀配對
- 法人籌碼
- UI 狀態
- 搜尋
- 本地儲存

未來新增 feature 時，應避免繼續把邏輯堆進首頁。

### Git 狀態很髒

目前有多個已修改與未追蹤檔案。

後續任務要先確認範圍，不要順手格式化或重構。
