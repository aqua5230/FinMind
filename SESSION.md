# SESSION.md — FinMind 專案狀態

更新：2026-05-08（session 23）

## 現況

台股量化掃描 + 回測系統，前後端 service 在 Railway，PostgreSQL 儲存價格/訊號/月營收。

Session 23 做完 S1.1 安全收尾 + 前端透明度標籤 + tests 進版控，三個 commit
（`753d6f7`、`79d0d66`、`b313d10`）已 push 到 origin/main。本地與 origin 同步。

**部署狀態：⚠️ Railway trial 過期，前後端 service 都掛**
- `git push` 觸發後端 build 但 Railway 拒絕（trial expired）→ 後端 502
- `./deploy.sh` 上傳階段被擋（"Your trial has expired"）→ 前端 404
- 不是 code 問題，git rollback 也救不了
- 等使用者處理 Railway billing（看 referral / promo / Hobby plan）後重跑部署

## Session 23 改動摘要

| commit | 內容 |
|---|---|
| `753d6f7` | S1.1：移除 `verify_api_key` sentinel 後門；`verify_origin` 改 `urlparse` 精確比對；`tests/` 從 gitignore 拿掉進版控（Q8 收） |
| `79d0d66` | 前端：雙刀配對 / 法人籌碼 tab 工具列各加一個橘色警示 badge（永遠可見） |
| `b313d10` | SESSION.md 補上 Railway 環境變數已設、回滾備忘（session 22 收尾事實） |

pytest 18/18 全綠。tsc 沙盒跑不動，但 page.tsx 改動只是純 JSX `<span>`，無型別風險。

## 下一步

### 🔴 等 Railway billing 解決
1. 使用者處理 Railway 方案（A 升級 Hobby / D 找 credit）
2. 解開後：`railway redeploy`（或前後端分別 redeploy 上一個 build）→ 兩個 service 應自動恢復
3. 煙霧測試：開前端 → 跑一個掃描，Network 應全是同源 `/api/*` 且 200
4. 後端再 curl `/api/health` + `/api/db-status` 驗證

回滾：因為這次部署根本沒成功，沒東西好 rollback。

### 🟡 pytest 排除 trading/（小，但下次 Codex 會再撞）
- 現況：Codex 在沙盒環境跑 `pytest` 撞到 `trading/test_order.py` 的 keyring，收集階段中止
- 解法：補 `pyproject.toml` 加 `[tool.pytest.ini_options] testpaths = ["tests"]`
- 估計 5 分鐘。下次寫任務書順手一起處理

### 🟢 S2 根治 /api/price（待 S1 穩才動）
`stock_prices` 擴 open/high 欄位 + 重跑 sync + 改讀 DB。

### 🟢 page.tsx 拆解（規劃中，需 spec）
1096 行已包含 7 個 tab。不順手重構，要先寫 refactor spec：
- 拆成 `app/scan/[type]/page.tsx` 動態 route，每個 tab 獨立檔
- 還是用 dynamic import 把 tab 邏輯切到子模組
- 評估後再動

### 🟢 法人籌碼正式化（需使用者決策）
目前已標 WIP。要嘛：
- A. 補 feature spec（掃描條件、結合月營收 YoY、流動性過濾、回測標準），通過再撕掉 WIP badge
- B. 從前端拿掉，避免使用者誤用

### 🟢 Q1-Q8 清理（仍暫不處理，Q8 已收）
Q1 個股報告管線整條移除｜Q2 `twse_broker.py` → `scripts/legacy/`｜
Q3 研究報告.md → `docs/research/`｜Q4 PDF 搬出 repo｜
Q6 `backtest_*.py` 集中 `backtests/`｜Q7 spec 同步｜~~Q8 tests/ 進版控~~ ✅。

## 策略狀態

| 策略 | 狀態 | 數字 |
|---|---|---|
| 月營收動能 | ✅ 主策略 | Test Sharpe 1.74、年化 29.1% |
| 雙刀配對 | ⚠️ 研究工具（前端已標 WIP） | 最佳 Test Sharpe +0.10，不達標 0.5 |
| RSI 低檔反彈 | ❌ 廢棄 | Sharpe -0.30，主掃描已移除 |
| 處置股 / 籌碼 / 可轉債 / 法人 | ⚠️ 掃描已部署、無正式回測 | 法人前端已標 WIP；其他需回測 |

月營收動能訊號：RevenueYoY 前 20% + 流動性 > 500 萬，TWII < 200MA 時不持股。

## 核心檔案

- `main.py` FastAPI 入口、lifespan 排程、`verify_origin`（urlparse 精確比對）
- `stock_report/api/routes.py` 核心 route + `verify_api_key`（sentinel 後門已移除）
- `stock_report/api/_limiter.py` slowapi Limiter（per-IP）
- `stock_report/api/{scan,pair_scan,institution_scan,disposition,chips_scan,cb_scan}.py` 6 掃描器
- `stock_report/data/db.py` PostgreSQL schema/CRUD
- `stock_report/data/price_sync.py` yfinance 每日 16:30 同步
- `frontend/app/page.tsx` 量化終端機（1096 行，待拆）
- `frontend/app/api/[...path]/route.ts` BFF catch-all proxy（server-side 代帶 X-API-Key）
- `tests/` 已進版控（test_helpers / test_routes / fixtures）

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
6. 部署前先確認 Railway 方案狀態（session 23 教訓，已記入 memory）

## 本地未 push commits

無，已全部 push 到 origin/main。
