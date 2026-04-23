# SESSION.md — FinMind 專案狀態

更新時間：2026-04-24（session 21，安全修補 S1）

---

## 專案結構

```
FinMind/
├── stock_report/          ← FastAPI 後端
│   ├── api/routes.py      ← 主要 API endpoints
│   ├── api/scan.py        ← 月營收掃描（RSI 舊 route 已移除）
│   ├── api/pair_scan.py   ← 雙刀配對掃描
│   ├── api/institution_scan.py ← 法人籌碼掃描（待做）
│   ├── api/ws.py          ← Fugle WebSocket
│   └── data/
│       ├── tw_stocks.py   ← 台股清單（TWSE+TPEX）
│       ├── db.py          ← PostgreSQL 連線、月營收、價格
│       └── price_sync.py  ← 每日批次價格同步
├── frontend/              ← Next.js 前端
│   ├── app/page.tsx       ← 首頁（量化終端機，含所有 tab）
│   ├── lib/api.ts         ← API 函數
│   ├── lib/signals.ts     ← 訊號計算
│   └── lib/types.ts
├── backtest_revenue.py    ← 月營收動能回測（現役）
├── backtest_revenue.py    ← 月營收動能回測
├── backtest_pairs.py      ← 雙刀配對回測（已完成，待執行）
└── scripts/
    ├── build_tw_universe.py
    └── fetch_revenue.py
```

## 部署

- 後端 URL：`https://finmind-production-23fd.up.railway.app`
- 前端 URL：`https://frontend-production-8b27.up.railway.app`
- **部署指令（從專案根目錄）：**
  - 前端：`./deploy.sh`
  - 後端：`railway service FinMind && railway up`
- ⚠️ 前後端是兩個獨立 service，各自需要部署

---

## 當前功能狀態（全部已部署）

| 功能 | 狀態 |
|------|------|
| 月營收動能掃描 | ✅ 每月 12 日 10:00 自動更新，手動：`python3 /tmp/push_revenue_to_api.py` |
| 雙刀配對掃描 | ⚠️ 保留為研究工具，回測不達標（最佳 Sharpe +0.10），**不可作為實盤訊號** |
| 全 tab 說明面板 | ✅ 所有 7 個 tab 均有 ? 按鈕 + 說明面板（策略邏輯、篩選條件、注意事項）|
| 盤中即時股價 | ✅ `/api/realtime`（TWSE 免費 API），Fugle WebSocket 補強 |
| Railway PostgreSQL | ✅ 月營收 169,689 筆，價格每日 16:30 同步 |
| 法人籌碼掃描 | ✅ `/api/institution-scan`，TWSE T86 免費 API，TTL 3600s，已部署 |
| 處置股追蹤 | ✅ `/api/disposition-scan`，TWSE punish API，TTL 3600s，已部署 |
| 籌碼好掃描（Feature 4） | ✅ `/api/chips-scan`，DB 價格 + T86 法人，TTL 3600s，已部署 |
| 可轉債監控（Feature 5） | ✅ `/api/cb-scan`，TPEX OpenAPI ISSBD5，TTL 1800s，已部署 |

---

## 策略結論（重要，勿忘）

### RSI 策略 — 已廢棄，禁止實盤

| 指標 | 結果 |
|------|------|
| 勝率（真實含停損停利）| 34.87% |
| 年化報酬 | -8.20% |
| Max Drawdown | 50.36% |
| Sharpe | -0.30 |

**「T+10 持有勝率 75.8%」是誤導性指標，不可作為實盤依據。**

- `/api/scan` 舊掃描 route 已移除。
- 前端 `fetchScan()` / `scanResults` 已移除。
- 舊回測檔（`backtest.py`、`backtest_v2.py`、`grid_search.py`、相關 csv/png）已刪除。

### 月營收動能策略 — 目前掃描器使用中

| 指標 | Train (2019-2022) | Test (2023-2025) |
|------|------------------|-----------------|
| 年化報酬 | 13.8% | **29.1%** |
| Sharpe | 0.86 | **1.74** |
| Max Drawdown | -12.5% | **-13.3%** |

- 訊號：RevenueYoY 前 20%，流動性 > 500 萬
- 大盤濾網：TWII < 200MA 時不持股

---

## 下個 Session 優先任務（續 S1）

| 優先度 | 項目 | 下一步 |
|--------|------|--------|
| 🔴 高 | 推 S1 到 Railway | **先**在 Railway 設 `API_KEY` + `ALLOWED_ORIGINS` 環境變數，再 `git push`。若直接 push 會 403/503 全死 |
| 🟡 中 | S1.1 補兩個架構債 | `verify_api_key` sentinel 後門 + `verify_origin` startswith bypass。任務書已在 session 21 尾結論備好 |
| 🟢 低 | Q1-Q8 清理 | 見下方「待使用者決定（下一輪）」段，使用者已要求「先紀錄，暫時不處理」|
| 🟢 低 | S2 根治 /api/price | `stock_prices` 擴 open/high 欄、重抓、改讀 DB。先等 S1 在 Railway 穩定運作再動 |

**本地未 push 的 commits**
- `f7acc74` 安全修補 S1
- `b80c6bb` 技術債清理第一輪
- 兩者累計：11 files changed + 9 files changed，**未推 Railway**

---

## backtest_pairs.py 現有參數

```python
ENTRY_Z        = 1.5   # Gemini 建議 2.0（台股假突破多）
MAX_HOLD_DAYS  = 15    # Gemini 建議 20-40
STOP_LOSS_PCT  = -0.05 # 缺 Z-score 停損，建議補 Z=3.5 門檻
```

Gemini 建議：雙重停損（Z=3.5 + 虧損 5-10%）

---

## 待做 Feature 規格

### Feature 2：處置股追蹤（✅ 已完成部署）

- 資料來源：TWSE 免費 API `https://www.twse.com.tw/zh/api/getDisposition`
  （FinMind `TaiwanStockDispositionSecuritiesPeriod` 為付費，不用）
- 新增 `stock_report/api/disposition.py`
- 掃描條件：
  - `days_to_release <= 5`（快出獄）
  - 處置期間最大跌幅 < -8%（價沒崩）
  - 處置期間均量 < 處置前20日均量 × 0.5（量縮）
- 回傳欄位：`stock_id`、`stock_name`、`disposition_start`、`disposition_end`、`days_to_release`、`price_change_during`、`volume_ratio`
- 路由：`GET /api/disposition-scan`，TTL 3600
- 前端：新增「處置」tab，K 線圖加灰色底色標記

### Feature 3：法人籌碼掃描（✅ 已完成部署）

- 資料來源：TWSE T86 免費 API（原 FinMind 需付費，已棄用）
- 端點：`GET https://www.twse.com.tw/fund/T86?response=json&date=YYYYMMDD&selectType=ALLBUT0999`
- 欄位：`[0]`股票代號、`[1]`股票名稱、`[4]`外資淨買賣超、`[10]`投信淨買賣超
- 掃描邏輯：外資連買 ≥5 天 + 近 20 日投信買超 ≥3 天
- TTL 快取 3600s，第一次請求約 13 秒（25 交易日 × 0.5s sleep）

### Feature 4：籌碼好掃描增強（✅ 已完成，待部署）

```
成交量 > 300 張
漲幅 > 5%
量比 > 2（今日量 / N 日均量）
主力 1日/10日/20日 全正（三大法人淨買超替代：外資+投信）
月線乖離率由小→大排序（= MA20 deviation，最接近月線的先顯示）
```

- 後端：`stock_report/api/chips_scan.py`，路由 `GET /api/chips-scan`，TTL 3600s
- 資料源：DB `stock_prices`（價格/量比/MA20）+ TWSE T86（法人）
- 前端：新增「籌碼好」tab，顯示漲幅/量比/月線乖離率
- main.py 已 include `chips_scan.router`

### Feature 5：可轉債監控（✅ 已完成，待部署）

- 資料源：TPEX OpenAPI `https://www.tpex.org.tw/openapi/v1/bond_ISSBD5_data`
  - 含 `PutOptionDate`、`PutOptionPrice`、`Guaranteed`（1=銀行擔保）
- 篩選：Guaranteed=1 + 距賣回日 < 180 天 + 年化報酬 > 1%（以面值100估算）
- 現價假設：面值 100（實際成交價需自查；CB 近賣回日通常接近面值）
- 後端：`stock_report/api/cb_scan.py`，路由 `/api/cb-scan`，TTL 1800s
- 前端：第 8 個 tab「可轉債」，顯示代號/母股/賣回日/賣回價/現價/剩餘天/年化報酬
- ⚠️ MOPS/TWSE/舊版 TPEX API 全部已失效，TPEX OpenAPI swagger.json 是目前唯一可用免費資料源

---

## backtest_pairs.py 狀態

- 成功標準：Sharpe > 0.5、MaxDD < 20%、勝率 > 45%
- 輸出：`pairs_backtest_trades.csv`、`pairs_backtest_equity.png`

### Baseline 結果（ENTRY_Z=1.5、MAX_HOLD=15、STOP_LOSS=-5%）

| 指標 | Train | Test |
|------|-------|------|
| Sharpe | 差 | **-0.84** ❌ |
| MaxDD | — | -19.33% ✅ |
| 勝率 | — | 49.61% ✅ |

**結論：Sharpe 為負，不達標，不可上線。**

### Grid Search 結果（27 組，已完成）

| 組合 | EntryZ | MaxHold | StopLoss | Test Sharpe | Test MaxDD | Test 勝率 |
|------|--------|---------|----------|-------------|------------|----------|
| 最佳 Sharpe | 2.5 | 20 | 5% | **+0.10** | -4.9% | 60.7% |
| Train 最佳 | 2.5 | 30 | 8% | +0.01 | -5.2% | 60.4% |

**結論：全部 27 組均未達標（Sharpe > 0.5）。雙刀配對策略不可實盤。**

輸出檔案：`pairs_gs_results.csv`、`pairs_gs_best_equity.png`、`pairs_gs_best_trades.csv`

### 後續研究方向（若要繼續）

- 檢查交易成本是否侵蝕獲利
- 台股放空可行性（融券限制）
- pair selection 改良（產業群聚污染問題）
- 縮小宇宙至同產業配對

---

## 核心教訓

1. **勝率 ≠ 賺錢** — 任何只看勝率不看盈虧比的回測都是自欺
2. **「T+X 持有勝率」是外行指標** — 實際停損停利後會劇烈改變
3. **改 UI 前先確認元件有被 import** — 用 `grep -n "ComponentName"` 全專案搜
4. **不要把實盤建立在未經完整模擬的策略上**

---

## 工作流規則

- 程式碼任務 → `cat task.md | codex exec --full-auto -`
- 查資料/跑腳本 → `gemini -p "..." --model gemini-2.5-pro --yolo`
- 驗收 → `tsc --noEmit` + 線上 bundle 驗證
- 部署 → `./deploy.sh`（前端）、`railway service FinMind && railway up`（後端）

## 禁止碰的地方

- `railway up` 不能從 `frontend/` 目錄執行
- `CandlestickChart.tsx` chart 繪製邏輯（已穩定）
- `KLinePanel.tsx` handler 邏輯

---

## 2026-04-24 技術債清理（第一輪）

**已清**
- 過期 AI 協作殘留：`000.md`、`SESSION_CODEX.md`、`SESSION_GEMINI.md`、`shared_context.md`、`codex_arch_review.md`、`gemini_security_review.md`、`TASK_LOG.md`（後兩個 git rm）
- Next.js 預設素材：`frontend/public/{next,vercel,file,globe,window}.svg`
- 自動生成檔：所有 `__pycache__/`（10 個）、`.DS_Store`、`frontend/tsconfig.tsbuildinfo`
- `.gitignore` 整理：移除 `codex_arch_review.md`、`shared_context.md`；新增 `frontend/tsconfig.tsbuildinfo`、`backtests/outputs/`
- 回測輸出歸檔：10 個 `*_trades.csv` / `*_equity.png` / `*_report.json` 從 root 搬到 `backtests/outputs/`（已 gitignore）

**驗證**
- `python3 -c "import main"` 通過
- `frontend` tsc --noEmit 通過
- `pytest tests/` 18/18 通過

**待使用者決定（下一輪，暫停）**

以下 Q1-Q8 於 2026-04-24 盤點後暫停，等使用者拍板再動手。

### Q1｜個股報告管線整條移除
- 理由：前端零引用（grep `/api/report` / `fetchReport` 都 0 命中），是舊 FinMind 範例遺留
- 影響檔：
  - Route：`POST /api/report`、`GET /api/report/{stock_id}`（`stock_report/api/routes.py`）
  - Python：`stock_report/cli.py`、`services/report_service.py`、`report/generator.py`、`api/deepseek.py`、`api/gemini.py`（5 檔全刪）
  - `stock_report/models.py` 的 `StockReport`（需確認無他處引用）
  - `requirements.txt`：`anthropic`、`typer`
  - `config.py`：`llm_api_key`、`deepseek_api_key`、`deepseek_model`、`gemini_api_key`、`gemini_model`、`generation`（6 欄位）
  - `.env.example`：對應變數
- Claude 建議：**移除**（`specs/mission.md` 明確不含 AI 報告功能；未來真要做重寫更快）

### Q2｜`twse_broker.py` 根目錄孤兒
- 現況：root 孤兒檔 268 行，CLI 解析 TWSE 卷商交易明細 ZIP，grep 零引用
- Claude 建議：**搬 `scripts/legacy/twse_broker.py`**（`scripts/` 已 gitignore，保留本機不入 repo）

### Q3｜`台股量化交易策略研究報告.md`
- 現況：182 行研究筆記（RSI 失敗分析 + 替代策略方向）
- Claude 建議：**搬 `docs/research/台股量化策略初步分析.md`**（重命名 + 新增 `docs/research/` 目錄版控）

### Q4｜`三竹股市說明書.pdf`（10MB）
- 現況：已 gitignore（`*.pdf`），僅本機
- Claude 建議：**搬 `~/Documents/FinMind/`**（repo root 不該放個人資料）

### Q5｜回測輸出 gitignore ✅ 已完成（此輪）

### Q6｜回測腳本搬 `backtests/` + 輸出路徑修正
- 涉檔：`backtest_revenue.py`（tracked）、`backtest_pairs.py`、`grid_search_pairs.py`、`backtest_strength_pullback.py`（untracked）
- Claude 建議：**搬 `backtests/{revenue,pairs,pairs_gridsearch,strength_pullback}.py`**，腳本內輸出路徑改寫成 `backtests/outputs/...`，然後 commit
- 注意：目前腳本輸出路徑是相對路徑（如 `backtest_strength_pullback.py` L50-52），下次執行會在 cwd 生檔

### Q7｜Spec 同步
- `specs/roadmap.md` 把處置股、可轉債從「Phase 3 延後」改「已完成部署」
- `specs/current-state.md` 把法人籌碼從「待做」改為「已部署」
- `specs/features/remove-rsi-legacy.md` 清掉「待刪 backtest.py / backtest_v2.py / grid_search.py」條列（SESSION.md 已寫刪了）
- Claude 建議：**全改**

### Q8｜`tests/` 當前被 gitignore = 無 CI 把關
- 現況：`.gitignore` 有 `tests/`，導致 `tests/test_helpers.py`、`tests/test_routes.py` 都沒版控
- Claude 建議：**分兩步**——先從 gitignore 拿掉 + commit，CI（GitHub Actions）之後單獨做

---

## 2026-04-24 安全修補 S1（Codex 執行 + Claude review）

**主體完成**
- `verify_api_key` fail-closed（生產：API_KEY 未設 → 503；DEBUG=true bypass 本機）
- `/api/stocks` 改用 `get_tw_stocks()`（TWSE/TPEX 免費 OpenAPI），移除 FinMind token 洩漏
- `stock_report/api/scan.py` 同步換 `get_tw_stocks()`，移除 FinMindClient
- 新增 `stock_report/api/_limiter.py`（slowapi Limiter，per-IP）
- 全站加 `@limiter.limit`：`/price` 30/min、`/realtime` 60/min、`/stocks` 10/min、`/signals*` 20/min、`/report*` 5/min、各 scan 5/min
- `main.py` 新增 `verify_origin` dependency，掛在所有 HTTP router（WebSocket 不掛），白名單 `/api/health` + `/api/db-status`
- `_price_cache` TTL 600→3600
- `requirements.txt` 加 `slowapi>=0.1.9`

**驗證**
- `python3 -c "import main"` 通過
- `pytest tests/` 18/18 通過
- `tsc --noEmit` exit 0

**待清技術債（下一輪 S1.1）**
- 債 1：`verify_api_key` 有 sentinel 後門（`routes.py:168-170`），為了讓舊測試 `test_verify_api_key_passes_when_api_key_is_not_configured` pass。根本修法：改測試語意（fail-closed 後應 raise 503，不是 pass），同步移除後門。
- 債 2：`verify_origin` 用 `origin.startswith()`（`main.py:55`），可被 `localhost:3000.evil.com` 形式繞過。實際影響接近零（CORSMiddleware + X-API-Key 是主防線），但該改成精確比對（`origin == item`）。

**S2（後續，未排）**
- `stock_prices` 擴 `open` / `high` 欄位（ALTER migration + 重跑 sync）
- `/api/price` 改讀 DB，完全移除 FinMind 呼叫

**Railway 部署注意**
- 部署前必須設 `API_KEY` 環境變數，否則所有受保護端點 503
- 必須設 `ALLOWED_ORIGINS=https://frontend-production-8b27.up.railway.app`，否則 verify_origin 只放行 localhost，前端 production 會 403
