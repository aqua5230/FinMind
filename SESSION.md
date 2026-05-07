# SESSION.md — FinMind 專案狀態

更新：2026-04-25（session 22）

## 現況

台股量化掃描 + 回測系統，前後端已部署 Railway，PostgreSQL 儲存價格/訊號/月營收。

Session 21 做 S1 安全修補（verify_api_key、verify_origin、全站 rate limit）。
Session 22 清技術債（untracked 檔分類、gitignore 擴充、specs/AGENTS/CLAUDE commit）+
前端改 BFF 架構（Next.js route handler `/api/[...path]` 在 server-side 代帶
X-API-Key，瀏覽器端不持 key）。本地 dev 已實測 `hasApiKey: true` outbound。
全部 commit 完，未 push。本地領先 origin/main 91 commits。

## 部署

- 後端：`railway service FinMind && railway up`（專案根目錄執行）
- 前端：`./deploy.sh`（專案根目錄）
- URL：後端 `finmind-production-23fd.up.railway.app`、前端 `frontend-production-8b27.up.railway.app`

## 下一步

### 🔴 推 S1 + BFF 到 Railway

**環境變數（已設 ✅，`--skip-deploys`）**
- 後端 FinMind：`API_KEY`（新產 64 字元）+ `ALLOWED_ORIGINS=https://frontend-production-8b27.up.railway.app`（評估後不含 localhost，BFF 架構下白名單宜窄）
- 前端 frontend：同把 `API_KEY` + `API_BASE_URL=https://finmind-production-23fd.up.railway.app`
- 前端已清殘留孤兒變數 `NEXT_PUBLIC_API_BASE_URL`、`NEXT_PUBLIC_API_URL`
- API_KEY 值只存 Railway，取回方式見 memory `project_api_key_location.md`

**待執行（使用者點頭才動）**
1. `git push` → 後端 Railway 自動部署（1-2 分鐘）
2. `./deploy.sh`（專案根目錄）→ 前端部署
3. 煙霧測試：開前端 → 跑一個掃描，Network 應全是同源 `/api/*` 且 200

炸了的回滾：Railway dashboard rollback 前後端各自的上一版。

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
- `frontend/app/api/[...path]/route.ts` BFF catch-all proxy（server-side 代帶 X-API-Key，session 22）

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

Session 21：`b80c6bb` 技術債清理｜`f7acc74` S1 安全修補｜`55a0b27` SESSION 封存
Session 22：`118f2a4` gitignore 擴充｜`282a481` AGENTS/CLAUDE/specs/ 補上｜`0a82f1f` 前端 BFF 架構

詳細改動細節靠 `git log` / `git show <hash>`，不在此檔重複。
