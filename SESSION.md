# SESSION.md — FinMind 專案狀態

更新：2026-04-24（session 21）

## 現況

台股量化掃描 + 回測系統，前後端已部署 Railway，PostgreSQL 儲存價格/訊號/月營收。

Session 21 做了 S1 安全修補（fail-closed、去 FinMind token 洩漏、全站 rate limit + verify_origin）。已 commit 未 push。

## 部署

- 後端：`railway service FinMind && railway up`（專案根目錄執行）
- 前端：`./deploy.sh`（專案根目錄）
- URL：後端 `finmind-production-23fd.up.railway.app`、前端 `frontend-production-8b27.up.railway.app`

## 下一步

### 🔴 推 S1 到 Railway（必做，順序不可顛倒）
1. Railway 後端 service 設 `API_KEY=<長字串>`
2. 設 `ALLOWED_ORIGINS=https://frontend-production-8b27.up.railway.app,http://localhost:3000`
3. `git push` 觸發部署
未設環境變數直接 push → 所有端點 403/503。

### 🟡 S1.1 補兩個架構債（可選）
- `verify_api_key` 有 sentinel 後門（`routes.py:168-170`，為讓舊測試 pass）→ 改測試語意 + 移除後門
- `verify_origin` 用 `origin.startswith()`（`main.py:55`）→ 改成精確比對（防 `localhost:3000.evil.com` 前綴繞過）

### 🟢 S2 根治 /api/price（後排）
`stock_prices` 擴 open/high 欄位 + 重跑 sync + 改讀 DB。等 S1 穩定再動。

### 🟢 Q1-Q8 清理（使用者要求先紀錄暫不處理）
Q1 個股報告管線整條移除（前端零引用）｜Q2 `twse_broker.py` → `scripts/legacy/`｜Q3 研究報告.md → `docs/research/`｜Q4 PDF 搬出 repo｜Q6 `backtest_*.py` 集中 `backtests/`｜Q7 spec 同步｜Q8 `tests/` 從 gitignore 拿掉。細節見 `git show f7acc74` 前的 SESSION.md。

## 策略狀態

| 策略 | 狀態 | 數字 |
|---|---|---|
| 月營收動能 | ✅ 主策略 | Test Sharpe 1.74、年化 29.1% |
| 雙刀配對 | ⚠️ 研究工具 | 最佳 Test Sharpe +0.10，不達標 0.5 |
| RSI 低檔反彈 | ❌ 廢棄 | Sharpe -0.30，主掃描已移除 |
| 處置股 / 籌碼 / 可轉債 / 法人 | ✅ 掃描已部署 | 需回測驗證才可實盤 |

月營收動能訊號：RevenueYoY 前 20% + 流動性 > 500 萬，TWII < 200MA 時不持股。

## 核心檔案

- `main.py` FastAPI 入口、lifespan 排程、verify_origin dependency
- `stock_report/api/routes.py` 核心 route（price/stocks/realtime/report/signals）+ verify_api_key
- `stock_report/api/_limiter.py` slowapi Limiter（per-IP）
- `stock_report/api/{scan,pair_scan,institution_scan,disposition,chips_scan,cb_scan}.py` 6 個掃描器
- `stock_report/data/db.py` PostgreSQL schema/CRUD（含 `stock_prices`、`signal_records`、`stock_revenue_monthly`）
- `stock_report/data/price_sync.py` yfinance 每日 16:30 同步
- `frontend/app/page.tsx` 量化終端機（1096 行，過重，新功能別再塞）

## 禁止碰

- `railway up` 不能從 `frontend/` 執行
- `frontend/components/chart/{CandlestickChart,KLinePanel}.tsx`（已穩定）
- `trading/`（模擬下單 + 憑證，除非明確要求）
- `.env` / token / 憑證
- `stock_report/data/` schema（等 S2 才動 DB）

## 核心教訓

1. 勝率 ≠ 賺錢，只看勝率是自欺
2. 「T+X 持有勝率」是外行指標，停損停利後會劇變
3. 改 UI 前先 grep 確認元件有被 import
4. 沒完整模擬不上實盤
5. fail-open 驗證是安全反模式（S1 教訓）

## 本地未 push commits

- `55a0b27` SESSION.md 封存 session 21
- `f7acc74` 安全修補 S1
- `b80c6bb` 技術債清理第一輪

詳細改動細節靠 `git log` / `git show <hash>`，不在此檔重複。
